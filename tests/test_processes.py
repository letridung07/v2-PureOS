import importlib
import os
import sys

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
