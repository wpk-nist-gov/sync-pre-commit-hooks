"""Update ``additional_dependencies`` in ``.pre-commit-config.yaml``"""

# NOTE: adapted from https://github.com/pre-commit/sync-pre-commit-deps
# ruff: noqa: D103
from __future__ import annotations

from argparse import ArgumentParser
from functools import lru_cache
from pathlib import Path
from typing import TYPE_CHECKING, Any, cast

from ._logging import get_logger
from ._utils import add_yaml_arguments, get_yaml

if TYPE_CHECKING:
    from collections.abc import Container, Sequence

ID_TO_PACKAGE = ["ruff-format:ruff", "ruff-check:ruff"]

logger = get_logger("sync-pre-commit-deps")


def _get_versions_from_ids(
    loaded: dict[str, Any],
    hook_ids_from: Container[str],
    id_to_package_mapping: dict[str, str],
) -> dict[str, str]:
    versions: dict[str, str] = {}
    for repo in loaded["repos"]:
        if repo["repo"] not in {"local", "meta"}:
            for hook in repo["hooks"]:
                if (hid := hook["id"]) in hook_ids_from:
                    # `mirrors-mypy` uses versions with a 'v' prefix, so we
                    # have to strip it out to get the mypy version.
                    cleaned_rev = repo["rev"].removeprefix("v")
                    key: str = id_to_package_mapping.get(hid, hid)  # pyright: ignore[reportAssignmentType]
                    versions[key] = cleaned_rev

    return versions


@lru_cache
def _get_versions_from_requirements(
    requirements_path: Path | None,
) -> dict[str, str]:
    if requirements_path is None:
        return {}

    from requirements import parse

    versions: dict[str, str] = {}
    with requirements_path.open(encoding="utf-8") as f:
        for requirement in parse(f):
            versions[requirement.name] = requirement.specs[0][-1]  # type: ignore[index]  # pyright: ignore[reportArgumentType]
    return versions


@lru_cache
def _get_version_from_lastversion(dep: str) -> str:
    from lastversion import (
        latest,
    )

    return cast("str", latest(dep, output_format="tag"))


def _get_versions_from_lastversion(dependencies: Sequence[str]) -> dict[str, Any]:
    return {dep: _get_version_from_lastversion(dep) for dep in dependencies}


def _get_hook_ids(loaded: dict[str, Any]) -> list[str]:
    out: list[str] = []
    for repo in loaded["repos"]:
        if repo["repo"] not in {"local", "meta"}:
            out.extend(hook["id"] for hook in repo["hooks"])
    return out


def _limit_hooks(
    hook_ids: Sequence[str],
    include: Sequence[str],
    exclude: Sequence[str],
) -> list[str]:
    include = include or hook_ids
    return [x for x in include if x not in exclude]


def _parse_id_to_dep(id_to_package: Sequence[str]) -> dict[str, str]:
    out: dict[str, str] = {}
    for x in id_to_package:
        hid, sep, package = x.partition(":")
        if sep != ":":
            msg = f"hook id to dep str {x} does not have form `id:dep`"
            raise ValueError(msg)
        out[hid.strip()] = package.strip()
    return out


