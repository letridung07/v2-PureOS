"""Process and scheduler utilities."""

from dataclasses import dataclass
import itertools
import threading
import time


@dataclass
class Process:
    pid: int
    name: str
    status: str = "ready"


class Scheduler:
    def __init__(self):
        self._pid_iter = itertools.count(1)
        self.processes = {}
        self._threads = {}
        self._stop_events = {}

    def spawn(self, name: str, runtime: float = 5.0) -> Process:
        pid = next(self._pid_iter)
        proc = Process(pid=pid, name=name, status="running")
        self.processes[pid] = proc
        stop_event = threading.Event()
        self._stop_events[pid] = stop_event

        def target():
            start = time.time()
            while not stop_event.is_set() and time.time() - start < runtime:
                time.sleep(0.1)
            if proc.status == "running":
                proc.status = "completed"

        thread = threading.Thread(target=target, name=f"process-{pid}", daemon=True)
        thread.start()
        self._threads[pid] = thread
        return proc

    def list(self):
        return list(self.processes.values())

    def kill(self, pid: int) -> bool:
        p = self.processes.get(pid)
        if not p:
            return False
        if p.status in ("running", "ready"):
            p.status = "killed"
        event = self._stop_events.get(pid)
        if event:
            event.set()
        thread = self._threads.get(pid)
        if thread and thread.is_alive():
            thread.join(timeout=1.0)
        return True

    def kill_all(self):
        for pid in list(self.processes.keys()):
            self.kill(pid)
