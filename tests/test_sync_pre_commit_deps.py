from __future__ import annotations

from contextlib import nullcontext
from pathlib import Path
from textwrap import dedent
from typing import TYPE_CHECKING, cast
from unittest.mock import patch

import pytest
import ruamel.yaml

from pre_commit_hooks import sync_pre_commit_deps
from pre_commit_hooks.sync_pre_commit_deps import main

if TYPE_CHECKING:
    from collections.abc import Sequence
    from typing import Any

DATA = Path(__file__).parent / "data"


def load_yaml_path(path: Path) -> dict[str, Any]:
    yaml = ruamel.yaml.YAML()
    with path.open(encoding="utf-8") as f:
        return cast("dict[str, Any]", yaml.load(f))


@pytest.fixture
def loaded_simple() -> dict[str, Any]:
    return load_yaml_path(DATA / "simple-pre-commit-config.yaml")


@pytest.mark.parametrize(
    ("hook_ids_from", "expected"),
    [
        (["black"], {"black": "23.3.0"}),
        (["black", "ruff-check"], {"black": "23.3.0", "ruff": "0.14.5"}),
        (["black", "ruff-format"], {"black": "23.3.0", "ruff-abc": "0.14.5"}),
    ],
)
def test__get_versions_from_ids(
    loaded_simple: dict[str, Any], hook_ids_from: list[str], expected: dict[str, Any]
) -> None:
    assert (
        sync_pre_commit_deps._get_versions_from_ids(
            loaded_simple,
            hook_ids_from,
            {"ruff-check": "ruff", "ruff-format": "ruff-abc"},
        )
        == expected
    )


@pytest.mark.parametrize(
    ("data", "expected"),
    [
        (
            dedent("""\
            ruff==0.14.6
            black==23.4.0,
            """),
            {"ruff": "0.14.6", "black": "23.4.0"},
        ),
    ],
)
def test__get_versions_from_requirements(
    tmp_path: Path, data: str, expected: dict[str, Any]
) -> None:
    path = tmp_path / "requirements.txt"
    path.write_text(data)

    assert sync_pre_commit_deps._get_versions_from_requirements(path) == expected


def test__lastversion() -> None:
    with patch("lastversion.latest", autospec=True, return_value="abc"):
        assert sync_pre_commit_deps._get_versions_from_lastversion(["ruff"]) == {
            "ruff": "abc"
        }


def test__get_hook_ids(loaded_simple: dict[str, Any]) -> None:
    assert sync_pre_commit_deps._get_hook_ids(loaded_simple) == [
        "black",
        "blacken-docs",
        "ruff-check",
        "ruff-format",
        "doccmd",
    ]


@pytest.mark.parametrize(
    ("include", "exclude", "expected"),
    [
        ([], [], list("abcde")),
        (["c", "d"], [], list("cd")),
        ([], ["a", "b"], list("cde")),
    ],
)
def test__limit_hooks(
    include: list[str], exclude: list[str], expected: list[str]
) -> None:
    hook_ids = list("abcde")

    assert sync_pre_commit_deps._limit_hooks(hook_ids, include, exclude) == expected


@pytest.mark.parametrize(
    ("id_to_package", "expected"),
    [
        (
            [],
            nullcontext({}),
        ),
        (
            ["a"],
            pytest.raises(ValueError, match=r"hook id to dep str .*"),
        ),
        (["a:b", "c : d", "e: f "], nullcontext({"a": "b", "c": "d", "e": "f"})),
    ],
)
def test__parse_id_to_dep(id_to_package: list[str], expected: Any) -> None:
    with expected as e:
        assert sync_pre_commit_deps._parse_id_to_dep(id_to_package) == e


def create_config_file(tmp_path: Path, contents: str) -> Path:
    cfg = tmp_path / ".pre-commit-config.yaml"
    cfg.write_text(contents)

    return cfg


@pytest.mark.parametrize(
    ("options", "s"),
    [
        pytest.param(
            [],
            dedent("""\
repos:
  - repo: https://github.com/psf/black
    rev: 23.3.0
    hooks:
      - id: black
  - repo: https://github.com/adamchainz/blacken-docs
    rev: 1.15.0
    hooks:
      - id: blacken-docs
        additional_dependencies:
          - black==23.3.0
            """),
            id="already correct version",
        ),
        pytest.param(
            ["--to-exclude", "blacken-docs"],
            dedent("""\
repos:
  - repo: https://github.com/psf/black
    rev: 23.3.0
    hooks:
      - id: black
  - repo: https://github.com/adamchainz/blacken-docs
    rev: 1.15.0
    hooks:
      - id: blacken-docs
        additional_dependencies:
          - black==23.2.0
            """),
            id="id not added to updateable",
        ),
        pytest.param(
            [],
            dedent("""\
repos:
  - repo: https://github.com/psf/black
    rev: 23.3.0
    hooks:
      - name: \N{SNOWMAN} black
        id: black
            """),
            id="unicode no-op",
        ),
        pytest.param(
            [],
            dedent("""\
repos:
  - repo: https://github.com/astral-sh/ruff-pre-commit
    rev: v0.14.5
    hooks:
      - id: ruff-check
        alias: ruff
  - repo: https://github.com/adamtheturtle/doccmd-pre-commit
    rev: v2025.11.8.1
    hooks:
      - id: doccmd
        name: "ruff format markdown"
        alias: ruff
        additional_dependencies:
          - ruff==0.14.5
            """),
            id="ruff",
        ),
    ],
)
def test_main_noop(options: Sequence[str], tmp_path: Path, s: str) -> None:
    cfg = create_config_file(tmp_path, s)

    assert not main((*options, str(cfg)))

    with cfg.open(encoding="utf-8") as f:
        assert f.read() == s


