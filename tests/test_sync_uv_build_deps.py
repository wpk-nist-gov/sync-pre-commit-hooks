from __future__ import annotations

from contextlib import nullcontext
from pathlib import Path
from textwrap import dedent
from typing import TYPE_CHECKING
from unittest.mock import patch

import pytest
from packaging.version import Version

from sync_pre_commit_hooks import sync_uv_build_deps as mod

from ._utils import create_config_file

if TYPE_CHECKING:
    from collections.abc import Sequence
    from typing import Any


@pytest.mark.parametrize(
    ("argv", "expected"),
    [
        pytest.param(
            (), (Path(".pre-commit-config.yaml"), Path("pyproject.toml"), False)
        ),
        pytest.param(
            ("--pre-commit-config", "hello/.pre-commit-config.yaml"),
            (Path("hello/.pre-commit-config.yaml"), Path("pyproject.toml"), False),
        ),
        pytest.param(
            ("--lastversion",),
            (Path(".pre-commit-config.yaml"), Path("pyproject.toml"), True),
        ),
    ],
)
def test__get_options(argv: Sequence[str], expected: tuple[Path, Path, bool]) -> None:
    assert mod._get_options(argv) == expected


@pytest.mark.parametrize(
    ("config", "expected"),
    [
        pytest.param(
            {
                "repos": [
                    {
                        "repo": "https://github.com/astral-sh/uv-pre-commit",
                        "rev": "0.11.6",
                    },
                ]
            },
            nullcontext(Version("0.11.6")),
        ),
        pytest.param(
            {
                "repos": [
                    {
                        "repo": "https://github.com/astral-sh/uv-pre-commit",
                        "rev": "v0.12.3",
                    },
                ]
            },
            nullcontext(Version("0.12.3")),
        ),
        pytest.param(
            {
                "repos": [
                    {
                        "repo": "https://github.com/astral-sh/a-thing",
                        "rev": "v0.12.3",
                    },
                ]
            },
            pytest.raises(ValueError, match=r"No repo found.*"),
        ),
    ],
)
def test__get_uv_version(config: dict[str, Any], expected: Any) -> None:

    with (
        patch(
            "sync_pre_commit_hooks.sync_uv_build_deps.pre_commit_config_load",
            autospec=True,
            return_value=(config, None),
        ),
        expected as e,
    ):
        assert mod._get_uv_version(Path("hello")) == e


@pytest.mark.parametrize(
    ("uv_version", "expected"),
    [
        (
            Version("0.11.0"),
            "uv-build>=0.11.0,<0.12.0",
        ),
        (
            Version("0.11.1"),
            "uv-build>=0.11.1,<0.12.0",
        ),
        (
            Version("1.2.3"),
            "uv-build>=1.2.3,<1.3.0",
        ),
    ],
)
def test__get_uv_build_dep(uv_version: Version, expected: str) -> None:
    assert mod._get_uv_build_dep(uv_version) == expected


@pytest.mark.parametrize(
    ("pre_commit_config", "pyproject", "expected", "code"),
    [
        pytest.param(
            dedent("""\
repos:
  - repo: https://github.com/astral-sh/uv-pre-commit
    rev: 0.11.6
    hooks:
      - id: uv-lock
            """),
            dedent("""\
[build-system]
build-backend = "uv_build"
requires = [
    "uv-build>=0.11.6,<0.12.0",
]
            """),
            dedent("""\
[build-system]
build-backend = "uv_build"
requires = [
    "uv-build>=0.11.6,<0.12.0",
]
            """),
            0,
        ),
        pytest.param(
            dedent("""\
repos:
  - repo: https://github.com/astral-sh/uv-pre-commit
    rev: 0.11.6
    hooks:
      - id: uv-lock
            """),
            dedent("""\
[build-system]
build-backend = "uv_build"
requires = [
    "uv-build>=0.11.0,<0.12.0",
]
            """),
            dedent("""\
[build-system]
build-backend = "uv_build"
requires = [
    "uv-build>=0.11.6,<0.12.0",
]
            """),
            1,
        ),
        pytest.param(
            dedent("""\
repos:
  - repo: https://github.com/astral-sh/uv-pre-commit
    rev: 0.11.3
    hooks:
      - id: uv-lock
            """),
            dedent("""\
[build-system]
build-backend = "uv_build"
requires = [
    "uv-build>=0.11.6,<0.12.0",
]
            """),
            dedent("""\
[build-system]
build-backend = "uv_build"
requires = [
    "uv-build>=0.11.3,<0.12.0",
]
            """),
            1,
        ),
    ],
)
def test_main(
    tmp_path: Path,
    pre_commit_config: str,
    pyproject: str,
    expected: str,
    code: int,
) -> None:

    path_pre_commit = create_config_file(
        tmp_path, pre_commit_config, ".pre-commit-config.yaml"
    )
    path_pyproject = create_config_file(tmp_path, pyproject, "pyproject.toml")

    assert (
        mod.main((
            f"--pre-commit-config={path_pre_commit}",
            f"--pyproject={path_pyproject}",
        ))
        == code
    )

    with path_pyproject.open(encoding="utf-8") as f:
        assert f.read() == expected


@pytest.mark.parametrize(
    ("version_str", "pyproject", "expected", "code"),
    [
        pytest.param(
            "0.11.6",
            dedent("""\
[build-system]
build-backend = "uv_build"
requires = [
    "uv-build>=0.11.6,<0.12.0",
]
            """),
            dedent("""\
[build-system]
build-backend = "uv_build"
requires = [
    "uv-build>=0.11.6,<0.12.0",
]
            """),
            0,
        ),
        pytest.param(
            "0.11.3",
            dedent("""\
[build-system]
build-backend = "uv_build"
requires = [
    "uv-build>=0.11.6,<0.12.0",
]
            """),
            dedent("""\
[build-system]
build-backend = "uv_build"
requires = [
    "uv-build>=0.11.3,<0.12.0",
]
            """),
            1,
        ),
        pytest.param(
            "1.2.3",
            dedent("""\
[build-system]
build-backend = "uv_build"
requires = [
    "uv-build>=0.11.6,<0.12.0",
]
            """),
            dedent("""\
[build-system]
build-backend = "uv_build"
requires = [
    "uv-build>=1.2.3,<1.3.0",
]
            """),
            1,
        ),
    ],
)
def test_main_lastversion(
    tmp_path: Path,
    version_str: str,
    pyproject: str,
    expected: str,
    code: int,
) -> None:

    path_pyproject = create_config_file(tmp_path, pyproject, "pyproject.toml")
    with patch(
        "sync_pre_commit_hooks.sync_uv_build_deps.get_version_from_lastversion",
        autospec=True,
        return_value=version_str,
    ):
        assert mod.main(("--lastversion", f"--pyproject={path_pyproject}")) == code

        with path_pyproject.open(encoding="utf-8") as f:
            assert f.read() == expected
