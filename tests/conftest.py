from __future__ import annotations

import os
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from collections.abc import Iterator


@pytest.fixture
def example_path(tmp_path: Path) -> Iterator[Path]:
    old_cwd = Path.cwd()
    os.chdir(tmp_path)
    yield tmp_path
    os.chdir(old_cwd)
