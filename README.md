# Azul Plugin Js Deobf

Deobfuscates JavaScript to make it more human readable.

## Installation

```bash
# Require install of npm packages seperately.
npm install deobfuscator
npm install restringer

# Python package install
pip install azul-plugin-js-deobf
```

## Npm Packages

deobfuscator - https://github.com/relative/synchrony
restringer - https://github.com/PerimeterX/restringer/tree/main

## Usage

Usage on local files:

```
$ azul-plugin-js-deobf malware.file
... example output goes here ...
```

Check `azul-plugin-js-deobf --help` for advanced usage.

## Dependency management

Dependencies are managed in the pyproject.toml and debian.txt file.

Version pinning is achieved using the `uv.lock` file.
Because the `uv.lock` file is configured to use a private UV registry, external developers using UV will need to delete the existing `uv.lock` file and update the project configuration to point to the publicly available PyPI registry instead.

To add new dependencies it's recommended to use uv with the command `uv add <new-package>`
    or for a dev package `uv add --dev <new-dev-package>`

The tool used for linting and managing styling is `ruff` and it is configured via `pyproject.toml`

The debian.txt file manages the debian dependencies that need to be installed on development systems and docker images.

Sometimes the debian.txt file is insufficient and in this case the Dockerfile may need to be modified directly to
install complex dependencies.
