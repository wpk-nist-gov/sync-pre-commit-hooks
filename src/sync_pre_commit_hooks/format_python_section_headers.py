"""
Format section headers in python.

Format trailing dashes ``# * a thing ----``
"""

from __future__ import annotations

import re
from argparse import ArgumentParser
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from ._logging import get_logger

if TYPE_CHECKING:
    from collections.abc import Sequence

logger = get_logger("format-python-headers")

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
@dataclass
class _Options:
    """Options class"""

    line_length: int
    dry_run: bool
    paths: list[Path]


def _get_options(argv: Sequence[str] | None = None) -> _Options:
    parser = ArgumentParser(description=__doc__)

    _ = parser.add_argument(
        "--line-length",
        type=int,
        default=88,
        help="Fill to location",
    )
    _ = parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Perform dry run",
    )
    _ = parser.add_argument("paths", type=Path, nargs="+", help="file paths to edit")

    options = parser.parse_args(argv)
    return _Options(**vars(options))


def main(argv: Sequence[str] | None = None) -> bool:
    """Main function"""
    options = _get_options(argv)

    errors = False
    for path in options.paths:
        errors |= _maybe_update_path(
            path, line_length=options.line_length, dry_run=options.dry_run
        )
    return errors


if __name__ == "__main__":
    raise SystemExit(main())
