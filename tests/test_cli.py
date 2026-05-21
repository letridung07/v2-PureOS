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
    expected = os.path.abspath("/tmp/pureos.json")
    args = cli_mod.parse_args(["--backing", "/tmp/pureos.json"])
    assert args.backing == expected
    assert args.shell is False
    assert args.version is False


def test_cli_backing_path_expands_user_home():
    expected = os.path.abspath(os.path.expanduser("~/pureos.json"))
    args = cli_mod.parse_args(["--backing", "~/pureos.json"])
    assert args.backing == expected
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
    assert "version" in info


def test_main_version(capsys):
    cli_mod.main(["--version"])
    captured = capsys.readouterr()
    assert captured.out.strip() == pureos_mod.__version__


def test_run_entrypoint_initializes_kernel():
    kernel = pureos_mod.run(shell=False, config={"format_on_boot": True, "auto_start_services": False})
    assert kernel is not None
    assert hasattr(kernel, "shutdown")
    kernel.shutdown()


def test_dunder_main_version(monkeypatch, capsys):
    monkeypatch.setattr(sys, "argv", ["python", "--version"])
    import importlib

    main_mod = importlib.import_module("pureos.__main__")
    main_mod.main()
    captured = capsys.readouterr()
    assert captured.out.strip() == pureos_mod.__version__


def test_run_module_as_main(monkeypatch, capsys):
    monkeypatch.setattr(sys, "argv", ["python", "--version"])
    import runpy

    original_pureos = sys.modules.get("pureos")
    original_main = sys.modules.get("pureos.__main__")
    try:
        sys.modules.pop("pureos.__main__", None)
        sys.modules.pop("pureos", None)
        runpy.run_module("pureos", run_name="__main__")
        captured = capsys.readouterr()
        assert captured.out.strip() == pureos_mod.__version__
    finally:
        if original_pureos is not None:
            sys.modules["pureos"] = original_pureos
        else:
            sys.modules.pop("pureos", None)
        if original_main is not None:
            sys.modules["pureos.__main__"] = original_main
        else:
            sys.modules.pop("pureos.__main__", None)
