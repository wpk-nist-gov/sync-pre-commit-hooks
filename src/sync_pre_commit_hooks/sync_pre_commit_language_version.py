"""Sync ``language_version`` with specified version or version file."""

from __future__ import annotations

from argparse import ArgumentParser
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

from ruamel.yaml.scalarstring import DoubleQuotedScalarString

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


@dataclass
class _Options:
    """Option class"""

    pre_commit_config: Path
    language_version: str

    yaml_mapping: int = 2
    yaml_sequence: int = 4
    yaml_offset: int = 2

    language_name: str | None = None
    hooks: list[str] = field(default_factory=list)
    force: bool = False

    @classmethod
    def from_params(
        cls,
        *,
        language_version: str | None,
        language_version_file: Path | None,
        language_name: str | None = None,
        hooks: Sequence[str] = (),
        force: bool = False,
        **kwargs: Any,
    ) -> _Options:

        return cls(
            language_version=get_language_version(
                language_version, language_version_file, logger
            ),
            language_name=language_name,
            hooks=list(hooks),
            force=force,
            **kwargs,
        )


def _get_options(argv: Sequence[str] | None = None) -> _Options:
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
        "--hook",
        dest="hooks",
        action="append",
        default=[],
        type=str,
        help="""
        Hook id's to update ``language_version`` value.
        """,
    )
    _ = parser.add_argument(
        "--force",
        action="store_true",
        help="""
        Pass to force setting ``language_version``, or ``default_language_version``
        fields. Default is to only update if these fields already exist.
        """,
    )

    _ = parser.add_argument(
        "--language-name",
        dest="language_name",
        type=str,
        help="""
        Language name to update under ``default_language_version``. For example, passing
        ``--language-version=3.14 --default-language-name=python`` sets
        ``default_language_version.python=3.14`` in ``.pre-commit-config.yaml``.
        """,
    )

    options = parser.parse_args(argv)

    return _Options.from_params(**vars(options))


def _update_yaml_file(  # ruff: ignore[complex-structure]
    pre_commit_config: Path,
    hooks: Container[str],
    language_version: str,
    yaml_mapping: int = 2,
    yaml_sequence: int = 4,
    yaml_offset: int = 2,
    language_name: str | None = None,
    force: bool = False,
) -> int:
    def _maybe_update(language_version_current: str | None) -> bool:
        if language_version_current is None:
            # no language version field.  Create it if force
            return force
        return language_version_current != language_version

    def _do_update(
        mapping: Any, key: str, language_version_current: str | None
    ) -> None:
        if language_version_current is None:
            # force
            logger.info(
                "Force updating default_language_version %s to %s",
                language_name,
                language_version,
            )
            mapping[key] = DoubleQuotedScalarString(language_version)
        else:
            # update
            logger.info(
                "Updating default_language_version %s from %s to %s",
                language_name,
                language_version_current,
                language_version,
            )
            mapping[key] = language_version

    loaded, yaml = pre_commit_config_load(
        pre_commit_config,
        mapping=yaml_mapping,
        sequence=yaml_sequence,
        offset=yaml_offset,
    )

    updated = False

    # maybe update default_language_version.language_name ?
    if language_name is not None:
        language_version_current = loaded.get("default_language_version", {}).get(
            language_name
        )
        if _maybe_update(language_version_current):
            updated = True
            if "default_language_version" not in loaded:
                loaded.insert(0, "default_language_version", {})  # type: ignore[attr-defined] # pyright: ignore[reportUnknownMemberType, reportAttributeAccessIssue]  # ty: ignore[unresolved-attribute]  # pyrefly: ignore [missing-attribute]
            assert "default_language_version" in loaded  # ruff: ignore[assert]
            _do_update(
                loaded["default_language_version"],
                language_name,
                language_version_current,
            )

    # update hooks
    for _, hook in pre_commit_config_repo_hook_iter(loaded, include_hook_ids=hooks):
        language_version_current = hook.get("language_version")
        if _maybe_update(language_version_current):
            updated = True
            _do_update(hook, "language_version", language_version_current)

    if updated:
        logger.info("Updating %s", pre_commit_config)
        yaml.dump(loaded, pre_commit_config)  # pyright: ignore[reportUnknownMemberType]
        return 1

    return 0


def main(argv: Sequence[str] | None = None) -> int:
    """Main function"""
    options = _get_options(argv)
    return _update_yaml_file(**asdict(options))


if __name__ == "__main__":
    raise SystemExit(main())
