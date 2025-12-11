# pylint: disable=bad-builtin
from __future__ import annotations

from contextlib import nullcontext
from pathlib import Path
from textwrap import dedent
from typing import TYPE_CHECKING

import pytest
from packaging.requirements import Requirement

from pre_commit_hooks import fill_pre_commit_deps as fill_deps
from pre_commit_hooks.fill_pre_commit_deps import (
    _limit_requirements,  # noqa: PLC2701
)

from ._utils import create_config_file

if TYPE_CHECKING:
    from collections.abc import Sequence
    from typing import Any


@pytest.fixture
def example_pyproject() -> str:
    return dedent("""
    [project]
    name = "package"
    dependencies = ["dep_0", "dep_1"]

    [project.optional-dependencies]
    a_option = ["a_thing", "b_thing", "package[b_option, c_option]"]
    "b.option" = ["b_0", "b_1", "package[other]"]
    c-option = ["b_0", "c_0"]
    other = ["other_0", "other_1"]
    all = ["package[a-option]", "package[other]"]

    [dependency-groups]
    dev = [
        "jupyter",
        { include-group = "test" },
        { include-group = "optional" },
        { include-group = "type_check" },
    ]
    test = [
        "pytest",
    ]
    optional = ["package[all]"]
    "type.check" = [
        "types-pyyaml",
        "pytest",
        "mypy",
    ]
    """)


@pytest.fixture
def parser(example_pyproject: str) -> fill_deps.ParseDependencies:
    return fill_deps.ParseDependencies.from_string(example_pyproject)


@pytest.mark.parametrize(
    ("deps", "exclude", "include", "expected"),
    [
        pytest.param(
            ["foo[a, b]", "bar_thing", "thing", "other"],
            [],
            [],
            ["foo[a,b]", "bar_thing", "thing", "other"],
            id="noop",
        ),
        pytest.param(
            ["foo[a, b]", "bar_thing", "thing", "other"],
            ["foo"],
            [],
            ["bar_thing", "thing", "other"],
            id="exclude",
        ),
        pytest.param(
            ["foo[a, b]", "bar_thing", "thing", "other"],
            [],
            ["foo"],
            ["foo[a,b]"],
            id="include",
        ),
    ],
)
def test__limit_requirements(
    deps: Sequence[str],
    exclude: Sequence[str],
    include: Sequence[str],
    expected: list[str],
) -> None:
    assert (
        list(map(str, _limit_requirements(map(Requirement, deps), exclude, include)))
        == expected
    )


@pytest.mark.parametrize(
    ("keys", "kws", "expected"),
    [
        pytest.param(["dependency-groups", "test"], {}, ["pytest"], id="get"),
        pytest.param(["hello"], {}, None, id="missing"),
        pytest.param(["hello"], {"default": 2}, 2, id="missing default"),
        pytest.param(
            ["hello"], {"default": 2, "factory": tuple}, (), id="missing factory"
        ),
    ],
)
def test_parsedependencies_get_in(
    parser: fill_deps.ParseDependencies,
    keys: list[str],
    kws: dict[str, Any],
    expected: Any,
) -> None:
    assert parser.get_in(*keys, **kws) == expected


@pytest.mark.parametrize(
    ("pyproject", "expected"),
    [
        pytest.param(
            dedent("""
            [project]
            name = "hello.there"
            """),
            nullcontext("hello-there"),
            id="normalize",
        ),
        pytest.param(
            dedent("""
            [project]
            """),
            pytest.raises(ValueError, match=r"Must specify .*"),
            id="missing",
        ),
    ],
)
def test_parsedependencies_package_name(pyproject: str, expected: Any) -> None:
    parser = fill_deps.ParseDependencies.from_string(pyproject)

    with expected as e:
        assert parser.package_name == e


def test_parsedependencies_dependencies(parser: fill_deps.ParseDependencies) -> None:
    assert list(map(str, parser.dependencies)) == ["dep-0", "dep-1"]


@pytest.mark.parametrize(
    ("extras", "groups", "no_project_dependencies", "expected"),
    [
        pytest.param([], [], False, ["dep-0", "dep-1"], id="project"),
        pytest.param(["other"], [], True, ["other-0", "other-1"], id="extra"),
        pytest.param(
            [], ["test"], False, ["dep-0", "dep-1", "pytest"], id="group and project"
        ),
    ],
)
def test_parsedependencies_pip_requirements(
    parser: fill_deps.ParseDependencies,
    extras: list[str],
    groups: list[str],
    no_project_dependencies: bool,
    expected: list[str],
) -> None:
    assert (
        sorted(
            map(
                str,
                parser.pip_requirements(
                    extras=extras,
                    groups=groups,
                    no_project_dependencies=no_project_dependencies,
                ),
            )
        )
        == expected
    )


