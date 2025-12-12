"""
Fill in `additional_dependencies`` extracted from `pyproject.toml` or `requirements.txt`

Works on single hook.
"""

# pylint: disable=bad-builtin,duplicate-code
from __future__ import annotations

from argparse import ArgumentParser
from functools import cached_property
from itertools import chain
from pathlib import Path
from typing import TYPE_CHECKING, cast

from packaging.requirements import Requirement
from packaging.utils import canonicalize_name

from ._logging import get_logger
from ._utils import (
    add_pre_commit_config_argument,
    add_yaml_arguments,
    get_in,
    pre_commit_config_load,
    pre_commit_config_repo_hook_iter,
)
from .resolve_dependencies import (
    ResolveDependencyGroups,
    ResolveOptionalDependencies,
    canonicalize_requirement,
)

if TYPE_CHECKING:
    from argparse import Namespace
    from collections.abc import (
        Callable,
        Collection,
        Iterable,
        Sequence,
    )
    from typing import Any

    from packaging.utils import NormalizedName

    from ._typing import NormalizedRequirement
    from ._typing_compat import Self


logger = get_logger("fill-pre-commit-deps")


def _limit_requirements(
    deps: Iterable[Requirement], exclude: Collection[str], include: Collection[str]
) -> Iterable[Requirement]:
    if exclude:

        def func_exclude(x: Requirement) -> bool:
            return x.name not in exclude

        deps = filter(func_exclude, deps)

    if include:

        def func_include(x: Requirement) -> bool:
            return x.name in include

        deps = filter(func_include, deps)
    return deps


class ParseDependencies:
    """
    Parse pyproject.toml file for dependencies

    Parameters
    ----------
    data : dict
    """

    def __init__(self, data: dict[str, Any]) -> None:
        self.data = data

    def get_in(
        self, *keys: str, default: Any = None, factory: Callable[[], Any] | None = None
    ) -> Any:
        """Generic getter."""
        return get_in(
            keys=keys, nested_dict=self.data, default=default, factory=factory
        )

    @cached_property
    def package_name(self) -> NormalizedName:
        """Clean name of package."""
        if (out := self.get_in("project", "name")) is None:
            msg = "Must specify `project.name`"
            raise ValueError(msg)
        return canonicalize_name(out)

    @cached_property
    def dependencies(self) -> list[NormalizedRequirement]:
        """project.dependencies"""
        return [
            canonicalize_requirement(Requirement(x))
            for x in self.get_in(
                "project",
                "dependencies",
                factory=list,
            )
        ]

    @cached_property
    def optional_dependencies(self) -> ResolveOptionalDependencies:
        """project.optional-dependencies"""
        return ResolveOptionalDependencies(
            package_name=self.package_name,
            unresolved={
                canonicalize_name(k): list(
                    map(canonicalize_requirement, map(Requirement, v))
                )
                for k, v in self.get_in(
                    "project",
                    "optional-dependencies",
                    factory=dict,
                ).items()
            },
        )

    @cached_property
    def dependency_groups(self) -> ResolveDependencyGroups:
        """dependency-groups"""
        return ResolveDependencyGroups(
            package_name=self.package_name,
            unresolved=cast(
                "dict[str, Any]",
                self.get_in(
                    "dependency-groups",
                    factory=dict,
                ),
            ),
            optional_dependencies=self.optional_dependencies,
        )

    def pip_requirements(
        self,
        extras: Iterable[str],
        groups: Iterable[str],
        no_project_dependencies: bool = False,
    ) -> set[NormalizedRequirement]:
        """Iterator of requirements"""
        out: set[NormalizedRequirement] = (
            set() if no_project_dependencies else set(self.dependencies)
        )
        out.update(self.optional_dependencies[extras])
        out.update(self.dependency_groups[groups])
        return out

    @classmethod
    def from_string(
        cls,
        toml_string: str,
    ) -> Self:
        """Create object from string."""
        from ._compat import tomllib

        data = tomllib.loads(toml_string)
        return cls(data=data)

    @classmethod
    def from_path(cls, path: str | Path) -> Self:
        """Create object from path."""
        from ._compat import tomllib

        with Path(path).open("rb") as f:
            data = tomllib.load(f)
        return cls(data=data)


def parse_requirements_file(
    requirements_path: Path,
) -> set[NormalizedRequirement]:
    """Get list of requirements for requirement.txt file"""
    from requirements import parse

    with requirements_path.open(encoding="utf-8") as f:
        return {canonicalize_requirement(Requirement(req.line)) for req in parse(f)}


