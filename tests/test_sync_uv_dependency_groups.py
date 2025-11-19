# ruff: noqa: ARG001, PLC2701

from __future__ import annotations

import os
from contextlib import nullcontext
from pathlib import Path
from textwrap import dedent
from typing import TYPE_CHECKING

import pytest

from pre_commit_hooks import sync_uv_dependency_groups
from pre_commit_hooks.sync_uv_dependency_groups import (
    _get_config_file,
    _get_python_version,
    _update_spec,
)

if TYPE_CHECKING:
    from collections.abc import Iterator
    from typing import Any


def get_data(pyproject: bool = True, python_version: str = "3.10") -> str:
    return dedent(f"""\
    [{"tool.uv." if pyproject else ""}dependency-groups]
    dev.requires-python = ">={python_version}"
    docs = {{ requires-python = ">={python_version}" }}
    """)


@pytest.fixture
def uv_toml(tmp_path: Path) -> Path:
    path = tmp_path / "uv.toml"
    path.write_text(get_data(False, "3.10"))

    return path


@pytest.fixture
def pyproject_toml(tmp_path: Path) -> Path:
    path = tmp_path / "pyproject.toml"
    path.write_text(get_data(True, "3.10"))

    return path


@pytest.fixture
def python_version_file(tmp_path: Path) -> Path:
    path = tmp_path / ".python-version"
    path.write_text("3.13", encoding="utf-8")
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

    assert uv_toml.read_text(encoding="utf-8") == get_data(False, "3.10")
    assert pyproject_toml.read_text(encoding="utf-8") == get_data(True, "3.10")


def test__get_config_file(example_path: Path) -> None:
    with pytest.raises(FileNotFoundError, match=r"Couldn't find uv.toml .*"):
        _ = _get_config_file(None)


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


@pytest.mark.parametrize(
    ("requires_python", "python_version", "expected"),
    [
        ("== 3.9", "3.10", "==3.10"),
        (">= 3.10 ", "3.10", ">=3.10"),
        (" ~= 3.8", "3.10", "~=3.10"),
    ],
)
def test__update_spec(requires_python: str, python_version: str, expected: str) -> None:
    assert _update_spec(requires_python, python_version) == expected


def test_main_uv_toml(
    example_path: Path, uv_toml: Path, pyproject_toml: Path, python_version_file: Path
) -> None:
    assert not sync_uv_dependency_groups.main([])
    assert uv_toml.read_text(encoding="utf-8") == get_data(False, "3.13")
    assert pyproject_toml.read_text(encoding="utf-8") == get_data(True, "3.10")


@pytest.mark.parametrize(
    ("data_in", "data_out"),
    [
        pytest.param(
            dedent("""\
            managed = true
            """),
            dedent("""\
            managed = true
            """),
            id="no dependency-groups",
        ),
        pytest.param(
            dedent("""\
            [dependency-groups]
            dev.requires-python = "==3.10"
            docs = {}
            """),
            dedent("""\
            [dependency-groups]
            dev.requires-python = "==3.13"
            docs = {}
            """),
            id="no requires-python",
        ),
        pytest.param(
            dedent("""\
            [dependency-groups]
            dev.requires-python = "==3.13"
            docs = {}
            """),
            dedent("""\
            [dependency-groups]
            dev.requires-python = "==3.13"
            docs = {}
            """),
            id="same spec",
        ),
        pytest.param(
            dedent("""\
            [dependency-groups]
            dev.requires-python = ">= 3.13"
            docs = {}
            """),
            dedent("""\
            [dependency-groups]
            dev.requires-python = ">=3.13"
            docs = {}
            """),
            id="reformat spec",
        ),
    ],
)
def test_main_edge(
    example_path: Path, python_version_file: Path, data_in: str, data_out: str
) -> None:
    uv_toml = example_path / "uv.toml"
    uv_toml.write_text(data_in)

    sync_uv_dependency_groups.main([])

    assert uv_toml.read_text() == data_out
