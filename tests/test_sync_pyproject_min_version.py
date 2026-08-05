# pyright: reportUnknownLambdaType=false
# ruff:file-ignore[unused-lambda-argument]
from __future__ import annotations

from contextlib import nullcontext
from pathlib import Path
from textwrap import dedent
from typing import TYPE_CHECKING
from unittest.mock import call, patch

import pytest

import sync_pre_commit_hooks.sync_pyproject_min_versions as mod

if TYPE_CHECKING:
    from types import EllipsisType
    from typing import Any

    from packaging.utils import NormalizedName


@pytest.mark.parametrize(
    ("line", "ignore"),
    [  # pyright: ignore[reportUnknownArgumentType]
        ("# sync-pyproject-min-versions:ignore", (Ellipsis, True)),
        ("# sync-pyproject-min-version:ignore", (Ellipsis, True)),
        ("#sync-pyproject-min-version:   ignore", (Ellipsis, True)),
        ("hello # sync-pyproject-min-versions:ignore", (Ellipsis, False)),
        ("hello # sync-pyproject-min-versions:ignore[a.b]", ({"a-b"}, False)),
        ("hello # sync-pyproject-min-versions:ignore[a.b, c]", ({"a-b", "c"}, False)),
        ("hello # a thing there", (set(), False)),
        # comment before negates
        ("# a thing # sync-pyproject-min-versions: ignore", (set(), False)),
        # comment after is fine
        (
            "# sync-pyproject-min-versions: ignore[a,b] # another thing",
            ({"a", "b"}, True),
        ),
        (
            "a thing # sync-pyproject-min-versions: ignore[a,b] # another thing",
            ({"a", "b"}, False),
        ),
    ],
)
def test__get_ignore_names(
    line: str, ignore: tuple[set[NormalizedName] | EllipsisType, bool]
) -> None:
    assert mod._get_ignore_names(line) == ignore


