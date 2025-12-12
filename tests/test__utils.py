from __future__ import annotations

from contextlib import nullcontext
from pathlib import Path
from typing import Any

import pytest

from sync_pre_commit_hooks._utils import get_language_version  # noqa: PLC2701


@pytest.mark.parametrize(
    ("python_version", "python_version_file", "create_file", "expected"),
    [
        ("3.13", ".python-version", False, nullcontext("3.13")),
        ("3.13", ".python-version", True, nullcontext("3.13")),
        (None, ".python-version", False, pytest.raises(FileNotFoundError)),
        (None, ".python-version", True, nullcontext("3.8")),
        (
            None,
            None,
            False,
            pytest.raises(ValueError, match=r"Must specify version .*"),
        ),
    ],
)
def test_get_language_version(
    example_path: Path,  # noqa: ARG001
    python_version: str | None,
    python_version_file: str,
    create_file: bool,
    expected: Any,
) -> None:
    if create_file:
        Path(python_version_file).write_text("3.8", encoding="utf-8")

    with expected as e:
        out = get_language_version(python_version, python_version_file)
        assert out == e
