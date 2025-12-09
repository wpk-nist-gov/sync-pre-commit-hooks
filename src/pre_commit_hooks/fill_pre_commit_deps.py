"""
Fill in `additional_dependencies`` extracted from `pyproject.toml` or `requirements.txt`

Works on single hook.
"""

# ruff: noqa: DOC402
# pylint: disable=bad-builtin,missing-class-docstring,duplicate-code
from __future__ import annotations

from abc import ABC, abstractmethod
from argparse import ArgumentParser
from dataclasses import dataclass, field
from functools import cached_property
from itertools import chain
from pathlib import Path
from typing import TYPE_CHECKING, cast

from dependency_groups import DependencyGroupResolver
from packaging.requirements import Requirement
from packaging.utils import canonicalize_name

from ._logging import get_logger
from ._utils import add_yaml_arguments, get_in, get_yaml

if TYPE_CHECKING:
    from argparse import Namespace
    from collections.abc import (
        Callable,
        Collection,
        Iterable,
        Iterator,
        Mapping,
        Sequence,
    )
    from typing import Any, NewType, Self

    from packaging.utils import NormalizedName

    NormalizedRequirement = NewType("NormalizedRequirement", Requirement)


logger = get_logger("fill-pre-commit-deps")


# Not used, but keep for posterity
# def _resolve_requirements(  # pragma: no cover
#     requirements: Iterable[Requirement],
#     package_name: str,
#     optional_dependencies: dict[str, list[Requirement]],
# ) -> Iterator[Requirement]:
#     for requirement in requirements:
#         if requirement.name == package_name:
#             for extra in requirement.extras:
#                 yield from _resolve_requirements(
#                     optional_dependencies[extra], package_name, optional_dependencies  # noqa: ERA001
#                 )  # noqa: ERA001,RUF100
#         else:  # noqa: ERA001
#             yield requirement


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


def _canonicalize_requirement(dep: Requirement) -> NormalizedRequirement:
    dep.name = canonicalize_name(dep.name)
    dep.extras = {canonicalize_name(e) for e in dep.extras}
    return cast("NormalizedRequirement", dep)


@dataclass
class _Resolve(ABC):
    package_name: NormalizedName
    unresolved: Mapping[str, Any]
    resolved: dict[NormalizedName, set[NormalizedRequirement]] = field(
        init=False, default_factory=dict
    )

    @abstractmethod
    def _get_unresolved_deps(
        self, key: NormalizedName
    ) -> Iterable[NormalizedRequirement]: ...

    @abstractmethod
    def _get_resolved_package_extras(
        self, extras: Iterable[NormalizedName]
    ) -> Iterable[NormalizedRequirement]: ...

    def _resolve(self, key: NormalizedName) -> Iterator[NormalizedRequirement]:
        """Do underlying resolve of normalized group/extra"""
        if key in self.resolved:
            yield from self.resolved[key]
        else:
            for dep in self._get_unresolved_deps(key):
                if dep.name == self.package_name:
                    yield from self._get_resolved_package_extras(
                        map(canonicalize_name, dep.extras)
                    )
                else:
                    yield dep

    def get(self, key: str | Iterable[str]) -> Iterator[NormalizedRequirement]:
        if isinstance(key, str):
            key = [key]

        for extra in map(canonicalize_name, key):
            if extra in self.resolved:
                yield from self.resolved[extra]
            else:
                val = self.resolved[extra] = set(self._resolve(extra))
                yield from val


@dataclass
class _ResolveOptionalDependencies(_Resolve):
    unresolved: Mapping[NormalizedName, Sequence[NormalizedRequirement]]

    def _get_unresolved_deps(
        self, key: NormalizedName
    ) -> Iterable[NormalizedRequirement]:
        yield from self.unresolved[key]

    def _get_resolved_package_extras(
        self, extras: Iterable[NormalizedName]
    ) -> Iterable[NormalizedRequirement]:
        for e in extras:
            yield from self._resolve(e)


@dataclass
class _ResolveDependencyGroups(_Resolve):
    optional_dependencies: _ResolveOptionalDependencies
    _resolver: DependencyGroupResolver = field(init=False)

    def __post_init__(self) -> None:
        self._resolver = DependencyGroupResolver(self.unresolved)

    def _get_unresolved_deps(
        self, key: NormalizedName
    ) -> Iterable[NormalizedRequirement]:
        return map(_canonicalize_requirement, self._resolver.resolve(key))

    def _get_resolved_package_extras(
        self, extras: Iterable[NormalizedName]
    ) -> Iterable[NormalizedRequirement]:
        yield from self.optional_dependencies.get(extras)