@pytest.mark.parametrize(
    ("argv", "expected"),
    [
        pytest.param([], {}, id="no requirements"),
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
def test_options_from_argv(argv: list[str], expected: Any) -> None:

    if isinstance(expected, dict):
        expected = nullcontext(mod.Options.from_kws(expected))

    with expected as e:
        assert mod.Options.from_argv(argv) == e


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
def test_options_from_params(
    versions: dict[str, str],
    include: list[str],
    exclude: list[str],
    expected: dict[str, str] | None,
) -> None:
    if expected is None:
        expected = versions

    assert (
        mod.Options.from_params(include=include, exclude=exclude).normalize_versions(
            versions
        )
        == expected
    )


@pytest.mark.parametrize(
    ("requirements", "export_output"),
    [
        ("hello==1.2.3", "there==2.3.4"),
    ],
)
@pytest.mark.parametrize(
    ("script_name", "locked", "script_lock", "expected"),
    [
        ("hello.py", False, "requirements", {"hello": "1.2.3"}),
        ("hello.py", True, "requirements", {"hello": "1.2.3"}),
        ("hello.py", False, "infer", {"hello": "1.2.3"}),
        ("hello.py", True, "infer", {"there": "2.3.4"}),
        ("hello.py", False, "force", {"there": "2.3.4"}),
        ("hello.py", True, "force", {"there": "2.3.4"}),
    ],
)
def test_options_get_versions(
    tmp_path: Path,
    requirements: str,
    export_output: str,
    script_name: str,
    locked: bool,
    script_lock: mod.SCRIPT_LOCK,
    expected: dict[NormalizedName, str],
) -> None:

    requirements_path = tmp_path / "requirements.txt"
    requirements_path.write_text(requirements)

    opts = mod.Options(requirements=requirements_path, script_lock=script_lock)

    script_path = tmp_path / script_name
    script_path.write_text("")
    if locked:
        lock_path = script_path.with_suffix(".py.lock")
        lock_path.write_text("")

    with patch(
        "sync_pre_commit_hooks.sync_pyproject_min_versions.check_output",
        side_effect=lambda x: export_output.encode(),
    ) as mocked:
        assert opts.get_versions_from_script(script_path) == expected

        if locked and script_lock in {"force", "infer"}:
            expected_calls = [
                call([
                    "uv",
                    "export",
                    "--locked",
                    "--quiet",
                    "--no-color",
                    "--script",
                    str(script_path),
                ])
            ]
        elif script_lock == "force" or (script_lock == "infer" and locked):
            expected_calls = [
                call([
                    "uv",
                    "export",
                    "--quiet",
                    "--no-color",
                    "--script",
                    str(script_path),
                ])
            ]

        else:
            expected_calls = []

        assert mocked.mock_calls == expected_calls


@pytest.mark.parametrize(
    ("paths", "expected"),
    [
        pytest.param(
            [],
            ((), ()),
        ),
        pytest.param(
            ["one.toml", "two.txt"],
            (("one.toml",), ()),
        ),
        pytest.param(
            ["one.toml", "two.txt", "foo.py", "bar.py"],
            (("one.toml",), ("foo.py", "bar.py")),
        ),
    ],
)
def test_options_paths(
    paths: list[str], expected: tuple[tuple[str, ...], tuple[str, ...]]
) -> None:
    paths_ = [Path(x) for x in paths]
    expected_ = tuple(tuple(Path(x) for x in e) for e in expected)
    opts = mod.Options.from_params(paths=paths_)
    assert (opts.toml_paths, opts.script_paths) == expected_


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
        pytest.param(
            False,
            [],
            [],
            dedent(r"""
            dependencies = [
                "mypy>=0.0.0",
                'pyright>=0.0.0',  # sync-pyproject-min-versions: ignore
                "an-example>=0.0.0",
            ]
            """),
            dedent(r"""
            dependencies = [
                "mypy>=1.2.3",
                'pyright>=0.0.0',  # sync-pyproject-min-versions: ignore
                "an-example>=3.4.5",
            ]
            """),
            id="comment inline",
        ),
        pytest.param(
            False,
            [],
            [],
            dedent(r"""
            dependencies = [
                "mypy>=0.0.0",
                # sync-pyproject-min-versions: ignore
                'pyright>=0.0.0',
                "an-example>=0.0.0",
            ]
            """),
            dedent(r"""
            dependencies = [
                "mypy>=1.2.3",
                # sync-pyproject-min-versions: ignore
                'pyright>=0.0.0',
                "an-example>=3.4.5",
            ]
            """),
            id="comment next line",
        ),
        pytest.param(
            False,
            [],
            [],
            dedent(r"""
            dependencies = [
                "mypy>=0.0.0", 'pyright>=0.0.0'  # sync-pyproject-min-versions: ignore[pyright]
                "an-example>=0.0.0",
            ]
            """),
            dedent(r"""
            dependencies = [
                "mypy>=1.2.3", 'pyright>=0.0.0'  # sync-pyproject-min-versions: ignore[pyright]
                "an-example>=3.4.5",
            ]
            """),
            id="comment spec",
        ),
        pytest.param(
            False,
            [],
            ["an.example"],
            dedent(r"""
            dependencies = [
                # sync-pyproject-min-versions: ignore[pyright]
                "mypy>=0.0.0", 'pyright>=0.0.0'
                "an-example>=0.0.0",
            ]
            """),
            dedent(r"""
            dependencies = [
                # sync-pyproject-min-versions: ignore[pyright]
                "mypy>=1.2.3", 'pyright>=0.0.0'
                "an-example>=0.0.0",
            ]
            """),
            id="comment spec next line",
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
        # comments
        pytest.param(
            True,
            [],
            [],
            dedent(r"""
            # /// script
            # dependencies = [
            #     "mypy>=0.0.0",
            #     'pyright>=0.0.0',
            # ]
            # ///
            """),
            dedent(r"""
            # /// script
            # dependencies = [
            #     "mypy>=1.2.3",
            #     'pyright>=2.3.4',
            # ]
            # ///
            """),
            id="multi",
        ),
        pytest.param(
            True,
            [],
            [],
            dedent(r"""
            # /// script
            # dependencies = [
            #     "mypy>=0.0.0",
            #     'pyright>=0.0.0',  # sync-pyproject-min-versions: ignore
            # ]
            # ///
            """),
            dedent(r"""
            # /// script
            # dependencies = [
            #     "mypy>=1.2.3",
            #     'pyright>=0.0.0',  # sync-pyproject-min-versions: ignore
            # ]
            # ///
            """),
            id="multi comment",
        ),
        pytest.param(
            True,
            [],
            [],
            dedent(r"""
            # /// script
            # dependencies = [
            #     "mypy>=0.0.0",
            #     # sync-pyproject-min-versions: ignore
            #     'pyright>=0.0.0',
            # ]
            # ///
            """),
            dedent(r"""
            # /// script
            # dependencies = [
            #     "mypy>=1.2.3",
            #     # sync-pyproject-min-versions: ignore
            #     'pyright>=0.0.0',
            # ]
            # ///
            """),
            id="multi comment next line",
        ),
        # note that first comment is removed so need #  # sync-pyproject-min-versions
        pytest.param(
            True,
            [],
            [],
            dedent(r"""
            # /// script
            # dependencies = [
            #     "mypy>=0.0.0",
            #     sync-pyproject-min-versions: ignore
            #     'pyright>=0.0.0',
            # ]
            # ///
            """),
            dedent(r"""
            # /// script
            # dependencies = [
            #     "mypy>=1.2.3",
            #     sync-pyproject-min-versions: ignore
            #     'pyright>=2.3.4',
            # ]
            # ///
            """),
            id="multi comment next line ill formed",
        ),
        pytest.param(
            True,
            [],
            [],
            dedent(r"""
            # /// script
            # dependencies = [
            #     "mypy>=0.0.0",  'pyright>=0.0.0',  # sync-pyproject-min-versions: ignore[pyright]
            # ]
            # ///
            """),
            dedent(r"""
            # /// script
            # dependencies = [
            #     "mypy>=1.2.3",  'pyright>=0.0.0',  # sync-pyproject-min-versions: ignore[pyright]
            # ]
            # ///
            """),
            id="multi comment spec",
        ),
        pytest.param(
            True,
            [],
            [],
            dedent(r"""
            # /// script
            # dependencies = [
            #     # sync-pyproject-min-versions: ignore[pyright]
            #     "mypy>=0.0.0",  'pyright>=0.0.0',

            # ]
            # ///
            """),
            dedent(r"""
            # /// script
            # dependencies = [
            #     # sync-pyproject-min-versions: ignore[pyright]
            #     "mypy>=1.2.3",  'pyright>=0.0.0',

            # ]
            # ///
            """),
            id="multi comment spec next line",
        ),
    ],
)


@versions_markers
@toml_markers
def test_replace_contents(
    versions: dict[str, str],
    as_script: bool,
    include: list[str],
    exclude: list[str],
    toml_or_script: str,
    expected: str | None,
) -> None:
    versions_: dict[NormalizedName, str] = {}
    if versions == {}:
        expected = toml_or_script
    else:
        versions_ = mod.Options.from_params(
            include=include,
            exclude=exclude,
        ).normalize_versions(versions)

    replacer = mod.Replacer(versions_)
    func = replacer.replace_contents_pep723 if as_script else replacer.replace_contents
    assert func(toml_or_script) == expected


@versions_markers
@toml_markers
@pytest.mark.parametrize("script_lock", ["requirements", "infer", "force"])
def test_main(
    tmp_path: Path,
    versions: dict[str, str],
    as_script: bool,
    include: list[str],
    exclude: list[str],
    toml_or_script: str,
    expected: str | None,
    script_lock: str,
) -> None:

    if not as_script and script_lock != "requirements":
        return

    if versions == {}:
        expected = toml_or_script

    requirements_path = tmp_path / "locked.txt"
    versions_str = "\n".join([
        f"{name} >= {version}" for name, version in versions.items()
    ])

    requirements_path.write_text(versions_str, encoding="utf-8")

    toml_or_script_path = tmp_path / ("a_script.py" if as_script else "pyproject.toml")
    toml_or_script_path.write_text(toml_or_script, encoding="utf-8")

    include_opts = [f"--include={x}" for x in include]
    exclude_opts = [f"--exclude={x}" for x in exclude]

    with patch(
        "sync_pre_commit_hooks.sync_pyproject_min_versions.check_output",
        side_effect=lambda x: versions_str.encode(),
    ):
        assert not mod.main([
            *(
                [f"--requirements={requirements_path}"]
                if script_lock in {"requirements", "infer"}
                else []
            ),
            f"--script-lock={script_lock}",
            *include_opts,
            *exclude_opts,
            str(toml_or_script_path),
        ])

        out = toml_or_script_path.read_text(encoding="utf-8")

        assert out == expected
