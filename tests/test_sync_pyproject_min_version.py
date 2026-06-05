from __future__ import annotations

from contextlib import nullcontext
from pathlib import Path
from textwrap import dedent
from typing import TYPE_CHECKING

import pytest

import sync_pre_commit_hooks.sync_pyproject_min_versions as mod

if TYPE_CHECKING:
    from typing import Any


@pytest.mark.parametrize(
    ("params", "expected"),
    [
        pytest.param([], pytest.raises(SystemExit, match=r"2"), id="no requirements"),
        pytest.param(
            ["-rhello.txt"],
            {"requirements": Path("hello.txt")},
            id="simple",
        ),
        pytest.param(
            [
                "-rhello.txt",
                "--include",
                "a",
                "--include",
                "b",
                "--exclude",
                "c",
                "--no-ignore-non-toml",
                "thing.toml",
            ],
            {
                "requirements": Path("hello.txt"),
                "include": ["a", "b"],
                "exclude": ["c"],
                "ignore_non_toml": False,
                "paths": [Path("thing.toml")],
            },
            id="all",
        ),
    ],
)
def test__get_params(params: list[str], expected: Any) -> None:

    if isinstance(expected, dict):
        expected = nullcontext(mod.Options.from_kws(expected))

    with expected as e:
        assert mod._get_options(params) == e


@pytest.mark.parametrize(
    ("versions", "include", "exclude", "expected"),
    [
        pytest.param({}, [], [], None),
        pytest.param({"a": "1.2.3", "b": "2.3.4"}, [], [], None),
        pytest.param(
            {"a_thing": "1.2.3", "b_thing": "2.3.4"},
            [],
            [],
            {"a-thing": "1.2.3", "b-thing": "2.3.4"},
        ),
        pytest.param(
            {"a_thing": "1.2.3", "b_thing": "2.3.4"},
            ["a.thing"],
            [],
            {"a-thing": "1.2.3"},
        ),
        pytest.param(
            {"a_thing": "1.2.3", "b_thing": "2.3.4"},
            ["a.thing"],
            ["a-thing"],
            {},
        ),
        pytest.param(
            {"a_thing": "1.2.3", "b_thing": "2.3.4"},
            [],
            ["a.thing"],
            {"b-thing": "2.3.4"},
        ),
    ],
)
def test__normalize_versions(
    versions: dict[str, str],
    include: list[str],
    exclude: list[str],
    expected: dict[str, str] | None,
) -> None:
    if expected is None:
        expected = versions
    assert (
        mod._normalize_versions(versions, include=include, exclude=exclude) == expected
    )


@pytest.mark.parametrize(
    ("paths", "ignore_non_toml", "expected"),
    [
        pytest.param(
            [],
            True,
            [],
        ),
        pytest.param(
            ["one.toml", "two.txt"],
            False,
            ["one.toml", "two.txt"],
        ),
        pytest.param(
            ["one.toml", "two.txt"],
            True,
            ["one.toml"],
        ),
    ],
)
def test__normalize_paths(
    paths: list[str], ignore_non_toml: bool, expected: list[str]
) -> None:
    paths_, expected_ = ([Path(x) for x in thing] for thing in (paths, expected))
    assert mod._normalize_paths(paths_, ignore_non_toml) == expected_


versions_markers = pytest.mark.parametrize(
    "versions",
    [{}, {"mypy": "1.2.3", "pyright": "2.3.4", "an-example": "3.4.5"}],
)
toml_markers = pytest.mark.parametrize(
    ("toml", "expected"),
    [
        pytest.param(
            dedent(r"""
            dependencies = [
                "mypy>=0.0.0",
                'pyright[other-thing,another.thing] >= 0.0.0; python_version<"3.11"',
                "an.example>=0.0.0",
                "an_example>=0.0.0",
                "a>=0.0.0",           # missing
                "mypy>0.0.0",         # >
                "mypy>=0.0.0,<4.0",   # mixed
                "mypy-other>=0.0.0",  # -other
                "other-mypy>=0.0.0",  # other-
                mypy>=0.0.0,          # no quote
                "mypy>=0.0.0,<4.0.0", # not just >=
                "mypy>=0.0.0; other-thing"  # invalid marker
                "mypy >= 1.2.3",      # untouched
            ]
            """),
            dedent(r"""
            dependencies = [
                "mypy>=1.2.3",
                'pyright[other-thing,another.thing] >= 2.3.4; python_version<"3.11"',
                "an.example>=3.4.5",
                "an_example>=3.4.5",
                "a>=0.0.0",           # missing
                "mypy>0.0.0",         # >
                "mypy>=0.0.0,<4.0",   # mixed
                "mypy-other>=0.0.0",  # -other
                "other-mypy>=0.0.0",  # other-
                mypy>=0.0.0,          # no quote
                "mypy>=0.0.0,<4.0.0", # not just >=
                "mypy>=0.0.0; other-thing"  # invalid marker
                "mypy >= 1.2.3",      # untouched
            ]
            """),
            id="replace mixecd",
        ),
    ],
)


@versions_markers
@toml_markers
def test_regex(versions: dict[str, str], toml: str, expected: str | None) -> None:
    if versions == {}:
        expected = toml
    replacer = mod._factory_replacer(versions)
    assert mod.REQUIREMENT_REGEX.sub(replacer, toml) == expected


@versions_markers
@toml_markers
def test_main(
    tmp_path: Path, versions: dict[str, str], toml: str, expected: str | None
) -> None:

    if versions == {}:
        expected = toml

    requirements_path = tmp_path / "locked.txt"
    toml_path = tmp_path / "pyproject.toml"

    versions_str = "\n".join([
        f"{name} >= {version}" for name, version in versions.items()
    ])

    requirements_path.write_text(versions_str, encoding="utf-8")
    toml_path.write_text(toml, encoding="utf-8")

    assert not mod.main(["--requirements", str(requirements_path), str(toml_path)])

    assert toml_path.read_text(encoding="utf-8") == expected
