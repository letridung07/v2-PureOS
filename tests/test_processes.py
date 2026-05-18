import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from pureos.processes import Scheduler


def test_scheduler_spawn_and_list():
    s = Scheduler()
    p = s.spawn("alpha")
    assert p.pid == 1
    assert p.name == "alpha"
    procs = s.list()
    assert len(procs) == 1
    assert procs[0].pid == p.pid
