"""
Console script (:mod:`~pre_commit_hooks.cli`)
==========================================================
"""

import argparse
import sys

PACKAGE = "pre_commit_hooks"


def get_parser() -> argparse.ArgumentParser:
    """Create parser."""
    parser = argparse.ArgumentParser()
    parser.add_argument("_", nargs="*")

    return parser


def main() -> int:
    """Console script for pre_commit_hooks."""
    parser = get_parser()
    args = parser.parse_args()

    print("Arguments: " + str(args._))  # noqa: T201
    print(f"Replace this message by putting your code into {PACKAGE}.cli.main")  # noqa: T201
    return 0


if __name__ == "__main__":
    sys.exit(main())  # pragma: no cover
