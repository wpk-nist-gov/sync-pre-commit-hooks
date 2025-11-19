# ruff: noqa: ARG001, PLC2701

from __future__ import annotations

import os
from contextlib import nullcontext
from pathlib import Path
from textwrap import dedent
from typing import TYPE_CHECKING

import pytest

from pre_commit_hooks.sync_uv_dependency_groups_min_python import (
    _get_config_file,
    _get_python_version,
)

if TYPE_CHECKING:
    from collections.abc import Iterator
    from typing import Any


@pytest.fixture
def old_data() -> str:
    return dedent("""\
    dev.requires-python = ">=3.10"
    docs = { requires-python = ">=3.10" }
    """)


@pytest.fixture
def uv_toml(tmp_path: Path, old_data: str) -> Path:
    data = f"[dependency-groups]\n{old_data}"

    path = tmp_path / "uv.toml"
    path.write_text(data)

    return path


@pytest.fixture
def pyproject_toml(tmp_path: Path, old_data: str) -> Path:
    data = f"[tool.uv.dependency-groups]\n{old_data}"

    path = tmp_path / "pyproject.toml"
    path.write_text(data)

    return path


@pytest.fixture
def example_path(tmp_path: Path) -> Iterator[Path]:
    old_cwd = Path.cwd()
    os.chdir(tmp_path)
    yield tmp_path
    os.chdir(old_cwd)


def test_fixtures(tmp_path: Path, uv_toml: Path, pyproject_toml: Path) -> None:
    assert tmp_path / "uv.toml" == uv_toml
    assert tmp_path / "pyproject.toml" == pyproject_toml

    assert uv_toml.exists()
    assert pyproject_toml.exists()

    assert uv_toml.read_text(encoding="utf-8") == dedent("""\
    [dependency-groups]
    dev.requires-python = ">=3.10"
    docs = { requires-python = ">=3.10" }
    """)

    assert pyproject_toml.read_text(encoding="utf-8") == dedent("""\
    [tool.uv.dependency-groups]
    dev.requires-python = ">=3.10"
    docs = { requires-python = ">=3.10" }
    """)


def test__get_config_file_uv_toml_default(example_path: Path, uv_toml: Path) -> None:
    assert _get_config_file(None).resolve() == uv_toml.resolve()
    assert (
        _get_config_file(Path("pyproject.toml")).resolve()
        == example_path / "pyproject.toml"
    )


def test__get_config_file_pyproject_toml_default(
    example_path: Path, pyproject_toml: Path
) -> None:
    assert _get_config_file(None).resolve() == pyproject_toml.resolve()
    assert _get_config_file(Path("uv.toml")).resolve() == example_path / "uv.toml"


def test__get_config_file_uv_toml_and_pyproject_toml_default(
    example_path: Path, uv_toml: Path, pyproject_toml: Path
) -> None:
    assert _get_config_file(None).resolve() == uv_toml.resolve()
    assert (
        _get_config_file(Path("pyproject.toml")).resolve() == pyproject_toml.resolve()
    )


@pytest.mark.parametrize(
    ("python_version", "python_version_file", "create_file", "expected"),
    [
        ("3.13", ".python-version", False, nullcontext("3.13")),
        ("3.13", ".python-version", True, nullcontext("3.13")),
        (None, ".python-version", False, pytest.raises(FileNotFoundError)),
        (None, ".python-version", True, nullcontext("3.8")),
    ],
)
def test__get_python_version(
    example_path: Path,
    python_version: str | None,
    python_version_file: str,
    create_file: bool,
    expected: Any,
) -> None:
    if create_file:
        Path(python_version_file).write_text("3.8", encoding="utf-8")

    with expected as e:
        out = _get_python_version(python_version, python_version_file)
        assert out == e
