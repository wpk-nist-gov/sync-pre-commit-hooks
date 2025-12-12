from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, cast

if TYPE_CHECKING:
    from argparse import ArgumentParser
    from collections.abc import (
        Callable,
        Container,
        Iterable,
        Iterator,
        Mapping,
        Sequence,
    )
    from logging import Logger
    from typing import Any

    from ruamel.yaml import YAML

    from ._typing import PreCommitConfigType, PreCommitHooksType, PreCommitRepoType


def get_in(
    keys: Sequence[Any],
    nested_dict: Mapping[Any, Any],
    default: Any = None,
    factory: Callable[[], Any] | None = None,
) -> Any:
    """
    >>> foo = {"a": {"b": {"c": 1}}}
    >>> get_in(["a", "b"], foo)
    {'c': 1}

    """
    import operator
    from functools import reduce

    try:
        return reduce(  # pyrefly: ignore[no-matching-overload] # ty: ignore[no-matching-overload]
            operator.getitem,  # pyrefly: ignore[bad-argument-type]  # ty: ignore[invalid-argument-type]
            keys,
            nested_dict,
        )
    except (KeyError, IndexError, TypeError):
        if factory is not None:
            return factory()
        return default


_ARGUMENT_HELP_TEMPLATE = (
    "The `{}` argument to the YAML dumper. "
    "See https://yaml.readthedocs.io/en/latest/detail/"
    "#indentation-of-block-sequences"
)


def add_yaml_arguments(parser: ArgumentParser) -> ArgumentParser:
    # yaml defaults are my preference
    _ = parser.add_argument(
        "--yaml-mapping",
        type=int,
        default=2,
        help=_ARGUMENT_HELP_TEMPLATE.format("mapping"),
    )
    _ = parser.add_argument(
        "--yaml-sequence",
        type=int,
        default=4,
        help=_ARGUMENT_HELP_TEMPLATE.format("sequence"),
    )
    _ = parser.add_argument(
        "--yaml-offset",
        type=int,
        default=2,
        help=_ARGUMENT_HELP_TEMPLATE.format("offset"),
    )

    return parser


def add_pre_commit_config_argument(parser: ArgumentParser) -> ArgumentParser:
    _ = parser.add_argument(
        "--config",
        type=Path,
        default=".pre-commit-config.yaml",
        help="pre-commit config file (Default '.pre-commit-config.yaml')",
    )

    return parser


def get_language_version(
    version: str | None,
    version_file: str | None,
    logger: Logger | None = None,
) -> str:
    if logger is None:
        from ._logging import get_logger

        logger = get_logger("_utils")

    if version is not None:
        logger.info("Using version %s", version)
        return version

    if version_file is None:
        msg = "Must specify version or version_file"
        raise ValueError(msg)

    version = Path(version_file).read_text(encoding="utf-8").strip()
    logger.info("Using version %s read from %s", version, version_file)
    return version


def pre_commit_config_load(
    path: Path,
    mapping: int = 2,
    sequence: int = 4,
    offset: int = 2,
) -> tuple[PreCommitConfigType, YAML]:
    from ruamel.yaml import YAML

    yaml = YAML()
    yaml.preserve_quotes = True
    yaml.indent(mapping, sequence, offset)  # pyright: ignore[reportUnknownMemberType]

    return cast("PreCommitConfigType", yaml.load(path)), yaml  # pyright: ignore[reportUnknownMemberType]


def pre_commit_config_repo_hook_iter(
    config: PreCommitConfigType,
    include_hook_ids: str | Container[str] | None = None,
    exclude_repos: str | Container[str] | None = None,
) -> Iterator[tuple[PreCommitRepoType, PreCommitHooksType]]:
    def _str_to_set(x: str | Container[str]) -> Container[str]:
        if isinstance(x, str):
            return {x}
        return x

    repo_iter: Iterable[PreCommitRepoType] = iter(config["repos"])
    if exclude_repos:
        repo_iter = (
            repo for repo in repo_iter if repo["repo"] not in _str_to_set(exclude_repos)
        )

    repo_hook_iter = ((repo, hook) for repo in repo_iter for hook in repo["hooks"])
    if include_hook_ids:
        return (
            (repo, hook)
            for repo, hook in repo_hook_iter
            if hook["id"] in _str_to_set(include_hook_ids)
        )
    return repo_hook_iter
