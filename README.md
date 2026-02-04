<!-- markdownlint-disable MD041 -->

<!-- prettier-ignore-start -->
[![Repo][repo-badge]][repo-link]
[![Docs][docs-badge]][docs-link]
[![PyPI license][license-badge]][license-link]
[![PyPI version][pypi-badge]][pypi-link]
[![Conda (channel only)][conda-badge]][conda-link]
[![Code style: ruff][ruff-badge]][ruff-link]
[![uv][uv-badge]][uv-link]

<!--
  For more badges, see
  https://shields.io/category/other
  https://naereen.github.io/badges/
  [pypi-badge]: https://badge.fury.io/py/sync-pre-commit-hooks
-->

[ruff-badge]: https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json
[ruff-link]: https://github.com/astral-sh/ruff
[uv-badge]: https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/uv/main/assets/badge/v0.json
[uv-link]: https://github.com/astral-sh/uv
[pypi-badge]: https://img.shields.io/pypi/v/sync-pre-commit-hooks
[pypi-link]: https://pypi.org/project/sync-pre-commit-hooks
[docs-badge]: https://img.shields.io/badge/docs-sphinx-informational
[docs-link]: https://pages.nist.gov/sync-pre-commit-hooks/
[repo-badge]: https://img.shields.io/badge/--181717?logo=github&logoColor=ffffff

[repo-link]: https://github.com/wpk-nist-gov/sync-pre-commit-hooks
[conda-badge]: https://img.shields.io/conda/v/wpk-nist/sync-pre-commit-hooks
[conda-link]: https://anaconda.org/wpk-nist/sync-pre-commit-hooks
[license-badge]: https://img.shields.io/pypi/l/sync-pre-commit-hooks?color=informational
[license-link]: https://github.com/wpk-nist-gov/sync-pre-commit-hooks/blob/main/LICENSE
[changelog-link]: https://github.com/wpk-nist-gov/sync-pre-commit-hooks/blob/main/CHANGELOG.md

[pre-commit]: https://pre-commit.com/
[lastversion]:  https://github.com/dvershinin/lastversion
[just]: https://github.com/casey/just
[uv]: https://github.com/astral-sh/uv

<!-- other links -->

<!-- prettier-ignore-end -->

# `sync-pre-commit-hooks`

Some [pre-commit] hooks I find useful to keep things in sync during package
development. The goal of most of these hooks is to have a single source of
truth, minimimizing the possibility that things like package dependencies get
out of sync.

<!--TOC-->

---

