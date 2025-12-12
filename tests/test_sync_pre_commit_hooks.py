"""Tests for `sync-pre-commit-hooks` package."""

from __future__ import annotations


def test_version() -> None:
    from sync_pre_commit_hooks import __version__

    assert __version__ != "999"