def _process_file(
    path: Path,
    yaml_mapping: int,
    yaml_sequence: int,
    yaml_offset: int,
    to_include: Sequence[str],
    to_exclude: Sequence[str],
    from_include: Sequence[str],
    from_exclude: Sequence[str],
    requirements: Path | None,
    lastversion_dependencies: Sequence[str],
    id_to_package_mapping: dict[str, str],
) -> int:
    yaml = get_yaml(yaml_mapping, yaml_sequence, yaml_offset)
    with path.open(encoding="utf-8") as f:
        loaded: dict[str, Any] = yaml.load(f)

    hook_ids = _get_hook_ids(loaded)
    hook_ids_update = _limit_hooks(hook_ids, include=to_include, exclude=to_exclude)
    hook_ids_from = _limit_hooks(hook_ids, include=from_include, exclude=from_exclude)

    versions = _get_versions_from_ids(loaded, hook_ids_from, id_to_package_mapping)
    versions.update(_get_versions_from_requirements(requirements))
    versions.update(_get_versions_from_lastversion(lastversion_dependencies))

    updated = False
    for repo in loaded["repos"]:  # noqa: PLR1702 # pylint: disable=too-many-nested-blocks
        for hook in repo["hooks"]:
            if hook["id"] in hook_ids_update:
                for i, dep in enumerate(hook.get("additional_dependencies", ())):
                    name, _, cur_version = dep.partition("==")
                    if (
                        target_version := versions.get(name, cur_version)
                    ) != cur_version:
                        name_and_version = type(dep)(f"{name}=={target_version}")
                        if hasattr(dep, "anchor"):
                            name_and_version.yaml_set_anchor(
                                dep.anchor.value, always_dump=True
                            )

                        hook["additional_dependencies"][i] = name_and_version
                        logger.info(
                            "Setting %s dependency %s to %s",
                            hook["id"],
                            name,
                            target_version,
                        )
                        updated = True

    if updated:
        with path.open("w+", encoding="utf-8") as f:
            yaml.dump(loaded, f)
        return 1

    return 0


def _get_parser() -> ArgumentParser:
    parser = ArgumentParser(description=__doc__)
    parser = add_yaml_arguments(parser)
    parser.add_argument(
        "paths",
        type=Path,
        nargs="*",
        help="The pre-commit config file to sync to.",
    )

    # hook id to extract from
    parser.add_argument(
        "--from",
        dest="from_include",
        action="append",
        default=[],
        help="""
        Hook id's to extract versions from. The default is to extract from all
        hooks. If pass ``--from id``, then only those hooks explicitly passed
        will be used to extract versions.
        """,
    )
    parser.add_argument(
        "--from-exclude",
        action="append",
        default=[],
        help="Hook id's to exclude extracting from.",
    )
    # hook id's to update
    parser.add_argument(
        "--to",
        dest="to_include",
        action="append",
        default=[],
        help="""
        Hook id's to allow update of additional_dependencies. The default is to
        allow updates to all hook id's additional_dependencies. If pass ``--to
        id``, then only those hooks explicitly passed will be updated.
        """,
    )
    parser.add_argument(
        "--to-exclude",
        action="append",
        default=[],
        help="Hook id's to exclude updating.",
    )
    parser.add_argument(
        "-r",
        "--requirements",
        type=Path,
        default=None,
        help="Requirements file to lookup pinned requirements to update.",
    )
    # use lastversion?
    parser.add_argument(
        "-l",
        "--last",
        dest="lastversion_dependencies",
        action="append",
        default=[],
        help="""
        Dependencies to lookup using `lastversion`. Requires network access and
        `lastversion` to be installed.
        """,
    )
    parser.add_argument(
        "-m",
        "--id-dep",
        type=str,
        action="append",
        default=ID_TO_PACKAGE,
        help=f"""
        Colon separated hook id to dependency mapping (``{{hook_id}}:{{dependency}}``).
        For example, to map the ``ruff-check`` hook to ``ruff``,
        pass ``-m 'ruff-check:ruff'. (Default: {ID_TO_PACKAGE})
        """,
    )

    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = _get_parser()
    args = parser.parse_args(argv)
    paths: list[Path] = args.paths or [Path(".pre-commit-config.yaml")]

    out = 0
    for path in paths:
        out += _process_file(
            path,
            yaml_mapping=args.yaml_mapping,
            yaml_sequence=args.yaml_sequence,
            yaml_offset=args.yaml_offset,
            to_include=args.to_include,
            to_exclude=args.to_exclude,
            from_include=args.from_include,
            from_exclude=args.from_exclude,
            requirements=args.requirements,
            lastversion_dependencies=args.lastversion_dependencies,
            id_to_package_mapping=_parse_id_to_dep(args.id_dep),
        )

    return out


if __name__ == "__main__":
    raise SystemExit(main())