- [`sync-pre-commit-hooks`](#sync-pre-commit-hooks)
  - [sync-pre-commit-deps](#sync-pre-commit-deps)
  - [fill-pre-commit-deps](#fill-pre-commit-deps)
  - [sync-pre-commit-language-version](#sync-pre-commit-language-version)
  - [apply-command](#apply-command)
  - [justfile-format](#justfile-format)
  - [sync-uv-dependency-groups](#sync-uv-dependency-groups)
  - [check-file-extension](#check-file-extension)
- [Project info](#project-info)
  - [Status](#status)
  - [What's new?](#whats-new)
  - [License](#license)
  - [Contact](#contact)
  - [Credits](#credits)

---

<!--TOC-->

## sync-pre-commit-deps

Inspired by
[pre-commit/sync-pre-commit-deps](https://github.com/pre-commit/sync-pre-commit-deps),
`sync-pre-commit-deps` synchronizes `additional_dependencies` from other hooks
and other sources. Here, you can sync dependencies from other hooks, from a
requirements.txt file, or using [lastversion]. The default is to pickup
dependencies from all hook id's and update `additional_dependencies` in all
hooks. To extract from only certain hook id's, use `--from` or `--from-exclude`.
To only update dependencies in specific hooks, use `--hook` or `--hook-exclude`.
If the name of a hook id is not the same as a dependency, you can pass
`-m {id}:{dependency}`. For example, to extract `ruff` from the hook id
`ruff-check`, pass `-m 'ruff-check:ruff'`. Note that by default, `ruff-check`
and `ruff-format` are translated to `ruff`. For example, this:

```yaml
repos:
  - repo: https://github.com/astral-sh/ruff-pre-commit
    rev: v0.14.5
    hooks:
      - id: ruff-format
        alias: ruff
  - repo: https://github.com/adamtheturtle/doccmd-pre-commit
    rev: v2025.11.8.1
    hooks:
      - id: doccmd
        name: "ruff format markdown"
        alias: ruff
        additional_dependencies:
          - ruff==0.14.3 # will be update to ruff==0.14.5 from "ruff-format" id.
  - repo: https://github.com/wpk-nist-gov/sync-pre-commit-hooks
    rev: v0.2.0
    hooks:
      - id: sync-pre-commit-deps
```

will auto update the version of `ruff` in the `doccmd` hook.

To include pinned dependencies from a `requirements.txt` file, pass
`-r/--requirements` option. For example, with requirements file:

```text
# pre-commit-additional-dependencies.txt
ruff==0.14.5
```

then this will be synced

```yaml
repos:
  - repo: https://github.com/adamtheturtle/doccmd-pre-commit
    rev: v2025.11.8.1
    hooks:
      - id: doccmd
        name: "ruff format markdown"
        alias: ruff
        additional_dependencies:
          - ruff==0.14.2 # will be updated to ruff==0.14.5 from requirements file
  - repo: https://github.com/wpk-nist-gov/sync-pre-commit-hooks
    rev: v0.2.0
    hooks:
      - id: sync-pre-commit-deps
        args: ["--requirements=pre-commit-additional-dependencies.txt"]
        # NOTE: should include requirement file in `files`
        files: >-
          "\.pre-commit-config.yaml$|^pre-commit-additional-dependencies.txt"
```

Note that the additional dependencies in the requirements file override any
found from hook id's.

Lastly, if you have network access (i.e., not on pre-commit.ci), you can use
[lastversion] to update additional dependencies, but you'll have to include it
in the install:

```yaml
repos:
  - repo: https://github.com/adamtheturtle/doccmd-pre-commit
    rev: v2025.11.8.1
    hooks:
      - id: doccmd
        name: "ruff format markdown"
        alias: ruff
        additional_dependencies:
          - ruff==0.14.2 # will be updated to latest version of ruff using lastversion
  - repo: https://github.com/wpk-nist-gov/sync-pre-commit-hooks
    rev: v0.2.0
    hooks:
      - id: sync-pre-commit-deps
        args: ["--last=doccmd"] # which hook id's additional dependencies
        additional_dependencies:
          - lastversion # need to include `lastversion` as additional dependency
```

Additional options are listed below:

<!-- markdownlint-disable-next-line MD013 -->
<!-- [[[cog
import sys
sys.path.insert(0, ".")
from tools.cog_utils import wrap_command, get_pyproject, run_command, cat_lines
sys.path.pop(0)
]]] -->
<!-- [[[end]]] -->

<!-- prettier-ignore-start -->
<!-- markdownlint-disable MD013 -->
<!-- [[[cog run_command("sync-pre-commit-deps --help", include_cmd=False, wrapper="restructuredtext")]]] -->

```restructuredtext
usage: sync-pre-commit-deps [-h] [--from FROM_INCLUDE] [--from-exclude FROM_EXCLUDE]
                            [--hook HOOK_INCLUDE] [--hook-exclude HOOK_EXCLUDE]
                            [-r REQUIREMENTS] [-l LASTVERSION_DEPENDENCIES] [-m ID_DEP]
                            [--config CONFIG] [--yaml-mapping YAML_MAPPING]
                            [--yaml-sequence YAML_SEQUENCE] [--yaml-offset YAML_OFFSET]

Update ``additional_dependencies`` in ``.pre-commit-config.yaml``

options:
  -h, --help            show this help message and exit
  --from FROM_INCLUDE   Hook id's to extract versions from. The default is to extract
                        from all hooks. If pass ``--from id``, then only those hooks
                        explicitly passed will be used to extract versions.
  --from-exclude FROM_EXCLUDE
                        Hook id's to exclude extracting from.
  --hook HOOK_INCLUDE   Hook id's to allow update of additional_dependencies. The
                        default is to allow updates to all hook id's
                        additional_dependencies. If pass ``--hook id``, then only those
                        hooks explicitly passed will be updated.
  --hook-exclude HOOK_EXCLUDE
                        Hook id's to exclude updating.
  -r, --requirements REQUIREMENTS
                        Requirements file to lookup pinned requirements to update.
  -l, --last LASTVERSION_DEPENDENCIES
                        Dependencies to lookup using `lastversion`. Requires network
                        access and `lastversion` to be installed.
  -m, --id-dep ID_DEP   Colon separated hook id to dependency mapping
                        (``{hook_id}:{dependency}``). For example, to map the ``ruff-
                        check`` hook to ``ruff``, pass ``-m 'ruff-check:ruff'. (Default:
                        ['ruff-format:ruff', 'ruff-check:ruff'])
  --config CONFIG       pre-commit config file (Default '.pre-commit-config.yaml')
  --yaml-mapping YAML_MAPPING
                        The `mapping` argument to the YAML dumper. See
                        https://yaml.readthedocs.io/en/latest/detail/#indentation-of-
                        block-sequences
  --yaml-sequence YAML_SEQUENCE
                        The `sequence` argument to the YAML dumper. See
                        https://yaml.readthedocs.io/en/latest/detail/#indentation-of-
                        block-sequences
  --yaml-offset YAML_OFFSET
                        The `offset` argument to the YAML dumper. See
                        https://yaml.readthedocs.io/en/latest/detail/#indentation-of-
                        block-sequences
```

<!-- [[[end]]] -->
<!-- prettier-ignore-end -->

## fill-pre-commit-deps

While `sync-pre-commit-deps` is focused on syncing single dependencies for
multiple hooks, `fill-pre-commit-deps` is intended to fill in all
`additional_dependencies` for a single hook. This is useful for hooks that
depend on multiple packages that can change during development (e.g., `mypy`).
The dependencies can come from package `optional-dependencies` (i.e., extras),
`dependency-groups`, or from _requirements_ files. For example, this:

```toml
# pyproject.toml
[project]
name = "example-package"
...
dependencies = [ "requests > 1.0" ]

[project.optional-dependencies]
io = [ "pyyaml" ]

[dependency-groups]
test = [ "pytest" ]
typecheck = [
  "mypy",
  "orjson",
  "example-package[io]",
  { include-group = "test" },
]

```

```yaml
repos:
  - repo: https://github.com/wpk-nist-gov/sync-pre-commit-hooks
    rev: v0.2.0
    hooks:
      - id: fill-pre-commit-deps
        args:
          - "--hook=mypy"
          - "--group=typecheck"
          - "--exclude=mypy"
  - repo: https://github.com/pre-commit/mirrors-mypy
    rev: v1.19.0
    hooks:
      - id: mypy
```

will lead to:

```yaml
repos:
  ...
  - repo: https://github.com/pre-commit/mirrors-mypy
    rev: v1.19.0
    hooks:
      - id: mypy
        additional_dependencies:
          - orjson
          - pytest
          - pyyaml
          - requests
```

So now you're `mypy` hook dependencies will never get out of sync!

Additional options are listed below:

<!-- prettier-ignore-start -->
<!-- markdownlint-disable MD013 -->
<!-- [[[cog run_command("fill-pre-commit-deps --help", include_cmd=False, wrapper="restructuredtext")]]] -->

```restructuredtext
usage: fill-pre-commit-deps [-h] --hook HOOK_ID [-g GROUPS] [-e EXTRAS]
                            [--no-project-dependencies] [--exclude EXCLUDE]
                            [--include INCLUDE] [-r REQUIREMENTS]
                            [--requirements-exclude REQUIREMENTS_EXCLUDE]
                            [--requirements-include REQUIREMENTS_INCLUDE]
                            [--pyproject PYPROJECT] [--config CONFIG]
                            [--yaml-mapping YAML_MAPPING]
                            [--yaml-sequence YAML_SEQUENCE] [--yaml-offset YAML_OFFSET]
                            [extra_deps ...]

Fill in `additional_dependencies`` extracted from `pyproject.toml` or `requirements.txt`
Works on single hook.

positional arguments:
  extra_deps            Extra dependencies. These are are prepended to any dependencies
                        found from extras/groups/requirements. These should be passed
                        after `"--"``. For example, to include an editable package, use
                        `fill-pre-commit-deps -g typecheck -- --editable=.``. Note that
                        these dependencies are included as is, without any
                        normalization.

options:
  -h, --help            show this help message and exit
  --hook HOOK_ID        Hook id to apply to.
  -g, --group GROUPS    Dependency group
  -e, --extra EXTRAS    Optional dependencies (i.e., extras)
  --no-project-dependencies
                        Do not include `project.dependencies`. You can still include
                        `extras` or `groups`.
  --exclude EXCLUDE     Exclude package.
  --include INCLUDE     Include package. Default is to include all packages. If you
                        specify, `--include``, only those packages are included.
  -r, --req, --requirements REQUIREMENTS
                        Requirements file.
  --requirements-exclude REQUIREMENTS_EXCLUDE
                        Exclude package from read `requirements.txt`.
  --requirements-include REQUIREMENTS_INCLUDE
                        Include package from read `requirements.txt`. Default is to
                        include all packages from requirements.txt. If you specify,
                        `--include``, only those packages are included.
  --pyproject PYPROJECT
                        pyproject.toml file (Default: 'pyproject.toml')
  --config CONFIG       pre-commit config file (Default '.pre-commit-config.yaml')
  --yaml-mapping YAML_MAPPING
                        The `mapping` argument to the YAML dumper. See
                        https://yaml.readthedocs.io/en/latest/detail/#indentation-of-
                        block-sequences
  --yaml-sequence YAML_SEQUENCE
                        The `sequence` argument to the YAML dumper. See
                        https://yaml.readthedocs.io/en/latest/detail/#indentation-of-
                        block-sequences
  --yaml-offset YAML_OFFSET
                        The `offset` argument to the YAML dumper. See
                        https://yaml.readthedocs.io/en/latest/detail/#indentation-of-
                        block-sequences
```

<!-- [[[end]]] -->
<!-- prettier-ignore-end -->

## sync-pre-commit-language-version

Sync `language_version` from value or file. This is useful for syncing the
language version for hooks like `mypy` with that used for development For
example, to keep the python version in sync for the `mypy` hook with the value
saved in a `.python-version` file, use:

```text
# .python-version file
3.14
```

```yaml
repos:
  - repo: https://github.com/wpk-nist-gov/sync-pre-commit-hooks
    rev: v0.2.0
    hooks:
      - id: sync-pre-commit-language-version
        args:
          - "--hook=mypy"
          - "--language-version-file=.python-version"
        files: ^\.python-version$
  - repo: https://github.com/pre-commit/mirrors-mypy
    rev: v1.19.0
    hooks:
      - id: mypy
        language_version: "3.10"
```

will lead to

```yaml
repos:
  ...
  - repo: https://github.com/pre-commit/mirrors-mypy
    rev: v1.19.0
    hooks:
      - id: mypy
        language_version: "3.14"
```

## apply-command

There are situations where you'd like to run a tool via [pre-commit] that only
takes a single file. One example of this is the [just] formatter. However,
pre-commit expects tools to multiple files. For this, you can use the
`apply-command` hook. For example, to run `just` formatter over all justfiles,
use:

```yaml
repos:
  - repo: https://github.com/wpk-nist-gov/sync-pre-commit-hooks
    rev: v0.2.0
      - id: apply-command
        name: justfile-format
        args: [just, --fmt, --unstable, --justfile]
        files: \.?[jJ]ustfile$|.*\.just$
```

This will run `just --fmt --unstable --justfile` over any justfiles in the repo.

Additional options to `apply-command`:

<!-- prettier-ignore-start -->
<!-- markdownlint-disable MD013 -->
<!-- [[[cog run_command("apply-command --help", include_cmd=False, wrapper="restructuredtext")]]] -->

```restructuredtext
usage: apply-command [-h] command paths [paths ...]

positional arguments:
  command     Command to run. Extra arguments to ``command`` will be parsed as well.
              Note that ``command`` will be parsed with ``shlex.split``. So, if you need
              to pass complex arguments, you should wrap ``command`` and these arguments
              in a single string. For example, to run ``command --option a`` over
              ``file1`` and ``file2``, you should use ``apply-command "command --option
              a" file1 file2``
  paths       Files to apply ``command`` to.

options:
  -h, --help  show this help message and exit
```

<!-- [[[end]]] -->
<!-- prettier-ignore-end -->

## justfile-format

This is just an explicit implementation of the [just] format example in
[apply-command](#apply-command). Note that `justfile-format` does not by default
install [just], so if you want the hook to install it, include it in
`additional_dependencies`.

```yaml
repos:
  - repo: https://github.com/wpk-nist-gov/sync-pre-commit-hooks
    rev: v0.2.0
      - id: justfile-format
        additional_dependencies:  # optional include `just` as a dependency
          - rust-just
```

## sync-uv-dependency-groups

I take advantage of `dependency-group` to organize project tasks (tests, type
checking, documentation, etc). Some groups, like tests, will run over multiple
python versions, while others, like documentation, will only ever run on the
projects default python version. If you support an old version of python with
your project and use `uv.lock`, this can lead to dependency conflicts. One way
around this is to limit the python version for certain dependency groups in
either `uv.toml` or `pyproject.toml`. For example, if you have:

```toml
[tool.uv.dependency-groups]
docs.requires-python = ">=3.10"
```

and you pin the python version to `3.13` in `.python-version` file, then running
`sync-uv-dependency-groups` will result in:

```toml
[tool.uv.dependency-groups]
docs.requires-python = ">=3.13"
```

This prevents [uv] `dependency-groups` from getting out of sync with the
`.python-version` file. Additional options are:

<!-- prettier-ignore-start -->
<!-- markdownlint-disable MD013 -->
<!-- [[[cog run_command("apply-command --help", include_cmd=False, wrapper="restructuredtext")]]] -->

```restructuredtext
usage: apply-command [-h] command paths [paths ...]

positional arguments:
  command     Command to run. Extra arguments to ``command`` will be parsed as well.
              Note that ``command`` will be parsed with ``shlex.split``. So, if you need
              to pass complex arguments, you should wrap ``command`` and these arguments
              in a single string. For example, to run ``command --option a`` over
              ``file1`` and ``file2``, you should use ``apply-command "command --option
              a" file1 file2``
  paths       Files to apply ``command`` to.

options:
  -h, --help  show this help message and exit
```

<!-- [[[end]]] -->
<!-- prettier-ignore-end -->

## check-file-extension

This is a simple hook to check that if you add a file with a given extension. If
such a file is found, the hook fails.

<!-- prettier-ignore-start -->
<!-- markdownlint-disable MD013 -->
<!-- [[[cog run_command("check-file-extension --help", include_cmd=False, wrapper="restructuredtext")]]] -->

```restructuredtext
usage: check-file-extension [-h] [-e EXTENSIONS] paths [paths ...]

Exit with non zero status if file has specified extension

positional arguments:
  paths

options:
  -h, --help            show this help message and exit
  -e, --ext EXTENSIONS  Extensions to exclude. Should include `"."`. For example `--ext
                        .rej --ext .bak ...`
```

<!-- [[[end]]] -->
<!-- prettier-ignore-end -->

# Project info

## Status

This package is actively used by the author. Please feel free to create a pull
request for wanted features and suggestions!

<!-- end-docs -->

## What's new?

See [changelog][changelog-link].

## License

This is free software. See [LICENSE][license-link].

## Contact

The author can be reached at <wpk@nist.gov>.

## Credits

This package was created using
[Cookiecutter](https://github.com/audreyr/cookiecutter) with the
[usnistgov/cookiecutter-nist-python](https://github.com/usnistgov/cookiecutter-nist-python)
template.
