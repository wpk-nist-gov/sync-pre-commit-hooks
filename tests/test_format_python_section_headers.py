from __future__ import annotations

from dataclasses import asdict
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

import sync_pre_commit_hooks.format_python_section_headers as mod

if TYPE_CHECKING:
    from typing import Any


@pytest.mark.parametrize(
    ("contents", "line_length", "out"),
    [
        ("hello there ---", None, None),
        ("# hello there -", None, None),
        ("# * hello there", None, None),
        ("# * hello there -", None, "# * hello there -".ljust(88, "-")),
        ("# * hello there -", 5, None),
        ("# * hello there -----", 21, None),
        ("## * hello there -", None, None),
        ("# *   hello there  -", 70, "# * hello there -".ljust(70, "-")),
        ("# *   hello there  ", None, None),
        ("     #*   hello there  -", None, "     # * hello there -".ljust(88, "-")),
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
        (
            [],
            "# *   hello there  -",
            "# * hello there -".ljust(88, "-"),
        ),
        (
            ["--dry-run"],
            "# *   hello there  -",
            "# *   hello there  -",
        ),
        (
            ["--line-length", "70"],
            "# *   hello there  -",
            "# * hello there -".ljust(70, "-"),
        ),
    ],
)
def test_main(tmp_path: Path, argv: list[str], contents: str, expected: str) -> None:

    path = tmp_path / "hello.py"
    path.write_text(contents)

    mod.main([*argv, str(path)])

    assert path.read_text(encoding="utf-8") == expected
