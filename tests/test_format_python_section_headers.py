from __future__ import annotations

from dataclasses import asdict
from pathlib import Path
from textwrap import dedent
from typing import TYPE_CHECKING

import pytest

import sync_pre_commit_hooks.format_python_section_headers as mod

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
        (["hello.txt"], {"paths": ["hello.txt"]}),
        (
            ["--line-length", "70", "--dry-run", "hello.txt", "there.py"],
            {"paths": ["hello.txt", "there.py"], "line_length": 70, "dry_run": True},
        ),
    ],
)
def test__get_options(argv: list[str], expected: dict[str, Any]) -> None:

    expected.setdefault("line_length", 88)
    expected.setdefault("dry_run", False)
    expected["paths"] = [Path(x) for x in expected["paths"]]

    assert asdict(mod._get_options(argv)) == expected


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

            # * get args ---------------------------------------------------------------

            there
            """),
            dedent("""
            hello

            # * get args ---------------------------------------------------------------

            there
            """),
            id="multi line",
        ),
    ],
)
def test_main(tmp_path: Path, argv: list[str], contents: str, expected: str) -> None:

    path = tmp_path / "hello.py"
    path.write_text(contents)

    mod.main([*argv, str(path)])

    assert path.read_text(encoding="utf-8") == expected
