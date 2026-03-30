"""Tests for `sync-pre-commit-hooks` package."""

from __future__ import annotations

import re


def test_version() -> None:
    from sync_pre_commit_hooks import __version__

    assert isinstance(__version__, str)
    assert re.match(r"^\d+\.\d+\.\d+.*$", __version__) is not None
