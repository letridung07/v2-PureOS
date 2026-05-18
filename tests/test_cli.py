import importlib
import os
import sys

try:
    cli_mod = importlib.import_module("pureos.cli")
except Exception:
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
    cli_mod = importlib.import_module("pureos.cli")


def test_cli_parse_args():
    args = cli_mod.parse_args(["--shell"])
    assert args.shell is True
    assert args.version is False


def test_cli_version_flag():
    args = cli_mod.parse_args(["--version"])
    assert args.version is True
    assert args.shell is False
