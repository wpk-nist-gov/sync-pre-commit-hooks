"""
Fill in ``additional_dependencies`` extracted from `pyproject.toml` or `requirements.txt`

Works on single hook.
"""

from __future__ import annotations

from argparse import ArgumentParser
from functools import cached_property
from pathlib import Path
from typing import TYPE_CHECKING, cast

from packaging.requirements import Requirement

from ._logging import get_logger
from ._utils import add_yaml_arguments, get_in

if TYPE_CHECKING:
    from argparse import Namespace
    from collections.abc import Callable, Container, Iterable, Sequence
    from typing import Any, Self

logger = get_logger("fill-pre-commit-deps")


def _resolve_extras(
    *,
    extras: str | Iterable[str],
    package_name: str,
    unresolved: dict[str, list[Requirement]],
) -> list[Requirement]:
    """Resolve extras"""
    if isinstance(extras, str):
        extras = [extras]

    out: list[Requirement] = []
    for extra in extras:
        for requirement in unresolved[extra]:
            if requirement.name == package_name:
                out.extend(
                    _resolve_extras(
                        extras=requirement.extras,
                        package_name=package_name,
                        unresolved=unresolved,
                    )
                )
            else:
                out.append(requirement)
    return out


def _resolve_group(
    requirements: list[Requirement],
    package_name: str,
    extras: dict[str, list[Requirement]],
) -> list[Requirement]:
    """Resolve project.name[extra] in a group"""
    out: list[Requirement] = []
    for requirement in requirements:
        if requirement.name == package_name:
            for extra in requirement.extras:
                out.extend(extras[extra])
        else:
            out.append(requirement)

    return out


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
    def package_name(self) -> str:
        """Clean name of package."""
        if (out := self.get_in("project", "name")) is None:
            msg = "Must specify `project.name`"
            raise ValueError(msg)
        return cast("str", out)

    @cached_property
    def dependencies(self) -> list[str]:
        """project.dependencies"""
        return cast(
            "list[str]",
            self.get_in(
                "project",
                "dependencies",
                factory=list,
            ),
        )

    @cached_property
    def optional_dependencies(self) -> dict[str, Any]:
        """project.optional-dependencies"""
        return cast(
            "dict[str, Any]",
            self.get_in(
                "project",
                "optional-dependencies",
                factory=dict,
            ),
        )

    @cached_property
    def dependency_groups(self) -> dict[str, Any]:
        """dependency-groups"""
        return cast(
            "dict[str, Any]",
            self.get_in(
                "dependency-groups",
                factory=dict,
            ),
        )

    @cached_property
    def requirements_base(self) -> list[Requirement]:
        """Base requirements"""
        return [Requirement(x) for x in self.dependencies]

    @cached_property
    def requirements_extras(self) -> dict[str, list[Requirement]]:
        """Extras requirements"""
        unresolved: dict[str, list[Requirement]] = {
            k: [Requirement(x) for x in v]
            for k, v in self.optional_dependencies.items()
        }

        resolved: dict[str, list[Requirement]] = {
            extra: _resolve_extras(
                extras=extra, package_name=self.package_name, unresolved=unresolved
            )
            for extra in unresolved
        }

        return resolved

    @cached_property
    def requirements_groups(self) -> dict[str, list[Requirement]]:
        """Groups requirements"""
        from dependency_groups import resolve

        unresolved: dict[str, list[Requirement]] = {
            group: [Requirement(x) for x in resolve(self.dependency_groups, group)]
            for group in self.dependency_groups
        }

        resolved: dict[str, list[Requirement]] = {
            group: _resolve_group(
                requirements, self.package_name, self.requirements_extras
            )
            for group, requirements in unresolved.items()
        }

        return resolved

    def _get_requirements(
        self,
        extras: Iterable[str],
        groups: Iterable[str],
        no_project_dependencies: bool = False,
    ) -> list[Requirement]:
        out: list[Requirement] = []

        if not no_project_dependencies:
            out.extend(self.requirements_base)

        def _extend_extra_or_group(
            extras: Iterable[str],
            requirements_mapping: dict[str, list[Requirement]],
        ) -> None:
            for extra in extras:
                out.extend(requirements_mapping[extra])

        _extend_extra_or_group(extras, self.requirements_extras)
        _extend_extra_or_group(groups, self.requirements_groups)

        return out

    def pip_requirements(
        self,
        *,
        extras: Iterable[str],
        groups: Iterable[str],
        no_project_dependencies: bool = False,
        exclude: Container[str] = (),
    ) -> list[str]:
        """Pip dependencies."""
        return sorted(
            {
                str(requirement)
                for requirement in self._get_requirements(
                    extras=extras,
                    groups=groups,
                    no_project_dependencies=no_project_dependencies,
                )
                if requirement.name not in exclude
            }
        )

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
    exclude: Container[str],
) -> list[str]:
    """Get list of requirements for requirement.txt file"""
    from requirements import parse

    with requirements_path.open(encoding="utf-8") as f:
        reqs = {Requirement(req.line) for req in parse(f)}

    return sorted({str(req) for req in reqs if req.name not in exclude})


def _update_yaml_file(
    path: Path,
    hook_id: str,
    deps: list[str],
    yaml_mapping: int = 2,
    yaml_sequence: int = 4,
    yaml_offset: int = 2,
) -> int:
    import ruamel.yaml

    yaml = ruamel.yaml.YAML()
    yaml.preserve_quotes = True
    yaml.indent(yaml_mapping, yaml_sequence, yaml_offset)
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
        "--hook", dest="hook_id", required=True, help="Hook id to apply to."
    )
    parser.add_argument(
        "--pyproject",
        type=Path,
        default="pyproject.toml",
        help="pyproject.toml file (Default: 'pyproject.toml')",
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=".pre-commit-config.yaml",
        help="pre-commit config file (Default '.pre-commit-config.yaml')",
    )
    parser.add_argument(
        "-r", "--requirements", type=Path, default=None, help="Requirements file."
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
        "--exclude", action="append", default=[], help="Exclude package."
    )
    parser.add_argument(
        "extra_deps",
        nargs="*",
        default=[],
        help="""
        Extra dependencies.  These are are prepended to any dependencies
        found from extras/groups/requirements.  These should be passed
        after ``"--"``.  For example, to include an editable package, use
        ``fill-pre-commit-deps -g typecheck -- --editable=.``.
        """,
    )

    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    """CLI."""
    options = get_options(argv)

    if options.requirements is not None:
        deps = parse_requirements_file(options.requirements, options.exclude)

    else:
        deps = ParseDepends.from_path(options.pyproject).pip_requirements(
            extras=options.extras,
            groups=options.groups,
            no_project_dependencies=options.no_project_dependencies,
            exclude=options.exclude,
        )

    deps = [*options.extra_deps, *deps]

    _update_yaml_file(
        path=options.config,
        hook_id=options.hook_id,
        deps=deps,
        yaml_mapping=options.yaml_mapping,
        yaml_sequence=options.yaml_sequence,
        yaml_offset=options.yaml_offset,
    )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
