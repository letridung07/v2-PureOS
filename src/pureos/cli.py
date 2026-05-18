"""CLI entrypoint and startup helpers for v2-PureOS."""

import argparse
import getpass
import json
import os
import platform
import socket
import sys
import time

from . import __version__
from . import run as run_pureos


def banner() -> None:
    print("v2-PureOS - minimal Python OS")
    print("=" * 48)


def system_info() -> None:
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


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description="v2-PureOS entrypoint")
    parser.add_argument(
        "--shell",
        action="store_true",
        help="Start interactive shell after initialization",
    )
    parser.add_argument(
        "--version",
        action="store_true",
        help="Show package version and exit",
    )
    return parser.parse_args(argv)


def main(argv=None):
    args = parse_args(argv)
    if args.version:
        print(__version__)
        return
    banner()
    system_info()
    run_pureos(shell=args.shell)
    print("Initialization complete.")
    print("Exiting.")
