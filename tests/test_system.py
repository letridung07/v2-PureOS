import importlib
import os
import sys

try:
    kernel_mod = importlib.import_module("pureos.core.kernel")
except Exception:
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
    kernel_mod = importlib.import_module("pureos.core.kernel")

Kernel = kernel_mod.Kernel


def test_system_stats(tmp_path):
    k = Kernel(config={"fs_backing": str(tmp_path / "store.json")})
    k.initialize()
    sh = k.shell

    # uptime
    assert "uptime: " in sh.registry.execute(["uptime"], capture_output=True)

    # date
    assert len(sh.registry.execute(["date"], capture_output=True)) > 0

    # df
    df_out = sh.registry.execute(["df"], capture_output=True)
    assert "filesystem" in df_out.lower()
    assert "virtualfs" in df_out

    # free
    free_out = sh.registry.execute(["free"], capture_output=True)
    assert "Mem:" in free_out
    assert "Swap:" in free_out

    k.shutdown()


def test_env_and_clear_commands(kernel, shell):
    # Test env / printenv
    shell.execute("export FOO=bar")
    shell.execute("export BAZ=qux")

    env_out = shell.registry.execute(["env"], capture_output=True)
    assert "FOO=bar" in env_out
    assert "BAZ=qux" in env_out

    printenv_out = shell.registry.execute(["printenv"], capture_output=True)
    assert "FOO=bar" in printenv_out
    assert "BAZ=qux" in printenv_out

    # Test clear
    clear_out = shell.registry.execute(["clear"], capture_output=True)
    assert clear_out == "\033[H\033[2J"
