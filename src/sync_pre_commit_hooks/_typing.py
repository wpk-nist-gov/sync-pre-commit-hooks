# pylint: disable=missing-class-docstring
from __future__ import annotations

from typing import TYPE_CHECKING, NewType, TypedDict

if TYPE_CHECKING:
    from packaging.requirements import Requirement

    from ._typing_compat import Required


class PreCommitHooksType(TypedDict, total=False):
    id: Required[str]
    alias: str
    name: str
    args: list[str]
    additional_dependencies: list[str]
    stages: list[str]
    language_version: str
    exclude: str
    exclude_types: list[str]


class PreCommitRepoType(TypedDict, total=True):
    repo: str
    rev: str
    hooks: list[PreCommitHooksType]


class PreCommitConfigType(
    TypedDict,
):
    repos: list[PreCommitRepoType]


NormalizedRequirement = NewType("NormalizedRequirement", "Requirement")