def test_parsedependencies_from_path() -> None:
    path = Path(__file__).parent.parent / "pyproject.toml"
    assert (
        fill_deps.ParseDependencies.from_path(path).package_name == "pre-commit-hooks"
    )


@pytest.mark.parametrize(
    ("requirements_string", "expected"),
    [
        pytest.param(
            dedent("""
            a_thing[other_thing]
            something; python_version>='3.8'
            """),
            {"a-thing[other-thing]", 'something; python_version >= "3.8"'},
            id="simple",
        )
    ],
)
def test_parse_requirements_file(
    tmp_path: Path, requirements_string: str, expected: set[str]
) -> None:
    path = tmp_path / "requirements.txt"
    path.write_text(requirements_string)

    assert set(map(str, fill_deps.parse_requirements_file(path))) == expected


@pytest.mark.parametrize(
    ("options", "pre_commit_str", "requirements_str", "expected", "code"),
    [
        pytest.param(
            ["--hook=mypy", "--no-project-dependencies"],
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
            ["--hook=mypy"],
            dedent("""\
repos:
  - repo: https://github.com/pre-commit/mirrors-mypy
    rev: v1.19.0
    hooks:
      - id: mypy
        additional_dependencies:
          - dep-0
          - dep-1
  - repo: https://github.com/usnistgov/pyproject2conda
    rev: v0.22.1
    hooks:
      - id: pyproject2conda-project
            """),
            None,
            dedent("""\
repos:
  - repo: https://github.com/pre-commit/mirrors-mypy
    rev: v1.19.0
    hooks:
      - id: mypy
        additional_dependencies:
          - dep-0
          - dep-1
  - repo: https://github.com/usnistgov/pyproject2conda
    rev: v0.22.1
    hooks:
      - id: pyproject2conda-project
            """),
            0,
            id="no_op 1",
        ),
        pytest.param(
            ["--hook=mypy", "--extra=other"],
            dedent("""\
repos:
  - repo: https://github.com/pre-commit/mirrors-mypy
    rev: v1.19.0
    hooks:
      - id: mypy
        additional_dependencies:
          - dep-0
          - dep-1
            """),
            None,
            dedent("""\
repos:
  - repo: https://github.com/pre-commit/mirrors-mypy
    rev: v1.19.0
    hooks:
      - id: mypy
        additional_dependencies:
          - dep-0
          - dep-1
          - other-0
          - other-1
            """),
            1,
            id="extra",
        ),
        pytest.param(
            [
                "--hook=mypy",
                "--group=type_check",
                "--no-project-dependencies",
                "--exclude=mypy",
            ],
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
        additional_dependencies:
          - pytest
          - types-pyyaml
            """),
            1,
            id="group",
        ),
        pytest.param(
            [
                "--hook=mypy",
                "--group=type_check",
                "--no-project-dependencies",
                "--include=pytest",
            ],
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
        additional_dependencies:
          - pytest
            """),
            1,
            id="group include",
        ),
        pytest.param(
            [
                "--hook=mypy",
                "--group=type_check",
                "--extra=c-option",
                "--exclude=mypy",
            ],
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
        additional_dependencies:
          - b-0
          - c-0
          - dep-0
          - dep-1
          - pytest
          - types-pyyaml
            """),
            1,
            id="extra and group",
        ),
        pytest.param(
            [
                "--hook=mypy",
                "--group=type_check",
                "--exclude=mypy",
                "--no-project-dependencies",
                "--requirements=requirements.txt",
                "--requirements-exclude=pyright",
            ],
            dedent("""\
repos:
  - repo: https://github.com/pre-commit/mirrors-mypy
    rev: v1.19.0
    hooks:
      - id: mypy
            """),
            dedent("""\
            foo == 0.1
            bar[thing] >= 0.2
            pyright==0.2
            """),
            dedent("""\
repos:
  - repo: https://github.com/pre-commit/mirrors-mypy
    rev: v1.19.0
    hooks:
      - id: mypy
        additional_dependencies:
          - bar[thing]>=0.2
          - foo==0.1
          - pytest
          - types-pyyaml
            """),
            1,
            id="requirements",
        ),
    ],
)
def test_main(
    example_path: Path,
    example_pyproject: str,
    options: Sequence[str],
    pre_commit_str: str,
    requirements_str: str | None,
    expected: str,
    code: int,
) -> None:
    pre_commit_config = create_config_file(example_path, pre_commit_str)
    pyproject = create_config_file(
        example_path, example_pyproject, name="pyproject.toml"
    )

    config_options = ["--config", str(pre_commit_config), "--pyproject", str(pyproject)]
    if requirements_str is not None:
        _ = create_config_file(example_path, requirements_str, name="requirements.txt")

    assert fill_deps.main((*options, *config_options)) == code

    assert pre_commit_config.read_text() == expected