def _update_yaml_file(
    path: Path,
    hook_id: str,
    deps: list[str],
    yaml_mapping: int = 2,
    yaml_sequence: int = 4,
    yaml_offset: int = 2,
) -> int:
    if not deps:
        return 0

    loaded, yaml = pre_commit_config_load(
        path, mapping=yaml_mapping, sequence=yaml_sequence, offset=yaml_offset
    )

    updated = False
    for _, hook in pre_commit_config_repo_hook_iter(loaded, include_hook_ids=hook_id):
        logger.info("Updating dependencies of hook %s", hook_id)
        if (seq := hook.get("additional_dependencies")) is not None:
            if seq == deps:
                continue
            seq.clear()
            seq.extend(deps)
        else:
            hook["additional_dependencies"] = deps

        updated = True

    if updated:
        logger.info("Updating %s", path)
        yaml.dump(loaded, path)  # pyright: ignore[reportUnknownMemberType]
        return 1

    return 0


def _get_options(argv: Sequence[str] | None = None) -> Namespace:
    """Get CLI options"""
    parser = ArgumentParser(description=__doc__)
    _ = parser.add_argument(
        "--hook", dest="hook_id", required=True, help="Hook id to apply to."
    )
    # pyproject
    _ = parser.add_argument(
        "-g",
        "--group",
        dest="groups",
        action="append",
        default=[],
        help="Dependency group",
    )
    _ = parser.add_argument(
        "-e",
        "--extra",
        dest="extras",
        action="append",
        default=[],
        help="Optional dependencies (i.e., extras)",
    )
    _ = parser.add_argument(
        "--no-project-dependencies",
        action="store_true",
        help="""
        Do not include `project.dependencies`.  You can still include
        `extras` or `groups`.
        """,
    )
    _ = parser.add_argument(
        "--exclude",
        action="append",
        default=[],
        help="Exclude package.",
    )
    _ = parser.add_argument(
        "--include",
        action="append",
        default=[],
        help="""
        Include package.  Default is to include all packages.  If you
        specify, `--include``, only those packages are included.
        """,
    )
    # requirements
    _ = parser.add_argument(
        "-r",
        "--req",
        "--requirements",
        dest="requirements",
        type=Path,
        default=None,
        help="Requirements file.",
    )
    _ = parser.add_argument(
        "--requirements-exclude",
        dest="requirements_exclude",
        action="append",
        default=[],
        help="Exclude package from read `requirements.txt`.",
    )
    _ = parser.add_argument(
        "--requirements-include",
        dest="requirements_include",
        action="append",
        default=[],
        help="""
        Include package from read `requirements.txt`. Default is to include all
        packages from requirements.txt. If you specify, `--include``, only
        those packages are included.
        """,
    )
    # extra deps
    _ = parser.add_argument(
        "extra_deps",
        nargs="*",
        default=[],
        help="""
        Extra dependencies. These are are prepended to any dependencies found
        from extras/groups/requirements. These should be passed after `"--"``.
        For example, to include an editable package, use `fill-pre-commit-deps
        -g typecheck -- --editable=.``. Note that these dependencies are
        included as is, without any normalization.
        """,
    )

    _ = parser.add_argument(
        "--pyproject",
        type=Path,
        default="pyproject.toml",
        help="pyproject.toml file (Default: 'pyproject.toml')",
    )
    parser = add_pre_commit_config_argument(parser)
    parser = add_yaml_arguments(parser)

    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    """CLI."""
    options = _get_options(argv)

    deps = _limit_requirements(
        deps=ParseDependencies.from_path(options.pyproject).pip_requirements(
            extras=options.extras,
            groups=options.groups,
            no_project_dependencies=options.no_project_dependencies,
        ),
        exclude=options.exclude,
        include=options.include,
    )

    if options.requirements is not None:
        deps_req = _limit_requirements(
            deps=parse_requirements_file(options.requirements),
            exclude=options.requirements_exclude,
            include=options.requirements_include,
        )

        deps = chain(deps, deps_req)

    deps_clean = [*options.extra_deps, *sorted(set(map(str, deps)))]

    return _update_yaml_file(
        path=options.config,
        hook_id=options.hook_id,
        deps=deps_clean,
        yaml_mapping=options.yaml_mapping,
        yaml_sequence=options.yaml_sequence,
        yaml_offset=options.yaml_offset,
    )


if __name__ == "__main__":
    raise SystemExit(main())
