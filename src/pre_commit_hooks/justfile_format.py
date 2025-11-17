"""Process justfile formatting"""

from __future__ import annotations

import sys
from argparse import ArgumentParser
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Sequence


def _format_file(path: Path, extras: Sequence[str]) -> None:
    from subprocess import check_call

    check_call(
        [
            "just",
            "--fmt",
            "--unstable",
            *extras,
            "--justfile",
            str(path),
        ]
    )


def main() -> int:
    """Main functionality"""
    parser = ArgumentParser()
    parser.add_argument(
        "paths",
        type=Path,
        nargs="+",
    )

    options, extras = parser.parse_known_args()

    for path in options.paths:
        _format_file(path, extras)
    return 0


if __name__ == "__main__":
    sys.exit(main())
