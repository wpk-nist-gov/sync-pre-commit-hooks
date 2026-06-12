"""Sync minimum versions of dependencies in pyproject.toml or pep723 section of python scripts to locked requirement file."""
# ruff: noqa: D101, D102
# pylint: disable=missing-class-docstring

from __future__ import annotations

import re
import sys
from argparse import ArgumentParser
from dataclasses import dataclass, field
from functools import partial
from itertools import chain
from pathlib import Path
from typing import TYPE_CHECKING

from packaging.requirements import InvalidRequirement, Requirement
from packaging.utils import canonicalize_name

from ._logging import get_logger
from ._utils import get_versions_from_requirements

if TYPE_CHECKING:
    from collections.abc import Callable, Sequence
    from typing import Any


logger = get_logger("sync-pyproject-min-versions")

# taken from https://github.com/pypa/packaging/blob/main/src/packaging/version.py
_version_pattern = r"""
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

_version_pattern = (
    _version_pattern.replace("*+", "*").replace("?+", "?")
    if (sys.implementation.name == "cpython" and sys.version_info < (3, 11, 5))
    or (sys.implementation.name == "pypy" and sys.version_info < (3, 11, 13))
    or sys.version_info < (3, 11)
    else _version_pattern
)

_regex_pattern = rf"""
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
       {_version_pattern}
    )
    (?P<markers>                                              # everything else
        .*?
    )
)
(?P=quote)
"""

REQUIREMENT_REGEX = re.compile(_regex_pattern, flags=re.VERBOSE | re.IGNORECASE)


def _factory_replacer(versions: dict[str, str]) -> Callable[[re.Match[str]], str]:
    def replacer(match: re.Match[str]) -> str:
        original_string = match.group(0)
        try:
            dep = Requirement(match.group("inner"))
        except InvalidRequirement:
            return original_string

        name = canonicalize_name(dep.name)
        if (
            name in versions
            and len(dep.specifier) == 1
            and next(iter(dep.specifier)).operator == ">="
        ):
            s = f"{match.group('quote')}{match.group('package')}{match.group('extras')}{versions[name]}{match.group('markers')}{match.group('quote')}"
            if s != original_string:
                logger.info("replace %s with %s", original_string, s)
            return s

        return original_string

    return replacer


def _replace_pep723_section(replacer: Callable[[str], str], contents: str) -> str:
    out: list[str] = []
    found = False
    lines = iter(contents.splitlines(keepends=True))

    for line in lines:
        if not found and re.match(r"^#\s+///\s+script$", line):
            found = True
            out.append(line)
            continue

        if found and re.match(r"^#\s+///$", line):
            return "".join(chain(out, [line], lines))

        out.append(replacer(line) if found and re.match(r"^#", line) else line)

    if found:
        logger.warning("Skipping update.  Found pep723 script start but no end")

    # if got here, didn't find pep723 data
    return contents


@dataclass
class Options:
    requirements: Path
    include: list[str] = field(default_factory=list)
    exclude: list[str] = field(default_factory=list)
    paths: list[Path] = field(default_factory=list)

    @classmethod
    def from_kws(cls, kws: Any) -> Options:
        return cls(**kws)


def _get_options(
    argv: Sequence[str] | None = None,
) -> Options:
    parser = ArgumentParser(description=__doc__)
    _ = parser.add_argument(
        "-r",
        "--requirements",
        required=True,
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
        requirements file. Specifying ``--exclude`` will skip those packages.
        Can specify multiple times.
        """,
    )
    _ = parser.add_argument(
        "paths", nargs="*", help="pyproject.toml/script files to process", type=Path
    )

    opts = parser.parse_args(argv)

    return Options(
        requirements=opts.requirements,
        include=opts.include,
        exclude=opts.exclude,
        paths=opts.paths,
    )


def _normalize_versions(
    versions: dict[str, str], include: list[str], exclude: list[str]
) -> dict[str, str]:

    # canonicalize names
    versions = {canonicalize_name(name): version for name, version in versions.items()}

    include_set, exclude_set = (
        {canonicalize_name(x) for x in o} for o in (include, exclude)
    )

    if include_set:
        versions = {
            name: version for name, version in versions.items() if name in include_set
        }
    if exclude_set:
        versions = {k: v for k, v in versions.items() if k not in exclude_set}

    return versions


def _get_toml_and_script_paths(paths: list[Path]) -> tuple[list[Path], list[Path]]:
    tomls: list[Path] = []
    scripts: list[Path] = []

    for path in paths:
        suffix = path.suffix

        if suffix == ".toml":
            tomls.append(path)
        elif suffix == ".py":
            scripts.append(path)
        else:
            logger.info("ignoring path %s", path)
    return tomls, scripts


def _process_paths(paths: list[Path], replacer: Callable[[str], str]) -> None:
    for path in paths:
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
    opts = _get_options(argv)

    versions = _normalize_versions(
        versions=get_versions_from_requirements(opts.requirements),
        include=opts.include,
        exclude=opts.exclude,
    )
    if not versions:
        return False

    replacer = partial(REQUIREMENT_REGEX.sub, _factory_replacer(versions))
    tomls, scripts = _get_toml_and_script_paths(opts.paths)

    _process_paths(tomls, replacer)
    _process_paths(scripts, partial(_replace_pep723_section, replacer))

    return False


if __name__ == "__main__":
    raise SystemExit(main())
