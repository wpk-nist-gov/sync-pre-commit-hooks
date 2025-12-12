# pyright: reportUnreachable=false
from __future__ import annotations

import sys

if sys.version_info >= (3, 11):
    from typing import Required, Self
else:
    from typing_extensions import Required, Self


if sys.version_info >= (3, 12):
    from typing import override
else:
    from typing_extensions import override


__all__ = ["Required", "Self", "override"]
