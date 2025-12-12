from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import call, patch

import pytest

from sync_pre_commit_hooks import apply_command

if TYPE_CHECKING:
    from collections.abc import Sequence


@pytest.mark.parametrize(
    ("return_value", "return_code"),
    [
        (0, 0),
        (1, 2),
    ],
)
@pytest.mark.parametrize(
    ("argv", "files", "command"),
    [
        pytest.param(
            ["just", "--fmt"],
            ["a", "b"],
            ["just", "--fmt"],
            id="separate",
        ),
        pytest.param(["just --fmt"], ["a", "b"], ["just", "--fmt"], id="combined"),
    ],
)
def test_main(
    argv: Sequence[str],
    files: Sequence[str],
    command: Sequence[str],
    return_value: int,
    return_code: int,
) -> None:
    with patch("subprocess.call", return_value=return_value) as mocked_call:
        assert apply_command.main([*argv, *files]) == return_code

        assert mocked_call.call_args_list == [
            call((*command, str(file))) for file in files
        ]
