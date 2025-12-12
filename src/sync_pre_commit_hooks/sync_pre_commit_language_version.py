"""Sync ``language_version`` with specified version or version file."""

from __future__ import annotations

from argparse import ArgumentParser
from pathlib import Path
from typing import TYPE_CHECKING

from ._logging import get_logger
from ._utils import (
    add_pre_commit_config_argument,
    add_yaml_arguments,
    get_language_version,
    pre_commit_config_load,
    pre_commit_config_repo_hook_iter,
)

if TYPE_CHECKING:
    from collections.abc import Container, Sequence
    from typing import Any

logger = get_logger("sync-pre-commit-language-version")


def _get_options(argv: Sequence[str] | None = None) -> dict[str, Any]:
    """Get parser"""
    parser = ArgumentParser(description=__doc__)
    parser = add_yaml_arguments(parser)
    parser = add_pre_commit_config_argument(parser)
    _ = parser.add_argument(
        "-l",
        "--language-version",
        type=str,
        default=None,
        help="""
        Update ``language_version`` to this value. Overrides
        ``--language-version-file``. Note that ``hook`` must already have key
        ``language_version`` for this to take effect.
        """,
    )
    _ = parser.add_argument(
        "-f",
        "--language-version-file",
        type=Path,
        default=None,
        help="""
        Update ``language_version`` to value read from file. For example,
        ``--language-version-file=".python-version"``. Note that `hook` must
        already have key ``language_version`` for this to take effect.
        """,
    )
    _ = parser.add_argument(
        "hook_ids",
        nargs="+",
        type=str,
        help="""
        Hook id's to update ``language_version`` value.
        """,
    )

    options = parser.parse_args(argv)

    kws = vars(options)
    kws["language_version"] = get_language_version(
        kws.pop("language_version"), kws.pop("language_version_file"), logger
    )

    return kws


def _update_yaml_file(
    config: Path,
    hook_ids: Container[str],
    language_version: str,
    yaml_mapping: int = 2,
    yaml_sequence: int = 4,
    yaml_offset: int = 2,
) -> int:
    loaded, yaml = pre_commit_config_load(
        config, mapping=yaml_mapping, sequence=yaml_sequence, offset=yaml_offset
    )

    updated = False
    for _, hook in pre_commit_config_repo_hook_iter(loaded, include_hook_ids=hook_ids):
        if (
            language_version_current := hook.get("language_version")
        ) is not None and language_version != language_version_current:
            logger.info(
                "Updating hook %s language_version from %s to %s",
                hook["id"],
                language_version_current,
                language_version,
            )
            hook["language_version"] = language_version
            updated = True

    if updated:
        logger.info("Updating %s", config)
        yaml.dump(loaded, config)  # pyright: ignore[reportUnknownMemberType]
        return 1

    return 0


def main(argv: Sequence[str] | None = None) -> int:
    """Main function"""
    options = _get_options(argv)
    return _update_yaml_file(**options)


if __name__ == "__main__":
    raise SystemExit(main())
