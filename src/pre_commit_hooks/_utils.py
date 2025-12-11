from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from argparse import ArgumentParser
    from collections.abc import Callable, Mapping, Sequence
    from logging import Logger
    from typing import Any


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
    parser.add_argument(
        "--yaml-mapping",
        type=int,
        default=2,
        help=_ARGUMENT_HELP_TEMPLATE.format("mapping"),
    )
    parser.add_argument(
        "--yaml-sequence",
        type=int,
        default=4,
        help=_ARGUMENT_HELP_TEMPLATE.format("sequence"),
    )
    parser.add_argument(
        "--yaml-offset",
        type=int,
        default=2,
        help=_ARGUMENT_HELP_TEMPLATE.format("offset"),
    )

    return parser


def get_python_version(
    python_version: str | None,
    python_version_file: str | None,
    logger: Logger | None = None,
) -> str:
    if logger is None:
        from ._logging import get_logger

        logger = get_logger("_utils")

    if python_version is not None:
        logger.info("Using python_version %s", python_version)
        return python_version

    if python_version_file is None:
        msg = "Must specify python_version or python_version_file"
        raise ValueError(msg)

    python_version = Path(python_version_file).read_text(encoding="utf-8").strip()
    logger.info(
        "Using python_version %s read from %s", python_version, python_version_file
    )
    return python_version
