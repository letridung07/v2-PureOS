"""Process and scheduler utilities."""

from dataclasses import dataclass
import itertools


@dataclass
class Process:
    pid: int
    name: str
    status: str = "ready"


class Scheduler:
    def __init__(self):
        self._pid_iter = itertools.count(1)
        self.processes = {}

    def spawn(self, name: str) -> Process:
        pid = next(self._pid_iter)
        proc = Process(pid=pid, name=name, status="running")
        self.processes[pid] = proc
        return proc

    def list(self):
        return list(self.processes.values())
