from __future__ import annotations

from textwrap import dedent
from typing import TYPE_CHECKING

import pytest

from sync_pre_commit_hooks.sync_pre_commit_language_version import main

# pyrefly: ignore [missing-import]
from ._utils import create_config_file

if TYPE_CHECKING:
    from collections.abc import Sequence
    from pathlib import Path


@pytest.mark.parametrize(
    ("options", "pre_commit_str", "language_version_file_str", "expected", "code"),
    [
        pytest.param(
            ["--hook=mypy", "--language-version=3.12"],
            dedent("""\
repos:
  - repo: https://github.com/pre-commit/mirrors-mypy
    rev: v1.19.0
    hooks:
      - id: mypy
            """),
            None,
            dedent("""\
repos:
  - repo: https://github.com/pre-commit/mirrors-mypy
    rev: v1.19.0
    hooks:
      - id: mypy
            """),
            0,
            id="no_op",
        ),
        pytest.param(
            ["--hook=mypy", "--language-version=3.12"],
            dedent("""\
repos:
  - repo: https://github.com/pre-commit/mirrors-mypy
    rev: v1.19.0
    hooks:
      - id: mypy
        language_version: "3.12"
            """),
            None,
            dedent("""\
repos:
  - repo: https://github.com/pre-commit/mirrors-mypy
    rev: v1.19.0
    hooks:
      - id: mypy
        language_version: "3.12"
            """),
            0,
            id="no_op with version",
        ),
        pytest.param(
            ["--hook=mypy", "--language-version-file=.python-version"],
            dedent("""\
repos:
  - repo: https://github.com/pre-commit/mirrors-mypy
    rev: v1.19.0
    hooks:
      - id: mypy
        language_version: "3.12"
  - repo: https://github.com/scientific-python/cookie
    rev: 2025.11.10
    hooks:
      - id: sp-repo-review
        language_version: "3.12"
            """),
            "3.13",
            dedent("""\
repos:
  - repo: https://github.com/pre-commit/mirrors-mypy
    rev: v1.19.0
    hooks:
      - id: mypy
        language_version: "3.13"
  - repo: https://github.com/scientific-python/cookie
    rev: 2025.11.10
    hooks:
      - id: sp-repo-review
        language_version: "3.12"
            """),
            1,
            id="update version",
        ),
        pytest.param(
            [
                "--hook=mypy",
                "--language-version=3.14",
                "--language-version-file=.python-version",
            ],
            dedent("""\
repos:
  - repo: https://github.com/pre-commit/mirrors-mypy
    rev: v1.19.0
    hooks:
      - id: mypy
        language_version: "3.12"
            """),
            "3.13",
            dedent("""\
repos:
  - repo: https://github.com/pre-commit/mirrors-mypy
    rev: v1.19.0
    hooks:
      - id: mypy
        language_version: "3.14"
            """),
            1,
            id="update version",
        ),
    ],
)
def test_main(
    example_path: Path,
    options: Sequence[str],
    pre_commit_str: str,
    language_version_file_str: str | None,
    expected: str,
    code: int,
) -> None:
    pre_commit_config = create_config_file(example_path, pre_commit_str)

    if language_version_file_str is not None:
        _ = create_config_file(
            example_path, language_version_file_str, name=".python-version"
        )

    assert main(options) == code

    assert pre_commit_config.read_text() == expected
