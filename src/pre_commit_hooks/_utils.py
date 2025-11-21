from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from argparse import ArgumentParser
    from collections.abc import Callable, Mapping, Sequence
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
