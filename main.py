#!/usr/bin/env python3
# Entrypoint for v2-PureOS
"""Starter script for v2-PureOS demo project.

Initializes the package and optionally enters an interactive shell.
"""
import argparse
import importlib
import json
import os
import platform
import sys
import time
import getpass
import socket

# Try top-level import first; if it fails, add src/ to sys.path and import dynamically
try:
    from pureos import run as run_pureos
except Exception:
    ROOT = os.path.dirname(__file__)
    SRC = os.path.join(ROOT, "src")
    if SRC not in sys.path:
        sys.path.insert(0, SRC)
    pureos = importlib.import_module("pureos")
    run_pureos = pureos.run


def banner():
    print("v2-PureOS - minimal Python OS")
    print("=" * 48)


def system_info():
    info = {
        "python": sys.version.split()[0],
        "platform": platform.platform(),
        "cwd": os.getcwd(),
        "user": getpass.getuser(),
        "hostname": socket.gethostname(),
        "time": time.strftime("%Y-%m-%d %H:%M:%S"),
    }
    print("System info:")
    print(json.dumps(info, indent=2))


def main():
    parser = argparse.ArgumentParser(description="v2-PureOS entrypoint")
    parser.add_argument(
        "--shell",
        action="store_true",
        help="Start interactive shell after initialization",
    )
    args = parser.parse_args()

    banner()
    system_info()
    run_pureos(shell=args.shell)
    print("Initialization complete.")
    print("Exiting.")


if __name__ == "__main__":
    main()
