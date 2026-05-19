import importlib
import os
import sys

try:
    kernel_mod = importlib.import_module("pureos.kernel")
except Exception:
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
    kernel_mod = importlib.import_module("pureos.kernel")

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
