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
  [pypi-badge]: https://badge.fury.io/py/pre-commit-hooks
-->

[ruff-badge]: https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json
[ruff-link]: https://github.com/astral-sh/ruff
[uv-badge]: https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/uv/main/assets/badge/v0.json
[uv-link]: https://github.com/astral-sh/uv
[pypi-badge]: https://img.shields.io/pypi/v/pre-commit-hooks
[pypi-link]: https://pypi.org/project/pre-commit-hooks
[docs-badge]: https://img.shields.io/badge/docs-sphinx-informational
[docs-link]: https://pages.nist.gov/pre-commit-hooks/
[repo-badge]: https://img.shields.io/badge/--181717?logo=github&logoColor=ffffff
[repo-link]: https://github.com/wpk-nist-gov/pre-commit-hooks
[conda-badge]: https://img.shields.io/conda/v/wpk-nist/pre-commit-hooks
[conda-link]: https://anaconda.org/wpk-nist/pre-commit-hooks
[license-badge]: https://img.shields.io/pypi/l/pre-commit-hooks?color=informational
[license-link]: https://github.com/wpk-nist-gov/pre-commit-hooks/blob/main/LICENSE
[changelog-link]: https://github.com/wpk-nist-gov/pre-commit-hooks/blob/main/CHANGELOG.md
[pre-commit]: https://pre-commit.com/
[lastversion]:  https://github.com/dvershinin/lastversion

<!-- other links -->

<!-- prettier-ignore-end -->

# `pre-commit-hooks`

Some [pre-commit] hooks I find useful in package development.

## sync-pre-commit-deps

Inspired by
[pre-commit/sync-pre-commit-deps](https://github.com/pre-commit/sync-pre-commit-deps)
but more general. Here, you can sync dependencies from other hooks, from a
requirements.txt file, or using [lastversion]. The default is to pickup
dependencies from hook id's `typos`, `codespell`, `ruff-format`, and
`ruff-check`. To extract dependencies from other hooks, pass
`--from={hook name to extract from}`. Note that the "ruff" id's are translated
to a `ruff` version. For example, this:

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
  - repo: https://github.com/wpk-nist-gov/sync-pre-commit-deps
    rev: v0.1.0
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
  - repo: https://github.com/wpk-nist-gov/sync-pre-commit-deps
    rev: v0.1.0
    hooks:
      - id: sync-pre-commit-deps
        args: ["--requirements=pre-commit-additional-dependencies.txt"]
        files: >-
          "\.pre-commit-config.yaml$|^pre-commit-additional-dependencies.txt"
```

Note that the additional dependencies in the requirements file override any
found from hook id's.

By default, only hooks `doccmd`, `justfile-format`, and `nbqa` are additional
dependencies are updated. To update other hooks, pass them with
`--to={hook id to update to}`.

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
  - repo: https://github.com/wpk-nist-gov/sync-pre-commit-deps
    rev: v0.1.0
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
<!-- [[[cog run_command("sync-pre-commit-deps --help", include_cmd=True, wrapper="bash")]]] -->

```bash
$ sync-pre-commit-deps --help
usage: sync-pre-commit-deps [-h] [--yaml-mapping YAML_MAPPING]
                            [--yaml-sequence YAML_SEQUENCE] [--yaml-offset YAML_OFFSET]
                            [--from FROM_INCLUDE] [--from-all]
                            [--from-exclude FROM_EXCLUDE] [--to TO_INCLUDE] [--to-all]
                            [--to-exclude TO_EXCLUDE] [-r REQUIREMENTS]
                            [-l LASTVERSION_DEPENDENCIES]
                            [paths ...]

Update ``additional_dependencies`` in ``.pre-commit-config.yaml``

positional arguments:
  paths                 The pre-commit config file to sync to.

options:
  -h, --help            show this help message and exit
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
  --from FROM_INCLUDE   hook id's to extract requirements from. Defaults to ['typos',
                        'codespell', 'ruff-format', 'ruff-check']
  --from-all            Extract dependencies from all hook id's
  --from-exclude FROM_EXCLUDE
                        Hook id's to exclude extracting from. Note that this is applied
                        even if pass ``--from-all``
  --to TO_INCLUDE       hook id's to allow update of additional_dependencies. Defaults
                        to ['doccmd', 'justfile-format', 'nbqa']
  --to-all              Update dependencies of all hooks
  --to-exclude TO_EXCLUDE
                        Hook id's to exclude updating. Note that this is applied even if
                        pass ``--to-all``
  -r, --requirements REQUIREMENTS
                        Requirements file to lookup pinned requirements to update.
  -l, --last LASTVERSION_DEPENDENCIES
                        Dependency to lookup using `lastversion`. Requires network
                        access and `lastversion` to be installed.
```

<!-- [[[end]]] -->

## Status

This package is actively used by the author. Please feel free to create a pull
request for wanted features and suggestions!

## Example usage

```python
import pre_commit_hooks
```

<!-- end-docs -->

## Installation

<!-- start-installation -->

Use one of the following

```bash
pip install pre-commit-hooks
```

or

```bash
conda install -c wpk-nist pre-commit-hooks
```

<!-- end-installation -->

## Documentation

See the [documentation][docs-link] for further details.

## What's new?

See [changelog][changelog-link].

## License

This is free software. See [LICENSE][license-link].

## Related work

Any other stuff to mention....

## Contact

The author can be reached at <wpk@nist.gov>.

## Credits

This package was created using
[Cookiecutter](https://github.com/audreyr/cookiecutter) with the
[usnistgov/cookiecutter-nist-python](https://github.com/usnistgov/cookiecutter-nist-python)
template.
