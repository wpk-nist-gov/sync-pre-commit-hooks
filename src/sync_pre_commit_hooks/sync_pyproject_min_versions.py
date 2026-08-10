"""Sync minimum versions of dependencies in pyproject.toml or pep723 section of python scripts to locked requirement file."""
# ruff:file-ignore[undocumented-public-class, undocumented-public-method]
# pylint: disable=missing-class-docstring

from __future__ import annotations

import re
import sys
from argparse import ArgumentParser
from dataclasses import dataclass, field
from functools import cached_property, partial
from itertools import chain
from pathlib import Path
from subprocess import check_output
from typing import TYPE_CHECKING

from packaging.requirements import InvalidRequirement, Requirement
from packaging.utils import canonicalize_name

from ._logging import get_logger
from ._utils import get_versions_from_requirements

if TYPE_CHECKING:
    from collections.abc import Callable, Container, Iterable, Sequence
    from types import EllipsisType
    from typing import Any, Final, Literal

    from packaging.utils import NormalizedName

    SCRIPT_LOCK = Literal["requirements", "infer", "force"]


logger = get_logger("sync-pyproject-min-versions")


def _get_requirements_pattern() -> str:

    # taken from https://github.com/pypa/packaging/blob/main/src/packaging/version.py
    version_pattern = r"""
        v?+                                                   # optional leading v
        (?a:
            (?:(?P<epoch>[0-9]+)!)?+                          # epoch
            (?P<release>[0-9]+(?:\.[0-9]+)*+)                 # release segment
            (?P<pre>                                          # pre-release
                [._-]?+
                (?P<pre_l>alpha|a|beta|b|preview|pre|c|rc)
                [._-]?+
                (?P<pre_n>[0-9]+)?
            )?+
            (?P<post>                                         # post release
                (?:-(?P<post_n1>[0-9]+))
                |
                (?:
                    [._-]?
                    (?P<post_l>post|rev|r)
                    [._-]?
                    (?P<post_n2>[0-9]+)?
                )
            )?+
            (?P<dev>                                          # dev release
                [._-]?+
                (?P<dev_l>dev)
                [._-]?+
                (?P<dev_n>[0-9]+)?
            )?+
        )
        (?a:\+
            (?P<local>                                        # local version
                [a-z0-9]+
                (?:[._-][a-z0-9]+)*+
            )
        )?+
    """

    version_pattern = (
        version_pattern.replace("*+", "*").replace("?+", "?")
        if (sys.implementation.name == "cpython" and sys.version_info < (3, 11, 5))
        or (sys.implementation.name == "pypy" and sys.version_info < (3, 11, 13))
        or sys.version_info < (3, 11)
        else version_pattern
    )

    return rf"""
    (?P<quote>["'])
    \s*
    (?P<inner>
        (?P<package>                                              # package name
            \b[a-zA-Z0-9][a-zA-Z0-9._-]*\b
        )
        (?P<extras>                                               # extras
            (?:\s*\[(?:\w|[,. -])*\])?\s*>=\s*
        )
        (?P<version>
        {version_pattern}
        )
        (?P<markers>                                              # everything else
            .*?
        )
    )
    (?P=quote)
    """


REQUIREMENT_REGEX: Final = re.compile(
    _get_requirements_pattern(), flags=re.VERBOSE | re.IGNORECASE
)
IGNORE_PATTERN: Final = re.compile(
    r"""
    \s*
    (?P<deps>
        [^\#]*
    )
    (:?
        \#\s*sync-pyproject-min-versions?:\s*ignore\s*
    )
    (?:
        \[(?P<ignore>[^\]]*)
    )?
    """,
    flags=re.VERBOSE,
)


