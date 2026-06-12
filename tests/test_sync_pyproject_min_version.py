from __future__ import annotations

from contextlib import nullcontext
from functools import partial
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
                "thing.toml",
            ],
            {
                "requirements": Path("hello.txt"),
                "include": ["a", "b"],
                "exclude": ["c"],
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
    ("paths", "expected"),
    [
        pytest.param(
            [],
            [[], []],
        ),
        pytest.param(
            ["one.toml", "two.txt"],
            [["one.toml"], []],
        ),
        pytest.param(
            ["one.toml", "two.txt", "foo.py", "bar.py"],
            [["one.toml"], ["foo.py", "bar.py"]],
        ),
    ],
)
def test__get_toml_and_script_paths(
    paths: list[str], expected: tuple[list[str], list[str]]
) -> None:
    paths_ = [Path(x) for x in paths]
    expected_ = tuple([Path(x) for x in e] for e in expected)
    assert mod._get_toml_and_script_paths(paths_) == expected_


versions_markers = pytest.mark.parametrize(
    "versions",
    [{}, {"mypy": "1.2.3", "pyright": "2.3.4", "an-example": "3.4.5"}],
)
toml_markers = pytest.mark.parametrize(
    ("as_script", "include", "exclude", "toml_or_script", "expected"),
    [
        pytest.param(
            False,
            [],
            [],
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
            id="replace multi",
        ),
        pytest.param(
            False,
            ["mypy"],
            [],
            dedent(r"""
            dependencies = [
                "mypy>=0.0.0",
                'pyright>=0.0.0',
                "an-example>=0.0.0",
            ]
            """),
            dedent(r"""
            dependencies = [
                "mypy>=1.2.3",
                'pyright>=0.0.0',
                "an-example>=0.0.0",
            ]
            """),
            id="replace mixed",
        ),
        pytest.param(
            False,
            [],
            ["mypy"],
            dedent(r"""
            dependencies = [
                "mypy>=0.0.0",
                'pyright>=0.0.0',
                "an-example>=0.0.0",
            ]
            """),
            dedent(r"""
            dependencies = [
                "mypy>=0.0.0",
                'pyright>=2.3.4',
                "an-example>=3.4.5",
            ]
            """),
            id="replace mixed 2",
        ),
        # scripts
        pytest.param(
            True,
            [],
            [],
            dedent(r"""
            # /// script
            # dependencies = [
            #     "mypy>=0.0.0",
            #     'pyright[other-thing,another.thing] >= 0.0.0; python_version<"3.11"',
            #     "an.example>=0.0.0",
            #     "an_example>=0.0.0",
            #     "a>=0.0.0",           # missing
            #     "mypy>0.0.0",         # >
            #     "mypy>=0.0.0,<4.0",   # mixed
            #     "mypy-other>=0.0.0",  # -other
            #     "other-mypy>=0.0.0",  # other-
            #     mypy>=0.0.0,          # no quote
            #     "mypy>=0.0.0,<4.0.0", # not just >=
            #     "mypy>=0.0.0; other-thing"  # invalid marker
            #     "mypy >= 1.2.3",      # untouched
            # ]
            # ///
            """),
            dedent(r"""
            # /// script
            # dependencies = [
            #     "mypy>=1.2.3",
            #     'pyright[other-thing,another.thing] >= 2.3.4; python_version<"3.11"',
            #     "an.example>=3.4.5",
            #     "an_example>=3.4.5",
            #     "a>=0.0.0",           # missing
            #     "mypy>0.0.0",         # >
            #     "mypy>=0.0.0,<4.0",   # mixed
            #     "mypy-other>=0.0.0",  # -other
            #     "other-mypy>=0.0.0",  # other-
            #     mypy>=0.0.0,          # no quote
            #     "mypy>=0.0.0,<4.0.0", # not just >=
            #     "mypy>=0.0.0; other-thing"  # invalid marker
            #     "mypy >= 1.2.3",      # untouched
            # ]
            # ///
            """),
            id="replace multi script",
        ),
        pytest.param(
            True,
            [],
            [],
            dedent(r"""
            # /// script
            # dependencies = [
            #     "mypy>=0.0.0",
            # ]
            # ///
            """),
            dedent(r"""
            # /// script
            # dependencies = [
            #     "mypy>=1.2.3",
            # ]
            # ///
            """),
            id="replace mixed script",
        ),
        pytest.param(
            True,
            ["mypy"],
            [],
            dedent(r"""
            # /// script
            # dependencies = [
            #     "mypy>=0.0.0",
            # ]
            """),
            dedent(r"""
            # /// script
            # dependencies = [
            #     "mypy>=0.0.0",
            # ]
            """),
            id="noreplace script (missing end)",
        ),
        pytest.param(
            True,
            ["mypy"],
            [],
            dedent(r"""
            # /// scripts
            # dependencies = [
            #     "mypy>=0.0.0",
            # ]
            # ///
            """),
            dedent(r"""
            # /// scripts
            # dependencies = [
            #     "mypy>=0.0.0",
            # ]
            # ///
            """),
            id="noreplace script (bad header)",
        ),
    ],
)


@versions_markers
@toml_markers
def test_regex(
    versions: dict[str, str],
    as_script: bool,
    include: list[str],
    exclude: list[str],
    toml_or_script: str,
    expected: str | None,
) -> None:
    if versions == {}:
        expected = toml_or_script
    else:
        versions = mod._normalize_versions(versions, include=include, exclude=exclude)

    replacer = partial(mod.REQUIREMENT_REGEX.sub, mod._factory_replacer(versions))
    if as_script:
        replacer = partial(mod._replace_pep723_section, replacer)
    assert replacer(toml_or_script) == expected


@versions_markers
@toml_markers
def test_main(
    tmp_path: Path,
    versions: dict[str, str],
    as_script: bool,
    include: list[str],
    exclude: list[str],
    toml_or_script: str,
    expected: str | None,
) -> None:

    if versions == {}:
        expected = toml_or_script

    requirements_path = tmp_path / "locked.txt"
    versions_str = "\n".join([
        f"{name} >= {version}" for name, version in versions.items()
    ])

    requirements_path.write_text(versions_str, encoding="utf-8")

    if as_script:
        toml_or_script_path = tmp_path / "a_script.py"
    else:
        toml_or_script_path = tmp_path / "pyproject.toml"

    toml_or_script_path.write_text(toml_or_script, encoding="utf-8")

    include_opts = [f"--include={x}" for x in include]
    exclude_opts = [f"--exclude={x}" for x in exclude]

    assert not mod.main([
        f"--requirements={requirements_path}",
        *include_opts,
        *exclude_opts,
        str(toml_or_script_path),
    ])

    assert toml_or_script_path.read_text(encoding="utf-8") == expected