@pytest.mark.parametrize(
    ("options", "text_in", "text_out"),
    [
        pytest.param(
            [],
            dedent("""\
repos:
  - repo: https://github.com/psf/black
    rev: 23.3.0
    hooks:
      - id: black
  - repo: https://github.com/adamchainz/blacken-docs
    rev: 1.15.0
    hooks:
      - id: blacken-docs
        additional_dependencies:
          - black==23.2.0
            """),
            dedent("""\
repos:
  - repo: https://github.com/psf/black
    rev: 23.3.0
    hooks:
      - id: black
  - repo: https://github.com/adamchainz/blacken-docs
    rev: 1.15.0
    hooks:
      - id: blacken-docs
        additional_dependencies:
          - black==23.3.0
            """),
            id="blacken",
        ),
        pytest.param(
            ["--from-exclude", "black"],
            dedent("""\
repos:
  - repo: https://github.com/psf/black
    rev: 23.3.0
    hooks:
      - id: black
  - repo: https://github.com/adamchainz/blacken-docs
    rev: 1.15.0
    hooks:
      - id: blacken-docs
        additional_dependencies:
          - black==23.2.0
  - repo: https://github.com/astral-sh/ruff-pre-commit
    rev: v0.14.5
    hooks:
      - id: ruff-check
        alias: ruff
      - id: ruff-format
        alias: ruff
  - repo: https://github.com/adamtheturtle/doccmd-pre-commit
    rev: v2025.11.8.1
    hooks:
      - id: doccmd
        name: "ruff format markdown"
        alias: ruff
        additional_dependencies:
          - ruff==0.14.2
            """),
            dedent("""\
repos:
  - repo: https://github.com/psf/black
    rev: 23.3.0
    hooks:
      - id: black
  - repo: https://github.com/adamchainz/blacken-docs
    rev: 1.15.0
    hooks:
      - id: blacken-docs
        additional_dependencies:
          - black==23.2.0
  - repo: https://github.com/astral-sh/ruff-pre-commit
    rev: v0.14.5
    hooks:
      - id: ruff-check
        alias: ruff
      - id: ruff-format
        alias: ruff
  - repo: https://github.com/adamtheturtle/doccmd-pre-commit
    rev: v2025.11.8.1
    hooks:
      - id: doccmd
        name: "ruff format markdown"
        alias: ruff
        additional_dependencies:
          - ruff==0.14.5
            """),
            id="ruff",
        ),
        # using requirements
        pytest.param(
            [
                "-r",
                str(DATA / "requirements-ruff.txt"),
            ],
            dedent("""\
repos:
  - repo: https://github.com/psf/black
    rev: 23.3.0
    hooks:
      - id: black
  - repo: https://github.com/adamchainz/blacken-docs
    rev: 1.15.0
    hooks:
      - id: blacken-docs
        additional_dependencies:
          - black==23.2.0
  - repo: https://github.com/astral-sh/ruff-pre-commit
    rev: v0.14.5
    hooks:
      - id: ruff-check
        alias: ruff
      - id: ruff-format
        alias: ruff
  - repo: https://github.com/adamtheturtle/doccmd-pre-commit
    rev: v2025.11.8.1
    hooks:
      - id: doccmd
        name: "ruff format markdown"
        alias: ruff
        additional_dependencies:
          - ruff==0.14.2
            """),
            dedent("""\
repos:
  - repo: https://github.com/psf/black
    rev: 23.3.0
    hooks:
      - id: black
  - repo: https://github.com/adamchainz/blacken-docs
    rev: 1.15.0
    hooks:
      - id: blacken-docs
        additional_dependencies:
          - black==23.4.0
  - repo: https://github.com/astral-sh/ruff-pre-commit
    rev: v0.14.5
    hooks:
      - id: ruff-check
        alias: ruff
      - id: ruff-format
        alias: ruff
  - repo: https://github.com/adamtheturtle/doccmd-pre-commit
    rev: v2025.11.8.1
    hooks:
      - id: doccmd
        name: "ruff format markdown"
        alias: ruff
        additional_dependencies:
          - ruff==0.14.6
            """),
            id="requirements",
        ),
        pytest.param(
            ["--last", "black", "--last", "ruff"],
            dedent("""\
repos:
  - repo: https://github.com/adamchainz/blacken-docs
    rev: 1.15.0
    hooks:
      - id: blacken-docs
        additional_dependencies:
          - black==23.2.0
  - repo: https://github.com/adamtheturtle/doccmd-pre-commit
    rev: v2025.11.8.1
    hooks:
      - id: doccmd
        name: "ruff format markdown"
        alias: ruff
        additional_dependencies:
          - ruff==0.14.2
            """),
            dedent("""\
repos:
  - repo: https://github.com/adamchainz/blacken-docs
    rev: 1.15.0
    hooks:
      - id: blacken-docs
        additional_dependencies:
          - black==abc
  - repo: https://github.com/adamtheturtle/doccmd-pre-commit
    rev: v2025.11.8.1
    hooks:
      - id: doccmd
        name: "ruff format markdown"
        alias: ruff
        additional_dependencies:
          - ruff==abc
            """),
            id="lastversion",
        ),
    ],
)
def test_main_from_to(
    tmp_path: Path, options: Sequence[str], text_in: str, text_out: str
) -> None:
    with patch("lastversion.latest", return_value="abc"):
        cfg = create_config_file(tmp_path, text_in)

        assert main([str(cfg), *options])

        with cfg.open(encoding="utf-8") as f:
            assert f.read() == text_out