def _get_ignore_names(line: str) -> tuple[set[NormalizedName] | EllipsisType, bool]:
    """
    Parse for ignore comments

    Look for comments of form `# sync-pyproject-min-versions: ignore[dep, ...]`

        * if no such comment, do not ignore (return []).
        * if comment without [dep, ...], ignore all (return Ellipsis)
        * if comment with [dep, ...], (return [dep, ...])


    Parameters
    ----------
    line : str
        String to analyze


    Returns
    -------
    ignore : set or ellipsis
        If ignore all, return ellipsis. Otherwise, return set of normalized
        dependency names to ignore.
    next_line: bool
        If True, ignore comment applies to the following line

    """
    if match := IGNORE_PATTERN.match(line):
        next_line = not bool(match.group("deps"))
        if ignore := match.group("ignore"):
            return {canonicalize_name(d.strip()) for d in ignore.split(",")}, next_line
        return Ellipsis, next_line
    return set(), False


class Replacer:
    def __init__(self, versions: dict[NormalizedName, str]) -> None:
        self.versions = versions

    def _match_func(
        self, match: re.Match[str], ignore: Container[NormalizedName]
    ) -> str:
        original_string = match.group(0)
        try:
            dep = Requirement(match.group("inner"))
        except InvalidRequirement:
            return original_string

        if (name := canonicalize_name(dep.name)) in ignore:
            return original_string

        if (
            name in self.versions
            and len(dep.specifier) == 1
            and next(iter(dep.specifier)).operator == ">="
        ):
            s = f"{match.group('quote')}{match.group('package')}{match.group('extras')}{self.versions[name]}{match.group('markers')}{match.group('quote')}"
            if s != original_string:
                logger.info("replace %s with %s", original_string, s)
            return s
        return original_string

    def _replace_line(
        self,
        line: str,
        ignore: Container[NormalizedName] | EllipsisType,
    ) -> str:
        if ignore is ...:
            return line
        return REQUIREMENT_REGEX.sub(partial(self._match_func, ignore=ignore), line)  # pyrefly: ignore[bad-argument-type]  # pyrefly bug

    def replace_contents(self, contents: str) -> str:
        out: list[str] = []
        lines = iter(contents.splitlines(keepends=True))
        line: str

        for line_ in lines:
            line = line_
            ignore, nextline = _get_ignore_names(line)
            if nextline:
                out.append(line)
                line = next(lines)
            out.append(self._replace_line(line, ignore))
        return "".join(out)

    def replace_contents_pep723(self, contents: str) -> str:
        out: list[str] = []
        found = False
        lines = iter(contents.splitlines(keepends=True))
        line: str

        for line_ in lines:
            line = line_
            if not found:
                found = re.match(r"^#\s+///\s+script$", line) is not None
                out.append(line)
                continue

            if re.match(r"^#\s+///$", line):
                return "".join(chain(out, [line], lines))

            if not re.match(r"^#", line):
                out.append(line)
                continue

            ignore, nextline = _get_ignore_names(line[1:])  # skip preceding '#'
            if nextline:
                out.append(line)
                line = next(lines)

            out.append(self._replace_line(line, ignore))

        if found:
            logger.warning("Skipping update.  Found pep723 script start but no end")

        # if got here, didn't find pep723 data
        return contents


