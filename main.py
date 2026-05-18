#!/usr/bin/env python3
# Entrypoint for v2-PureOS
"""Starter script for v2-PureOS demo project.

Initializes the package and optionally enters an interactive shell.
"""

import importlib
import os
import sys

# Try top-level import first; if it fails, add src/ to sys.path and import dynamically
try:
    from pureos.cli import main as run_pureos_cli
except Exception:
    ROOT = os.path.dirname(__file__)
    SRC = os.path.join(ROOT, "src")
    if SRC not in sys.path:
        sys.path.insert(0, SRC)
    cli = importlib.import_module("pureos.cli")
    run_pureos_cli = cli.main


def main():
    run_pureos_cli()


if __name__ == "__main__":
    main()
