from __future__ import annotations

from contextlib import AbstractContextManager, nullcontext
from dataclasses import asdict
from pathlib import Path
from textwrap import dedent
from typing import TYPE_CHECKING

import pytest

import sync_pre_commit_hooks.format_code_section_headers as mod

if TYPE_CHECKING:
    from typing import Any


@pytest.mark.parametrize(
    ("contents", "line_length", "out"),
    [
        pytest.param(
            "# * get args ---------------------------------------------------------------------------",
            None,
            None,
            id="long-line",
        ),
        pytest.param("hello there ---", None, None, id="simple"),
        pytest.param("# hello there -", None, None, id="no star"),
        pytest.param("# * hello there", None, None, id="no trailing"),
        pytest.param(
            "# * hello there -", None, "# * hello there -".ljust(88, "-"), id="basic"
        ),
        pytest.param("# * hello there -", 5, None, id="short line-length"),
        pytest.param("# * hello there -----", 21, None, id="no change"),
        pytest.param("## * hello there -", None, None, id="double hash no opt"),
        pytest.param(
            "# *   hello there  -",
            70,
            "# * hello there -".ljust(70, "-"),
            id="long fill",
        ),
        pytest.param("# *   hello there  ", None, None, id="no trailing dash"),
        pytest.param(
            "     #*   hello there  -",
            None,
            "     # * hello there -".ljust(88, "-"),
            id="formatting",
        ),
    ],
)
def test__maybe_update_contents(
    contents: str,
    line_length: int | None,
    out: str | None,
) -> None:
    if line_length is None:
        line_length = 88

    updated = out is not None
    if out is None:
        out = contents
    assert mod._maybe_update_contents(contents, line_length) == (out, updated)


@pytest.mark.parametrize(
    ("argv", "expected"),
    [
        (["hello.txt"], nullcontext({"paths": ["hello.txt"]})),
        (
            ["--line-length", "70", "--dry-run", "hello.txt", "there.py"],
            nullcontext({
                "paths": ["hello.txt", "there.py"],
                "default_line_length": 70,
                "dry_run": True,
            }),
        ),
        (
            ["--ext-line-length", "yaml:120", "-e", ".toml:110", "hello.txt"],
            nullcontext({
                "paths": ["hello.txt"],
                "extension_line_length_mapping": {".yaml": 120, ".toml": 110},
            }),
        ),
        (
            ["--ext-line-length", "yaml=120", "-e", ".toml:110", "hello.txt"],
            pytest.raises(ValueError, match=r"Missing separator.*"),
        ),
    ],
)
def test__from_argv(
    argv: list[str], expected: AbstractContextManager[dict[str, Any]]
) -> None:
    with expected as e:
        out = asdict(mod._Options.from_args(argv))

        e.setdefault("default_line_length", 88)
        e.setdefault("dry_run", False)
        e.setdefault("no_config", False)
        e.setdefault("extension_line_length_mapping", {})
        e["paths"] = [Path(x) for x in e["paths"]]

        assert out == e


def _optional_contents(
    path: Path, request: pytest.FixtureRequest, default_contents: str
) -> Path:
    contents: Any = (
        param
        if (param := getattr(request, "param", None)) is not None
        else default_contents
    )
    path.write_text(dedent(contents), encoding="utf-8")
    return path


@pytest.fixture
def editorconfig_path(tmp_path: Path, request: pytest.FixtureRequest) -> Path:
    contents = """
    [*.py]
    max_line_length = 100

    [*.yaml]
    max_line_length = 110

    [*.toml]
    max_line_length = 120

    """

    return _optional_contents(
        path=tmp_path / ".editorconfig",
        request=request,
        default_contents=contents,
    )


@pytest.fixture
def example_python_path(tmp_path: Path, request: pytest.FixtureRequest) -> Path:
    contents = """
    import sys

    # * A header  --
    """
    return _optional_contents(
        path=tmp_path / "example_python_file.py",
        request=request,
        default_contents=contents,
    )


@pytest.fixture
def example_yaml_path(tmp_path: Path, request: pytest.FixtureRequest) -> Path:
    contents = """
repos:
  # * meta hooks  ---
  - repo: meta
    hooks:
      - id: check-hooks-apply
      - id: check-useless-excludes
    """

    return _optional_contents(
        path=tmp_path / "example_yaml_file.yaml",
        request=request,
        default_contents=contents,
    )


@pytest.fixture
def example_toml_path(tmp_path: Path, request: pytest.FixtureRequest) -> Path:
    contents = """
    # * Project -
    [project]
    name = "sync-pre-commit-hooks"
    """

    return _optional_contents(
        path=tmp_path / "example_toml_file.toml",
        request=request,
        default_contents=contents,
    )


@pytest.mark.parametrize(
    (
        "params",
        "editorconfig_path",
        "expected_python",
        "expected_yaml",
        "expected_toml",
    ),
    [
        ({}, None, 100, 110, 120),
        (
            {"extension_line_length_mapping": {".yaml": 66, ".toml": 22}},
            None,
            100,
            66,
            22,
        ),
        (
            {
                "default_line_length": 20,
                "no_config": True,
                "extension_line_length_mapping": {".yaml": 66},
            },
            None,
            20,
            66,
            20,
        ),
        (
            {"default_line_length": 20, "extension_line_length_mapping": {".yaml": 66}},
            """
            [*.py]
            max_line_length = 77
            """,
            77,
            66,
            20,
        ),
    ],
    indirect=["editorconfig_path"],
)
def test_get_line_length(
    params: dict[str, Any],
    editorconfig_path: Path,
    example_python_path: Path,
    example_yaml_path: Path,
    example_toml_path: Path,
    expected_python: int,
    expected_yaml: int,
    expected_toml: int,
) -> None:

    assert editorconfig_path.exists()

    options = mod._Options(**params)

    for path, expected in (
        (example_python_path, expected_python),
        (example_yaml_path, expected_yaml),
        (example_toml_path, expected_toml),
    ):
        assert options.get_line_length(path) == expected


@pytest.mark.parametrize(
    ("argv", "contents", "expected"),
    [
        pytest.param(
            [], "# *   hello there  -", "# * hello there -".ljust(88, "-"), id="basic"
        ),
        pytest.param(
            ["--dry-run"], "# *   hello there  -", "# *   hello there  -", id="dry-run"
        ),
        pytest.param(
            ["--line-length", "70"],
            "# *   hello there  -",
            "# * hello there -".ljust(70, "-"),
            id="line-length",
        ),
        pytest.param(
            [],
            "# * get args -------------------------------------------------------------------------",
            "# * get args ---------------------------------------------------------------------------",
            id="long-line",
        ),
        pytest.param(
            [],
            dedent("""
            hello

            # * get args -------------------------------------------------------------------------

            there
            """),
            dedent("""
            hello

            # * get args ---------------------------------------------------------------------------

            there
            """),
            id="multi line",
        ),
    ],
)
def test_main(tmp_path: Path, argv: list[str], contents: str, expected: str) -> None:

    path = tmp_path / "hello.py"
    path.write_text(contents)

    mod.main(["--no-config", *argv, str(path)])

    assert path.read_text(encoding="utf-8") == expected
