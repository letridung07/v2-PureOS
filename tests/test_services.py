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


def test_service_stop_keeps_stopping_if_not_terminated(tmp_path):
    start_file = tmp_path / "started"

    def svc(stop_event=None):
        start_file.write_text("started")
        if stop_event:
            for _ in range(20):
                if stop_event.is_set():
                    break
                time.sleep(0.1)

    sm = ServiceManager()
    sm.register("svc", svc, daemon=False, stoppable=True)
    t = sm.start("svc")
    time.sleep(0.05)
    assert sm.status("svc")["state"] == "running"
    sm.stop("svc", timeout=0.01)
    status = sm.status("svc")
    assert status["state"] == "stopping"
    assert t.is_alive()
    sm.stop("svc", timeout=1.0)
    assert sm.status("svc")["state"] == "stopped"
    assert not t.is_alive()


def test_service_status_and_restart(tmp_path):
    start_file = tmp_path / "started"

    def svc(stop_event=None):
        start_file.write_text("started")
        if stop_event:
            stop_event.wait(2)

    sm = ServiceManager()
    sm.register(
        "svc",
        svc,
        daemon=False,
        stoppable=True,
        description="test service",
        auto_start=False,
    )

    status = sm.status("svc")
    assert status["state"] == "stopped"
    assert status["description"] == "test service"
    assert status["auto_start"] is False

    sm.start("svc")
    time.sleep(0.05)
    assert sm.status("svc")["state"] == "running"
    sm.stop("svc", timeout=1.0)
    assert sm.status("svc")["state"] == "stopped"
    assert not sm.status("svc")["alive"]

    t2 = sm.restart("svc", timeout=1.0)
    time.sleep(0.05)
    assert sm.status("svc")["state"] == "running"
    sm.stop("svc", timeout=1.0)
    t2.join(timeout=1.0)
    assert not t2.is_alive()
