import importlib
import json
import os
import sys

try:
    cli_mod = importlib.import_module("pureos.cli")
    pureos_mod = importlib.import_module("pureos")
except Exception:
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
    cli_mod = importlib.import_module("pureos.cli")
    pureos_mod = importlib.import_module("pureos")


def test_cli_parse_args():
    args = cli_mod.parse_args(["--shell"])
    assert args.shell is True
    assert args.version is False


def test_cli_version_flag():
    args = cli_mod.parse_args(["--version"])
    assert args.version is True
    assert args.shell is False


def test_cli_backing_flag():
    args = cli_mod.parse_args(["--backing", "/tmp/pureos.json"])
    assert args.backing == "/tmp/pureos.json"
    assert args.shell is False
    assert args.version is False


def test_cli_parse_no_args():
    args = cli_mod.parse_args([])
    assert args.shell is False
    assert args.version is False
    assert args.backing is None


def test_banner(capsys):
    cli_mod.banner()
    captured = capsys.readouterr()
    assert "v2-PureOS" in captured.out
    assert "=" * 48 in captured.out


def test_system_info(capsys):
    cli_mod.system_info()
    captured = capsys.readouterr()
    assert "System info:" in captured.out
    # Should contain valid JSON
    lines = captured.out.strip().split("\n")
    json_str = "\n".join(lines[1:])  # skip "System info:" line
    info = json.loads(json_str)
    assert "python" in info
    assert "platform" in info
    assert "cwd" in info
    assert "user" in info
    assert "hostname" in info
    assert "time" in info


def test_main_version(capsys):
    cli_mod.main(["--version"])
    captured = capsys.readouterr()
    assert captured.out.strip() == pureos_mod.__version__
