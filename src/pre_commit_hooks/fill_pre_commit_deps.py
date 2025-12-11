"""
Fill in `additional_dependencies`` extracted from `pyproject.toml` or `requirements.txt`

Works on single hook.
"""

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
from ruamel.yaml import YAML

from ._logging import get_logger
from ._utils import add_yaml_arguments, get_in, get_python_version

if TYPE_CHECKING:
    from argparse import Namespace
    from collections.abc import (
        Callable,
        Collection,
        Iterable,
        Mapping,
        Sequence,
    )
    from typing import Any, NewType

    from packaging.utils import NormalizedName

    from ._typing_compat import Self

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
        init=False, default_factory=dict["NormalizedName", "set[NormalizedRequirement]"]
    )

    @abstractmethod
    def _get_unresolved_deps(
        self, key: NormalizedName
    ) -> Iterable[NormalizedRequirement]: ...

    @abstractmethod
    def _get_resolved_package_extras(
        self, extras: Iterable[NormalizedName]
    ) -> Iterable[NormalizedRequirement]: ...

    def _resolve(self, key: NormalizedName) -> set[NormalizedRequirement]:
        """Do underlying resolve of normalized group/extra"""
        if key in self.resolved:
            return self.resolved[key]

        resolved: set[NormalizedRequirement] = set()
        for dep in self._get_unresolved_deps(key):
            if dep in resolved:
                continue
            if dep.name == self.package_name:
                resolved.update(
                    self._get_resolved_package_extras(
                        map(canonicalize_name, dep.extras)
                    )
                )
            else:
                resolved.add(dep)

        self.resolved[key] = resolved
        return resolved

    def __getitem__(self, key: str | Iterable[str]) -> set[NormalizedRequirement]:
        if isinstance(key, str):
            key = [key]

        out: set[NormalizedRequirement] = set()
        for k in map(canonicalize_name, key):
            out.update(self._resolve(k))
        return out


@dataclass
class _ResolveOptionalDependencies(_Resolve):
    unresolved: Mapping[NormalizedName, Sequence[NormalizedRequirement]]  # type: ignore[assignment]  # pyright: ignore[reportIncompatibleVariableOverride]

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
        yield from self.optional_dependencies[extras]


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
            _canonicalize_requirement(Requirement(x))
            for x in self.get_in(
                "project",
                "dependencies",
                factory=list,
            )
        ]

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
        return {_canonicalize_requirement(Requirement(req.line)) for req in parse(f)}


def _update_yaml_file(
    path: Path,
    hook_id: str,
    deps: list[str],
    python_version: str | None = None,
    yaml_mapping: int = 2,
    yaml_sequence: int = 4,
    yaml_offset: int = 2,
) -> int:
    if not deps and python_version is None:
        return 0

    yaml = YAML()
    yaml.preserve_quotes = True
    yaml.indent(yaml_mapping, yaml_sequence, yaml_offset)  # pyright: ignore[reportUnknownMemberType]

    with path.open(encoding="utf-8") as f:
        loaded: dict[str, Any] = yaml.load(f)  # pyright: ignore[reportUnknownVariableType,reportUnknownMemberType]

    updated = False
    for repo in loaded["repos"]:  # pyright: ignore[reportUnknownVariableType]  # noqa: PLR1702
        for hook in repo["hooks"]:  # pyright: ignore[reportUnknownVariableType]
            if hook["id"] == hook_id:
                if deps:
                    logger.info("Updating dependencies of hook %s", hook_id)
                    if (seq := hook.get("additional_dependencies")) is not None:  # pyright: ignore[reportUnknownVariableType,reportUnknownMemberType]
                        if seq != deps:
                            seq.clear()  # pyright: ignore[reportUnknownMemberType]
                            seq.extend(deps)  # pyright: ignore[reportUnknownMemberType]
                            updated = True
                    else:
                        hook["additional_dependencies"] = deps
                        updated = True

                if (
                    python_version is not None
                    and (language_version := hook.get("language_version")) is not None  # pyright: ignore[reportUnknownVariableType, reportUnknownMemberType]
                    and python_version != language_version
                ):
                    logger.info(
                        "Updating hook %s language_version to %s",
                        hook_id,
                        python_version,
                    )
                    hook["language_version"] = python_version
                    updated = True

    if updated:
        logger.info("Updating %s", path)
        with path.open("w", encoding="utf-8") as f:
            yaml.dump(loaded, f)  # pyright: ignore[reportUnknownMemberType]
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
        "--requirements-exclude",
        dest="requirements_exclude",
        action="append",
        default=[],
        help="Exclude package from read `requirements.txt`.",
    )
    parser.add_argument(
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
    # python version (language_version)
    parser.add_argument(
        "--python-version",
        default=None,
        help="""
        Update `language_version` to this value.
        Overrides ``--python-version-file``.
        Note that `hook` must already have to key ``language_version`` for this to take effect.
        """,
    )
    parser.add_argument(
        "--python-version-file",
        default=None,
        type=Path,
        help="""
        Update ``language_version`` to value read from file.  For example, ``--python-version-file=".python-version"``.
        Note that `hook` must already have to key ``language_version`` for this to take effect.
        """,
    )

    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    """CLI."""
    options = get_options(argv)

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

    python_version = (
        None
        if options.python_version is None and options.python_version_file is None
        else get_python_version(
            options.python_version, options.python_version_file, logger
        )
    )

    return _update_yaml_file(
        path=options.config,
        hook_id=options.hook_id,
        deps=deps_clean,
        python_version=python_version,
        yaml_mapping=options.yaml_mapping,
        yaml_sequence=options.yaml_sequence,
        yaml_offset=options.yaml_offset,
    )


if __name__ == "__main__":
    raise SystemExit(main())
