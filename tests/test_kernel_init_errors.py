import importlib
import os
import sys

try:
    kernel_mod = importlib.import_module("pureos.core.kernel")
except Exception:
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
    kernel_mod = importlib.import_module("pureos.core.kernel")

Kernel = kernel_mod.Kernel


def test_kernel_initialize_handles_driver_start_errors(tmp_path):
    backing = tmp_path / "store.json"
    k = Kernel(config={"fs_backing": str(backing)})

    # Force drivers.start_all to raise to exercise initialize error handling
    def bad_start_all():
        raise RuntimeError("start failed")

    k.drivers.start_all = bad_start_all
    # Should not raise even if driver start fails
    k.initialize()
    # Shutdown should still complete
    k.shutdown()
