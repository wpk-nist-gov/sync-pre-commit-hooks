from __future__ import annotations

from typing import Required, TypedDict


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
