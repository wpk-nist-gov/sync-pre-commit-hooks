# pyright: reportUnreachable=false
from __future__ import annotations

import sys
from typing import NotRequired, Required, Self

if sys.version_info >= (3, 12):
    from typing import override
else:
    from typing_extensions import override


__all__ = ["NotRequired", "Required", "Self", "override"]
