# v2-PureOS

![CI](https://github.com/letridung07/v2-PureOS/actions/workflows/ci.yml/badge.svg)

v2-PureOS is a Python project that demonstrates OS-like behavior with a virtual filesystem, process scheduler, service manager, and interactive shell. It is intentionally simple and built using only Python's standard library.

## Quickstart

Run the project directly from the repository root:

```bash
python3 main.py --shell
```

This will initialize v2-PureOS, print startup information, and open the interactive shell.

If you want to run the package-style entrypoint:

```bash
PYTHONPATH=src python3 -m pureos --shell
```

Or install it locally for easier reuse:

```bash
python3 -m pip install -e .
python3 -m pureos --shell
```

## Basic usage

The entrypoint supports two options:

- `--shell` — start the interactive shell
- `--version` — print the package version and exit
- `--backing <path>` — specify a persistent backing file for the virtual filesystem

Once inside the shell, use `help` to see the available commands. For a full command reference and usage notes, see `docs/index.md`.

## Development and testing

Requirements:

- Python 3.8 or newer
- Optional test dependencies: `pytest`, `pytest-cov`

Run tests locally:

```bash
python3 -m pip install -q pytest pytest-cov
pytest
```

The project includes a GitHub Actions workflow at `.github/workflows/ci.yml`.

## Project layout

- `main.py` — top-level launcher for the package
- `src/pureos` — package source code
- `tests` — test suite covering filesystem, shell, services, processes, networking, and kernel behavior

## Notes

This README is intended as a project overview and quickstart. For detailed shell commands, examples, and implementation notes, consult `docs/index.md`.

Test commit entry created by assistant.
