import importlib
import os
import sys
import time

try:
    kernel_mod = importlib.import_module("pureos.kernel")
except Exception:
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
    kernel_mod = importlib.import_module("pureos.kernel")

Kernel = kernel_mod.Kernel


def test_kernel_initialize_and_shutdown(tmp_path):
    backing = tmp_path / "store.json"
    k = Kernel(config={"fs_backing": str(backing)})
    k.initialize()
    assert "/etc/motd" in k.fs.list()

    def svc(ev):
        ev.wait(2)

    k.services.register("testsvc", svc, daemon=False, stoppable=True)
    k.start_service("testsvc")
    time.sleep(0.05)
    k.shutdown()
    assert all(not t.is_alive() for t in k.services._threads.values())
