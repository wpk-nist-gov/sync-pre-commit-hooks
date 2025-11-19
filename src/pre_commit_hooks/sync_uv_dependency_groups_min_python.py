"""
Update minimum value for python-version in `tool.uv.dependency-groups` table.

By default, set value to `>=python_version` with `python_version` taken from `.python-version` file.
"""

from __future__ import annotations

import logging
from argparse import ArgumentParser
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Sequence
    from typing import Any


FORMAT = "[%(name)s - %(levelname)s] %(message)s"
logging.basicConfig(level=logging.INFO, format=FORMAT)
logger = logging.getLogger("sync-uv-dependency-groups-min-python")


def _get_config_file(config_file: Path | None) -> Path:
    if config_file is not None:
        return config_file

    if (uv_toml := Path("uv.toml")).exists():
        return uv_toml

    if (pyproject := Path("pyproject.toml")).exists():
        return pyproject

    msg = "Couldn't find uv.toml or pyproject.toml"
    raise ValueError(msg)


def _get_python_version(
    python_version: str | None,
    python_version_file: str,
) -> str:
    if python_version is not None:
        return python_version

    return Path(python_version_file).read_text(encoding="utf-8").strip()


def _process_file(
    config_file: Path,
    python_version: str,
) -> None:
    from tomlkit.toml_file import TOMLFile

    logger.info("Processing file %s", config_file)

    toml = TOMLFile(config_file)

    data: Any = toml.read()

    dependency_groups: dict[str, dict[str, Any]] | None = (
        data["tool"]["uv"] if config_file.name == "pyproject.toml" else data
    ).get("dependency-groups")

    if dependency_groups is None:
        return

    python_min_version = f">={python_version}"
    for k, v in dependency_groups.items():
        if "requires-python" in v and v["requires-python"] != python_min_version:
            logger.info("update %s to %s", k, python_min_version)
            v["requires-python"] = python_min_version

    toml.write(data)


def main(args: Sequence[str] | None = None) -> int:
    """Main program."""
    parser = ArgumentParser(description=__doc__)
    parser.add_argument(
        "--python-version", "-p", help="Minimum python version", default=None
    )
    parser.add_argument(
        "--python-version-file",
        "-f",
        default=".python-version",
        type=Path,
        help="Text file with python version",
    )
    parser.add_argument(
        "config_file",
        nargs="?",
        type=Path,
        help="""
        File containing dependency-groups table. Default is to look for `uv.toml` then `pyproject.toml`
        """,
    )
    options = parser.parse_args(args)
    _process_file(
        config_file=_get_config_file(options.config_file),
        python_version=_get_python_version(
            options.python_version, options.python_version_file
        ),
    )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
