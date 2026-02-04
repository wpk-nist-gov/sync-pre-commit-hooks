from __future__ import annotations

from contextlib import nullcontext
from typing import TYPE_CHECKING

import pytest

from sync_pre_commit_hooks import check_file_extension

if TYPE_CHECKING:
    from typing import Any


@pytest.mark.parametrize(
    ("extensions", "expected"),
    [
        ([".txt", ".xyz"], nullcontext()),
        (["txt"], pytest.raises(ValueError, match=r"Extensions must start .*")),
    ],
)
def test__check_extensions_have_dot(extensions: list[str], expected: Any) -> None:

    with expected:
        _ = check_file_extension._check_extensions_have_dot(extensions)


@pytest.mark.parametrize(
    ("paths", "options", "expected"),
    [
        (["hello.txt", "there"], ["-e.rej"], 0),
        (["hello.txt", "there.rej"], ["-e.rej"], 1),
        (["hello.gz", "hello.tar"], ["-e.tar.gz"], 0),
        (["hello.gz", "hello.tar", "there.tar.gz"], ["-e.tar.gz"], 1),
    ],
)
def test_main(paths: list[str], options: list[str], expected: bool) -> None:

    assert check_file_extension.main([*options, *paths]) == expected
