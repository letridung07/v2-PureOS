import importlib
import os
import sys
import time

try:
    services_mod = importlib.import_module("pureos.services")
except Exception:
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
    services_mod = importlib.import_module("pureos.services")

ServiceManager = services_mod.ServiceManager


def test_service_start_and_stop(tmp_path):
    start_file = tmp_path / "started"

    def svc(stop_event=None):
        start_file.write_text("started")
        if stop_event:
            stop_event.wait(2)

    sm = ServiceManager()
    sm.register("svc", svc, daemon=False, stoppable=True)
    t = sm.start("svc")
    time.sleep(0.05)
    assert start_file.exists()
    sm.stop("svc", timeout=1.0)
    t.join(timeout=1.0)
    assert not t.is_alive()
