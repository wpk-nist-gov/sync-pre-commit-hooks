"""Sync `rev` version to current version"""

from __future__ import annotations

import logging
from argparse import ArgumentParser
from pathlib import Path
from typing import TYPE_CHECKING, cast

if TYPE_CHECKING:
    from collections.abc import Sequence


FORMAT = "[%(name)s - %(levelname)s] %(message)s"
logging.basicConfig(level=logging.INFO, format=FORMAT)
logger = logging.getLogger(__name__)


DEFAULT_REPO_URL = "https://github.com/wpk-nist-gov/sync-pre-commit-hooks"


def _get_current_package_version(config_file: Path) -> str:
    import tomllib

    with config_file.open("rb") as f:
        return cast("str", tomllib.load(f)["project"]["version"])


def _update_readme(
    rev_version: str,
    readme: Path,
    repo_url: str,
) -> tuple[bool, list[str]]:
    import re

    repo_patterm = re.compile(rf"\s+[-]\s+repo\:\s+{repo_url}")
    rev_pattern = re.compile(r"(\s*rev:\s*v).*")

    logger.info("Processing %s", readme)
    with readme.open(encoding="utf-8") as f:
        out: list[str] = []
        update = False
        for line in f:
            out.append(line)
            if repo_patterm.match(line):
                rev_line = next(f)
                new_line = rev_pattern.sub(rf"\g<1>{rev_version}", rev_line)
                out.append(new_line)
                if rev_line != new_line:
                    logger.info(
                        "replace %s with %s", rev_line.rstrip(), new_line.rstrip()
                    )
                    update = True

    return update, out


def main(argv: Sequence[str] | None = None) -> int:
    """CLI."""
    parser = ArgumentParser(description=__doc__)

    parser.add_argument(
        "paths", nargs="*", type=Path, help="files to update.  Defaults to 'README.md'"
    )
    parser.add_argument(
        "-c",
        "--config",
        type=Path,
        default="pyproject.toml",
        help="config file.  Defaults to 'pyproject.toml'",
    )
    parser.add_argument(
        "--repo",
        default=DEFAULT_REPO_URL,
        help=f"repo url.  Defaults to {DEFAULT_REPO_URL}",
    )

    options = parser.parse_args(argv)

    readmes: list[Path] = options.paths or [Path("README.md")]
    rev_version = _get_current_package_version(options.config)
    repo_url: str = options.repo

    for readme in readmes:
        update, lines = _update_readme(
            rev_version=rev_version, readme=readme, repo_url=repo_url
        )
        if update:
            logger.info("Updating file %s", readme)
            readme.write_text("".join(lines), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
