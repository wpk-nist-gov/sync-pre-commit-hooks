"""Tests for `sync-pre-commit-hooks` package."""

from __future__ import annotations

<<<<<<< before updating
=======
import re

import pytest

from sync_pre_commit_hooks import example_function

>>>>>>> after updating

def test_version() -> None:
    from sync_pre_commit_hooks import __version__

<<<<<<< before updating
    assert __version__ != "999"
=======
    assert isinstance(__version__, str)
    assert re.match(r"^\d+\.\d+\.\d+.*$", __version__) is not None


@pytest.fixture
def response() -> tuple[int, int]:
    return 1, 2


def test_example_function(response: tuple[int, int]) -> None:
    expected = 3
    assert example_function(*response) == expected


def test_command_line_interface() -> None:
    from sync_pre_commit_hooks import cli

    assert not cli.main([])
>>>>>>> after updating
