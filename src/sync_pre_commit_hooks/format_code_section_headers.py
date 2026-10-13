"""
Format section headers in code files.

Format trailing dashes for lines like ``# * a thing ----`` to specified
line-length.

Line lengths are deterimend from, in order, ``--ext-line-length``, read from
``.editorconfig`` (if do not have ``--no-config`` option), and finally from
``--line-length`` option.
"""

from __future__ import annotations

import re
from argparse import ArgumentParser, RawDescriptionHelpFormatter
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

from ._logging import get_logger

if TYPE_CHECKING:
    from argparse import Namespace
    from collections.abc import Sequence


logger = get_logger("format-code-section-headers")

# * Replace ----------------------------------------------------------------------------
PATTERN = r"""
^(?P<prefix>
    \s*[#]
)
\s*
(?P<type>
    \s*[*]*
)
\s*
(?P<title>
    .*?
)
\w*
[-]+$
"""


HEADER_REGEX = re.compile(
    r"""
    ^(?P<prefix>
        [^\S\r\n]*[#]
    )
    \s*
    (?P<type>
        \s*[*]+
    )
    \s*
    (?P<title>
        .*?
    )
    \w*
    [-]+$
    """,
    flags=re.MULTILINE | re.VERBOSE,
)


class _Replacer:
    """Class to perform re.sub and flag changes."""

    def __init__(self, line_length: int = 88) -> None:
        self.line_length = line_length
        self.updated = False

    def __call__(self, obj: re.Match[str]) -> str:
        prefix = obj.group("prefix")
        type_ = obj.group("type").strip()
        title = obj.group("title").strip()

        name = f"{prefix} {type_} {title}"
        if len(name) < self.line_length and (
            out := f"{name} ".ljust(self.line_length, "-")
        ) != obj.group(0):
            self.updated = True
            return out
        return obj.group(0)


def _maybe_update_contents(contents: str, line_length: int) -> tuple[str, bool]:
    replacer = _Replacer(line_length)
    out = HEADER_REGEX.sub(replacer, contents)
    return out, replacer.updated


def _maybe_update_path(path: Path, line_length: int, dry_run: bool = False) -> bool:
    out, updated = _maybe_update_contents(path.read_text(encoding="utf-8"), line_length)
    logger.info("update %s" if updated else "no change %s", path)

    if not dry_run and updated:
        _ = path.write_text(out, encoding="utf-8")
    return updated


# * get args ---------------------------------------------------------------------------
def _get_extension_line_length_mapping(
    extension_line_lengths: Sequence[str],
) -> dict[str, int]:
    out: dict[str, int] = {}
    for x in extension_line_lengths:
        ext, sep, line_length = x.partition(":")
        if sep != ":":
            msg = f"Missing separator ':' in extension to line-length string {x}"
            raise ValueError(msg)

        ext = ext.strip()
        if not ext.startswith("."):
            ext = f".{ext}"
        out[ext] = int(line_length)
    return out


@dataclass
class _Options:
    """Options class"""

    default_line_length: int = 88
    dry_run: bool = False
    paths: list[Path] = field(default_factory=list)
    no_config: bool = False
    extension_line_length_mapping: dict[str, int] = field(default_factory=dict)

    def get_line_length(self, path: Path) -> int:

        if (
            line_length := self.extension_line_length_mapping.get(path.suffix)
        ) is not None:
            return line_length

        if not self.no_config:
            from editorconfig import EditorConfigError, get_properties

            try:  # pylint: disable=too-many-try-statements
                if (
                    s := get_properties(str(path.resolve())).get("max_line_length")
                ) is not None:
                    return int(s)
            except EditorConfigError:  # pragma: no cover
                pass

        return self.default_line_length

    @classmethod
    def from_namespace(cls, options: Namespace) -> _Options:
        return cls(
            default_line_length=options.default_line_length,
            dry_run=options.dry_run,
            paths=options.paths,
            no_config=options.no_config,
            extension_line_length_mapping=_get_extension_line_length_mapping(
                options.extension_line_lengths
            ),
        )

    @classmethod
    def from_args(cls, argv: Sequence[str] | None = None) -> _Options:
        parser = ArgumentParser(
            description=__doc__,
            formatter_class=RawDescriptionHelpFormatter,
        )

        _ = parser.add_argument(
            "--line-length",
            dest="default_line_length",
            type=int,
            default=88,
            help="Default line length to fill headers to",
        )
        _ = parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Perform dry run",
        )
        _ = parser.add_argument(
            "--ext-line-length",
            "-e",
            dest="extension_line_lengths",
            type=str,
            action="append",
            default=[],
            help="""
            Colon separated extension to line-length mapping
            (``{extension}:{line-length}``). For example, to apply ``line_length=80`` to
            only yaml files, use ``--ext-line-length '.yaml:80'. Note that the ``"."`` in
            extension is optional.
            """,
        )
        _ = parser.add_argument(
            "--no-config",
            action="store_true",
            help="If True, ignore .editorconfig",
        )

        _ = parser.add_argument(
            "paths", type=Path, nargs="+", help="file paths to edit"
        )

        options = parser.parse_args(argv)
        return cls.from_namespace(options)


def main(argv: Sequence[str] | None = None) -> bool:
    """Main function"""
    options = _Options.from_args(argv)

    errors = False
    for path in options.paths:
        errors |= _maybe_update_path(
            path, line_length=options.get_line_length(path), dry_run=options.dry_run
        )
    return errors


if __name__ == "__main__":
    raise SystemExit(main())
