"""Sync `uv-build` in `pyproject.toml:build-system.requires` with uv hook in .pre-commit-config.yaml"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from packaging.requirements import Requirement
from packaging.utils import canonicalize_name
from packaging.version import Version

from ._logging import get_logger
from ._utils import (
    add_pre_commit_config_argument,
    get_version_from_lastversion,
    pre_commit_config_load,
)

if TYPE_CHECKING:
    from collections.abc import Sequence
    from typing import Any


logger = get_logger("sync-uv-build-deps")


def _get_options(argv: Sequence[str] | None = None) -> tuple[Path, list[Path], bool]:
    from argparse import ArgumentParser

    parser = ArgumentParser(description=__doc__)

    parser = add_pre_commit_config_argument(parser)

    _ = parser.add_argument(
        "--lastversion",
        action="store_true",
        help="""
        Use `lastversion` to get latest version of uv instead of syncing with
        uv-pre-commit version from .pre-commit-config.yaml.
        """,
    )

    _ = parser.add_argument(
        "paths",
        type=Path,
        nargs="*",
        help="""
        Paths to consider. Path ``--pre-commit-config`` is ignored.
        """,
    )

    options = parser.parse_args(argv)

    pre_commit_config_resolved = options.pre_commit_config.resolve()

    paths: list[Path] = []
    for path in options.paths:
        if path.resolve() == pre_commit_config_resolved:
            logger.info("ignore path %s", path)
        else:
            paths.append(path)

    return options.pre_commit_config, paths, options.lastversion


def _get_uv_version(pre_commit_config: Path) -> Version:
    loaded, _ = pre_commit_config_load(pre_commit_config)
    for repo in loaded["repos"]:
        if repo["repo"].endswith("uv-pre-commit"):
            return Version(repo["rev"])

    msg = "No repo found for uv"
    raise ValueError(msg)


def _get_uv_build_dep(uv_version: Version) -> str:
    release = list(uv_version.release)
    release[1] += 1
    release[2] = 0

    version_upper = ".".join(str(x) for x in release)
    return f"uv-build>={uv_version},<{version_upper}"


def _update_pyproject(pyproject: Path, uv_build_dep: str) -> bool:
    from tomlkit.toml_file import TOMLFile

    toml = TOMLFile(pyproject)

    data: Any = toml.read()

    # NOTE: modify in place to preserve formatting.
    if data.get("build-system", {}).get("requires") is None:
        msg = "No build system found."
        raise KeyError(msg)

    requires: list[str] = data["build-system"]["requires"]
    for i, dep in enumerate(requires):
        name = canonicalize_name(Requirement(dep).name)
        if name != "uv-build":
            msg = "Not using uv-build"
            raise ValueError(msg)
        if name == "uv-build" and dep != uv_build_dep:
            logger.info("update %s to %s", dep, uv_build_dep)
            index = i
            break
    else:
        index = -1

    if index >= 0:
        requires[index] = uv_build_dep
        toml.write(data)
        return True
    return False


def main(argv: Sequence[str] | None = None) -> bool:
    """Main function."""
    pre_commit_config, paths, use_lastversion = _get_options(argv)

    uv_version = (
        Version(get_version_from_lastversion("uv"))
        if use_lastversion
        else _get_uv_version(pre_commit_config)
    )

    logger.info("pre_commit_config: %s", pre_commit_config)
    logger.info("uv_version: %s", uv_version)
    logger.info("uv-build: %s", _get_uv_build_dep(uv_version))

    error = False
    uv_build_deps = _get_uv_build_dep(uv_version)

    for pyproject in paths:
        logger.info("pyproject: %s", pyproject)
        error |= _update_pyproject(pyproject, uv_build_deps)
    return error


if __name__ == "__main__":
    raise SystemExit(main())
