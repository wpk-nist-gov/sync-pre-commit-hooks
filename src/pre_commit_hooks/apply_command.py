"""Apply command that works on single file to multiple files."""

from __future__ import annotations

import shlex
import subprocess
from argparse import ArgumentParser
from pathlib import Path
from typing import TYPE_CHECKING

from ._logging import get_logger

logger = get_logger("apply-command")

if TYPE_CHECKING:
    from collections.abc import Sequence


def _apply_command(command: str, extras: Sequence[str], path: Path) -> int:
    cmd = (*shlex.split(command), *extras, str(path))
    logger.info("%s", shlex.join(cmd))
    code = subprocess.call(cmd)
    logger.info("return code: %s", code)
    return code


def main(argv: Sequence[str] | None = None) -> int:
    """Main functionality"""
    parser = ArgumentParser()
    parser.add_argument(
        "command",
        help="""
        Command to run. Extra arguments to ``command`` will be parsed as well.
        Note that ``command`` will be parsed with ``shlex.split``. So, if you
        need to pass complex arguments, you should wrap ``command`` and these
        arguments in a single string. For example, to run ``command --option
        a`` over ``file1`` and ``file2``, you should use ``apply-command
        "command --option a" file1 file2``
        """,
    )
    parser.add_argument(
        dest="paths",
        nargs="+",
        type=Path,
        help="Files to apply ``command`` to.",
    )
    options, extras = parser.parse_known_args(argv)

    return_code = 0
    for path in options.paths:
        return_code += _apply_command(options.command, extras, path)
    return return_code


if __name__ == "__main__":
    raise SystemExit(main())
