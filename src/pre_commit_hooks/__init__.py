"""
Top level API (:mod:`pre_commit_hooks`)
=======================================
"""

from importlib.metadata import PackageNotFoundError
from importlib.metadata import version as _version

try:
    __version__ = _version("pre-commit-hooks")
except PackageNotFoundError:  # pragma: no cover
    __version__ = "999"


__author__ = """William P. Krekelberg"""
__email__ = "wpk@nist.gov"


__all__ = [
    "__version__",
]