class ParseDepends:
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
        return list(
            map(
                _canonicalize_requirement,
                self.get_in(
                    "project",
                    "dependencies",
                    factory=list,
                ),
            )
        )

    @cached_property
    def optional_dependencies(self) -> _ResolveOptionalDependencies:
        """project.optional-dependencies"""
        return _ResolveOptionalDependencies(
            package_name=self.package_name,
            unresolved={
                canonicalize_name(k): list(
                    map(_canonicalize_requirement, map(Requirement, v))
                )
                for k, v in self.get_in(
                    "project",
                    "optional-dependencies",
                    factory=dict,
                ).items()
            },
        )

    @cached_property
    def dependency_groups(self) -> _ResolveDependencyGroups:
        """dependency-groups"""
        return _ResolveDependencyGroups(
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
    ) -> Iterator[NormalizedRequirement]:
        """Iterator of requirements"""
        if not no_project_dependencies:
            yield from self.dependencies

        yield from self.optional_dependencies.get(extras)
        yield from self.dependency_groups.get(groups)

    @classmethod
    def from_string(
        cls,
        toml_string: str,
    ) -> Self:
        """Create object from string."""
        import tomllib

        data = tomllib.loads(toml_string)
        return cls(data=data)

    @classmethod
    def from_path(cls, path: str | Path) -> Self:
        """Create object from path."""
        import tomllib

        with Path(path).open("rb") as f:
            data = tomllib.load(f)
        return cls(data=data)


def parse_requirements_file(
    requirements_path: Path,
) -> Iterator[NormalizedRequirement]:
    """Get list of requirements for requirement.txt file"""
    from requirements import parse

    with requirements_path.open(encoding="utf-8") as f:
        for req in parse(f):
            yield _canonicalize_requirement(Requirement(req.line))


def _update_yaml_file(
    path: Path,
    hook_id: str,
    deps: list[str],
    yaml_mapping: int = 2,
    yaml_sequence: int = 4,
    yaml_offset: int = 2,
) -> int:
    yaml = get_yaml(yaml_mapping, yaml_sequence, yaml_offset)
    with path.open(encoding="utf-8") as f:
        loaded: dict[str, Any] = yaml.load(f)

    updated = False
    for repo in loaded["repos"]:
        for hook in repo["hooks"]:
            if hook["id"] == hook_id:
                if "additional_dependencies" in hook:
                    seq = hook["additional_dependencies"]
                    seq.clear()
                    seq.extend(deps)
                else:
                    hook["additional_dependencies"] = deps
                updated = True

    if updated:
        with path.open("w", encoding="utf-8") as f:
            yaml.dump(loaded, f)
        return 1

    return 0


def get_options(argv: Sequence[str] | None = None) -> Namespace:
    """Get CLI options"""
    parser = ArgumentParser(description=__doc__)
    parser = add_yaml_arguments(parser)
    parser.add_argument(
        "--config",
        type=Path,
        default=".pre-commit-config.yaml",
        help="pre-commit config file (Default '.pre-commit-config.yaml')",
    )
    parser.add_argument(
        "--hook", dest="hook_id", required=True, help="Hook id to apply to."
    )
    # pyproject
    parser.add_argument(
        "--pyproject",
        type=Path,
        default="pyproject.toml",
        help="pyproject.toml file (Default: 'pyproject.toml')",
    )
    parser.add_argument(
        "-g",
        "--group",
        dest="groups",
        action="append",
        default=[],
        help="Dependency group",
    )
    parser.add_argument(
        "-e",
        "--extra",
        dest="extras",
        action="append",
        default=[],
        help="Optional dependencies (i.e., extras)",
    )
    parser.add_argument(
        "--no-project-dependencies",
        action="store_true",
        help="""
        Do not include `project.dependencies`.  You can still include
        `extras` or `groups`.
        """,
    )
    parser.add_argument(
        "--exclude",
        action="append",
        default=[],
        help="Exclude package.",
    )
    parser.add_argument(
        "--include",
        action="append",
        default=[],
        help="""
        Include package.  Default is to include all packages.  If you
        specify, `--include``, only those packages are included.
        """,
    )
    # requirements
    parser.add_argument(
        "-r",
        "--req",
        "--requirements",
        dest="requirements",
        type=Path,
        default=None,
        help="Requirements file.",
    )
    parser.add_argument(
        "--req-exclude",
        action="append",
        default=[],
        help="Exclude package from read `requirements.txt`.",
    )
    parser.add_argument(
        "--req-include",
        action="append",
        default=[],
        help="""
        Include package from read `requirements.txt`. Default is to include all
        packages from requirements.txt. If you specify, `--include``, only
        those packages are included.
        """,
    )
    # extra deps
    parser.add_argument(
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

    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    """CLI."""
    options = get_options(argv)

    deps = _limit_requirements(
        deps=ParseDepends.from_path(options.pyproject).pip_requirements(
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
            exclude=options.req_exclude,
            include=options.req_include,
        )

        deps = chain(deps, deps_req)

    deps_clean = [*options.extra_deps, *sorted(set(map(str, deps)))]

    _update_yaml_file(
        path=options.config,
        hook_id=options.hook_id,
        deps=deps_clean,
        yaml_mapping=options.yaml_mapping,
        yaml_sequence=options.yaml_sequence,
        yaml_offset=options.yaml_offset,
    )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
