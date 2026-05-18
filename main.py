#!/usr/bin/env python3
# Minimal entrypoint for v2-PureOS
"""Simple initializer for the v2-PureOS demo project.
Prints basic system information using only the Python standard library.
"""
import sys
import platform
import os
import json
import socket
import getpass
import time


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
    banner()
    system_info()
    print("Initialization complete.")
    print("Exiting.")


if __name__ == "__main__":
    main()
