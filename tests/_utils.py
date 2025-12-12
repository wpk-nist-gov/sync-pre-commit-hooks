from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path


def create_config_file(
    parent: Path, contents: str, name: str = ".pre-commit-config.yaml"
) -> Path:
    cfg = parent / name
    cfg.write_text(contents)

    return cfg
