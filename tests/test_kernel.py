import importlib
import os
import sys
import time

try:
    kernel_mod = importlib.import_module("pureos.core.kernel")
except Exception:
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
    kernel_mod = importlib.import_module("pureos.core.kernel")

Kernel = kernel_mod.Kernel


def test_kernel_initialize_and_shutdown(tmp_path):
    backing = tmp_path / "store.json"
    k = Kernel(config={"fs_backing": str(backing)})
    k.initialize()
    assert "/etc/" in k.fs.list()

    def svc(ev):
        ev.wait(2)

    k.services.register("testsvc", svc, daemon=False, stoppable=True)
    k.start_service("testsvc")
    time.sleep(0.05)
    k.shutdown()
    assert all(not t.is_alive() for t in k.services._threads.values())


def test_kernel_persistent_filesystem(tmp_path):
    backing = tmp_path / "store.json"
    k1 = Kernel(config={"fs_backing": str(backing)})
    k1.initialize()
    k1.fs.write("/var/data", "hello")
    k1.shutdown()

    k2 = Kernel(config={"fs_backing": str(backing)})
    k2.initialize()
    assert k2.fs.read("/var/data") == "hello"
    assert k2.fs.read("/etc/motd") == "Welcome to v2-PureOS"


def test_kernel_auto_start_config(tmp_path):
    backing = tmp_path / "store.json"
    k = Kernel(config={"fs_backing": str(backing), "auto_start_services": ["noop"]})
    k.initialize()
    status = k.services.status("noop")
    assert status["state"] == "running"
    assert status["alive"]
    k.shutdown()
    assert not k.services.status("noop")["alive"]


def test_kernel_register_service_and_auto_start(tmp_path):
    backing = tmp_path / "store.json"
    k = Kernel(config={"fs_backing": str(backing), "auto_start_services": ["testsvc"]})
    start_file = tmp_path / "started"

    def svc(ev=None):
        start_file.write_text("started")
        if ev:
            ev.wait(2)

    k.register_service(
        "testsvc",
        svc,
        daemon=False,
        stoppable=True,
        description="test service",
        auto_start=True,
    )
    k.initialize()
    time.sleep(0.05)
    assert start_file.exists()
    assert k.services.status("testsvc")["state"] == "running"
    k.shutdown()
    assert not k.services.status("testsvc")["alive"]
