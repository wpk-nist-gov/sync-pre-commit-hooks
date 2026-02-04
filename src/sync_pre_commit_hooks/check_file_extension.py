"""Exit with non zero status if file has specified extension"""

from __future__ import annotations

from argparse import ArgumentParser
from pathlib import Path
from typing import TYPE_CHECKING

from ._logging import get_logger

if TYPE_CHECKING:
    from collections.abc import Iterable, Sequence

logger = get_logger("exclude-extension")


def _check_extensions_have_dot(extensions: list[str]) -> list[str]:
    error = False
    for ext in extensions:
        if not ext.startswith("."):
            logger.info("%s must start with '.'", ext)
            error = True

    if error:
        msg = "Extensions must start with '.'"
        raise ValueError(msg)

    return extensions


def _has_excluded_extension(extensions: Sequence[str], paths: Iterable[Path]) -> bool:
    has_forbidden = False
    for path in paths:
        # check this way to handle possible excludes like `.tar.gz`
        name = path.name
        for ext in extensions:
            if name.endswith(ext):
                logger.info("%s has forbidden extension %s", path, ext)
                has_forbidden = True
    return has_forbidden


def _get_options(argv: Sequence[str] | None) -> tuple[list[str], list[Path]]:
    parser = ArgumentParser(description=__doc__)

    _ = parser.add_argument(
        "-e",
        "--ext",
        dest="extensions",
        action="append",
        default=[],
        help="""
        Extensions to exclude.  Should include `"."`.
        For example `--ext .rej --ext .bak ...`
        """,
    )
    _ = parser.add_argument(
        "paths",
        type=Path,
        nargs="+",
    )

    options = parser.parse_args(argv)

    extensions: list[str] = _check_extensions_have_dot(options.extensions)
    paths: list[Path] = options.paths
    return extensions, paths


def main(argv: Sequence[str] | None = None) -> int:
    """CLI"""
    extensions, paths = _get_options(argv)

    if _has_excluded_extension(extensions, paths):
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit
