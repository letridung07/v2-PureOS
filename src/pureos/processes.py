"""Process and scheduler utilities."""

from dataclasses import dataclass
import itertools
import threading
import time
from typing import Optional, Callable


@dataclass
class Process:
    pid: int
    name: str
    status: str = "ready"
    exit_code: Optional[int] = None
    exit_reason: Optional[str] = None


class Scheduler:
    def __init__(self):
        self._pid_iter = itertools.count(1)
        self.processes = {}
        self._threads = {}
        self._stop_events = {}

    def spawn(
        self, name: str, target_func: Optional[Callable] = None, *args, **kwargs
    ) -> Process:
        pid = next(self._pid_iter)

        runtime = kwargs.get("runtime", 5.0)
        actual_target = None
        if target_func is not None:
            if callable(target_func):
                actual_target = target_func
            else:
                runtime = float(target_func)

        proc = Process(
            pid=pid,
            name=name,
            status="running",
            exit_code=None,
            exit_reason="started",
        )
        self.processes[pid] = proc
        stop_event = threading.Event()
        self._stop_events[pid] = stop_event

        def target():
            try:
                if actual_target:
                    import inspect

                    sig = inspect.signature(actual_target)
                    if "stop_event" in sig.parameters:
                        actual_target(*args, stop_event=stop_event, **kwargs)
                    else:
                        actual_target(*args, **kwargs)
                else:
                    start = time.time()
                    while not stop_event.is_set() and time.time() - start < runtime:
                        time.sleep(0.1)
                if proc.status == "running":
                    proc.status = "completed"
                    proc.exit_code = 0
                    proc.exit_reason = "completed"
            except Exception as exc:
                proc.status = "failed"
                proc.exit_code = 1
                proc.exit_reason = str(exc)

        thread = threading.Thread(
            target=target,
            name=f"process-{pid}",
            daemon=True,
        )
        thread.start()
        self._threads[pid] = thread
        return proc

    def list(self):
        return list(self.processes.values())

    def status(self, pid: int) -> Optional[Process]:
        return self.processes.get(pid)

    def wait(self, pid: int, timeout: Optional[float] = None) -> bool:
        thread = self._threads.get(pid)
        if not thread:
            return False
        thread.join(timeout)
        return not thread.is_alive()

    def kill(self, pid: int) -> bool:
        p = self.processes.get(pid)
        if not p:
            return False
        if p.status in ("running", "ready"):
            p.status = "killed"
            p.exit_code = 1
            p.exit_reason = "killed"
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

    def wait_all(self, timeout: Optional[float] = None) -> bool:
        if timeout is None:
            for thread in self._threads.values():
                thread.join()
            return all(not thread.is_alive() for thread in self._threads.values())

        deadline = time.time() + timeout
        for thread in self._threads.values():
            remaining = deadline - time.time()
            if remaining <= 0:
                break
            thread.join(remaining)
        return all(not thread.is_alive() for thread in self._threads.values())
