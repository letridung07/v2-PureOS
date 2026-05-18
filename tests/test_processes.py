import importlib
import os
import sys
import time

try:
    processes = importlib.import_module("pureos.processes")
except Exception:
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
    processes = importlib.import_module("pureos.processes")

Scheduler = processes.Scheduler


def test_scheduler_spawn_and_list():
    s = Scheduler()
    p = s.spawn("alpha")
    assert p.pid == 1
    assert p.name == "alpha"
    procs = s.list()
    assert len(procs) == 1
    assert procs[0].pid == p.pid


def test_scheduler_status_and_wait():
    s = Scheduler()
    p = s.spawn("alpha", runtime=0.1)
    assert p.status == "running"
    assert s.status(p.pid) is p
    assert s.status(p.pid).status == "running"
    waited = s.wait(p.pid, timeout=1.0)
    assert waited
    assert s.status(p.pid).status == "completed"
    assert s.status(p.pid).exit_code == 0
    assert s.status(p.pid).exit_reason == "completed"


def test_scheduler_kill_sets_exit_status():
    s = Scheduler()
    p = s.spawn("beta", runtime=5.0)
    time.sleep(0.05)
    assert s.kill(p.pid)
    assert s.status(p.pid).status == "killed"
    assert s.status(p.pid).exit_code == 1
    assert s.status(p.pid).exit_reason == "killed"
