"""
Update minimum value for python-version in `tool.uv.dependency-groups` table.

By default, set value to `>=python_version` with `python_version` taken from `.python-version` file.
"""

from __future__ import annotations

from argparse import ArgumentParser
from pathlib import Path
from typing import TYPE_CHECKING

from packaging.specifiers import Specifier

from ._logging import get_logger

if TYPE_CHECKING:
    from collections.abc import Sequence
    from typing import Any


logger = get_logger("sync-uv-dependency-groups")


def _get_config_file(config_file: Path | None) -> Path:
    if config_file is not None:
        return config_file

    if (uv_toml := Path("uv.toml")).exists():
        return uv_toml

    if (pyproject := Path("pyproject.toml")).exists():
        return pyproject

    msg = "Couldn't find uv.toml or pyproject.toml"
    raise FileNotFoundError(msg)


def _get_python_version(
    python_version: str | None,
    python_version_file: str,
) -> str:
    if python_version is not None:
        logger.info("Using python_version %s", python_version)
        return python_version

    python_version = Path(python_version_file).read_text(encoding="utf-8").strip()
    logger.info(
        "Using python_version %s read from %s", python_version, python_version_file
    )
    return python_version


def _update_spec(requires_python: str, python_version: str) -> str:
    spec = Specifier(requires_python)
    return str(Specifier(f"{spec.operator}{python_version}"))


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
        logger.info("No dependency-group table found")
        return

    for k, v in dependency_groups.items():
        if "requires-python" in v:
            requires_python = v["requires-python"]
            if requires_python != (
                new_spec := _update_spec(requires_python, python_version)
            ):
                logger.info("update %s from %s to %s", k, requires_python, new_spec)
                v["requires-python"] = new_spec

    toml.write(data)


def main(args: Sequence[str] | None = None) -> int:
    """Main program."""
    parser = ArgumentParser(description=__doc__)
    parser.add_argument(
        "--python-version",
        "-p",
        help="Minimum python version.  Overrides ``--python-version-file``.",
        default=None,
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
