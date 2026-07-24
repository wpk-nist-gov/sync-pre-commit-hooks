"""
Top level API (:mod:`sync_pre_commit_hooks`)
============================================
"""

from importlib.metadata import PackageNotFoundError
from importlib.metadata import version as _version

<<<<<<< before updating
try:  # noqa: RUF067
=======
from .core import example_function

try:  # ruff:ignore[non-empty-init-module]
>>>>>>> after updating
    __version__ = _version("sync-pre-commit-hooks")
except PackageNotFoundError:  # pragma: no cover
    __version__ = "999"


__author__ = """William P. Krekelberg"""


__all__ = [
    "__version__",
]