@dataclass(frozen=True)
class Options:
    requirements: Path | None = None
    include: frozenset[NormalizedName] = field(default_factory=frozenset)
    exclude: frozenset[NormalizedName] = field(default_factory=frozenset)
    toml_paths: tuple[Path, ...] = field(default_factory=tuple)
    script_paths: tuple[Path, ...] = field(default_factory=tuple)
    script_lock: SCRIPT_LOCK = "infer"

    def normalize_versions(self, versions: dict[str, str]) -> dict[NormalizedName, str]:
        out = {canonicalize_name(name): version for name, version in versions.items()}

        if self.include:
            out = {
                name: version for name, version in out.items() if name in self.include
            }
        if self.exclude:
            out = {k: v for k, v in out.items() if k not in self.exclude}

        return out

    def get_versions_from_requirements(
        self, requirements: str | Path
    ) -> dict[NormalizedName, str]:
        return self.normalize_versions(get_versions_from_requirements(requirements))

    @cached_property
    def versions(self) -> dict[NormalizedName, str]:
        return (
            self.get_versions_from_requirements(self.requirements)
            if self.requirements
            else {}
        )

    def get_versions_from_script(self, script_path: Path) -> dict[NormalizedName, str]:
        lock_exists = script_path.with_suffix(".py.lock").exists()
        if self.script_lock == "force" or (self.script_lock == "infer" and lock_exists):
            import shlex

            args = [
                "uv",
                "export",
                *(["--frozen", "--offline"] if lock_exists else []),
                "--quiet",
                "--no-color",
                "--script",
                str(script_path),
            ]
            logger.info("Run: %s", shlex.join(args))
            return self.get_versions_from_requirements(
                check_output(args).decode("utf-8")
            )
        return self.versions

    @classmethod
    def from_params(
        cls,
        requirements: Path | None = None,
        include: Iterable[str] = (),
        exclude: Iterable[str] = (),
        paths: Iterable[Path] = (),
        script_lock: SCRIPT_LOCK = "infer",
    ) -> Options:
        # parse paths
        toml_paths: list[Path] = []
        script_paths: list[Path] = []
        for path in paths:
            suffix = path.suffix
            if suffix == ".toml":
                toml_paths.append(path)
            elif suffix == ".py":
                script_paths.append(path)
            else:
                logger.info("ignoring path %s", path)

        return cls(
            requirements=requirements,
            include=frozenset(canonicalize_name(x) for x in include),
            exclude=frozenset(canonicalize_name(x) for x in exclude),
            toml_paths=tuple(toml_paths),
            script_paths=tuple(script_paths),
            script_lock=script_lock,
        )

    @classmethod
    def from_kws(cls, kws: Any) -> Options:
        return cls.from_params(**kws)

    @classmethod
    def from_argv(cls, argv: Sequence[str] | None = None) -> Options:
        parser = ArgumentParser(description=__doc__)
        _ = parser.add_argument(
            "-r",
            "--requirements",
            type=Path,
            help="Requirements file to extract locked versions from.",
        )
        _ = parser.add_argument(
            "--include",
            default=[],
            action="append",
            help="""
            Package names to include. Default is to consider all packages in
            requirements file. Specifying ``--include`` will only update those
            packages. Can specify multiple times.
            """,
        )
        _ = parser.add_argument(
            "--exclude",
            default=[],
            action="append",
            help="""
            Packages to exclude. Default is to consider all packages in
            requirements file. Specifying ``--exclude`` will ignore those packages.
            Can specify multiple times.
            """,
        )
        _ = parser.add_argument(
            "--script-lock",
            choices=("requirements", "infer", "force"),
            default="infer",
            help="""
            How to determine locked dependencies for scripts.

            * infer (default): Use ``uv export --frozen --script script.py`` if
              ``script.py.lock`` exists or fallback to ``requirements``
            * force: Use output of ``uv export --script script.py`` always.
              Note that this may require network access.
            * requirements:  Use passed ``--requirements`` file
            """,
        )
        _ = parser.add_argument(
            "paths", nargs="*", help="pyproject.toml/script files to process", type=Path
        )

        opts = parser.parse_args(argv)

        return cls.from_params(
            requirements=opts.requirements,
            include=opts.include,
            exclude=opts.exclude,
            paths=opts.paths,
            script_lock=opts.script_lock,
        )


def _process_path(path: Path, replacer: Callable[[str], str]) -> None:
    logger.info("processing %s", path)
    contents = path.read_text(encoding="utf-8")
    out = replacer(contents)
    if contents != out:
        logger.info("update %s", path)
        _ = path.write_text(out, encoding="utf-8")
    else:
        logger.info("no change %s", path)


def main(argv: Sequence[str] | None = None) -> bool:
    """Main function"""
    opts = Options.from_argv(argv)

    if opts.toml_paths and opts.versions:
        replacer = Replacer(opts.versions)
        for path in opts.toml_paths:
            _process_path(path=path, replacer=replacer.replace_contents)

    if (opts.versions or opts.script_lock in {"infer", "force"}) and opts.script_paths:
        for path in opts.script_paths:
            lock_replacer = Replacer(opts.get_versions_from_script(path))
            if lock_replacer.versions:
                _process_path(path=path, replacer=lock_replacer.replace_contents_pep723)

    return False


if __name__ == "__main__":
    raise SystemExit(main())
