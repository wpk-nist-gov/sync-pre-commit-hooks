from __future__ import annotations

from textwrap import dedent
from typing import TYPE_CHECKING

import pytest
from packaging.requirements import Requirement

from pre_commit_hooks import fill_pre_commit_deps as fill_deps
from pre_commit_hooks.fill_pre_commit_deps import (
    _limit_requirements,  # noqa: PLC2701
)

if TYPE_CHECKING:
    from collections.abc import Sequence


@pytest.mark.parametrize(
    ("deps", "exclude", "include", "expected"),
    [
        pytest.param(
            ["foo[a, b]", "bar_thing", "thing", "other"],
            [],
            [],
            ["foo[a,b]", "bar_thing", "thing", "other"],
        ),
        pytest.param(
            ["foo[a, b]", "bar_thing", "thing", "other"],
            ["foo"],
            [],
            ["bar_thing", "thing", "other"],
        ),
        pytest.param(
            ["foo[a, b]", "bar_thing", "thing", "other"],
            [],
            ["foo"],
            ["foo[a,b]"],
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
    ("dep", "expected"),
    [
        ("foo[a_thing, b]", "foo[a-thing,b]"),
        ("a_thing", "a-thing"),
        ("a.thing[b.thing]", "a-thing[b-thing]"),
    ],
)
def test__canonicalize_requirement(dep: str, expected: str) -> None:
    assert str(fill_deps._canonicalize_requirement(Requirement(dep))) == expected


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
def parser(example_pyproject: str) -> fill_deps.ParseDepends:
    return fill_deps.ParseDepends.from_string(example_pyproject)


@pytest.mark.parametrize(
    ("extras", "expected"),
    [
        ("a_option", ["a-thing", "b-0", "b-1", "b-thing", "c-0", "other-0", "other-1"]),
        ("c.option", ["b-0", "c-0"]),
        (["other", "c-option"], ["b-0", "c-0", "other-0", "other-1"]),
        (["all"], ["a-thing", "b-0", "b-1", "b-thing", "c-0", "other-0", "other-1"]),
    ],
)
def test_resolve_optional_deps(
    parser: fill_deps.ParseDepends, extras: str | list[str], expected: list[str]
) -> None:
    assert sorted(map(str, parser.optional_dependencies.get(extras))) == expected


@pytest.mark.parametrize(
    ("groups", "expected"),
    [
        ("test", ["pytest"]),
        (
            "dev",
            [
                "a-thing",
                "b-0",
                "b-1",
                "b-thing",
                "c-0",
                "jupyter",
                "mypy",
                "other-0",
                "other-1",
                "pytest",
                "types-pyyaml",
            ],
        ),
        (["test", "type_check"], ["mypy", "pytest", "types-pyyaml"]),
    ],
)
def test_resolve_groups(
    parser: fill_deps.ParseDepends, groups: str | list[str], expected: list[str]
) -> None:
    assert sorted(map(str, set(parser.dependency_groups.get(groups)))) == expected
