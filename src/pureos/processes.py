"""Process and scheduler utilities."""

from __future__ import annotations

from dataclasses import dataclass
import itertools
import threading
import time
from typing import Optional, Callable, TYPE_CHECKING

if TYPE_CHECKING:
    from .memory import MemoryDriver


@dataclass
class Process:
    pid: int
    name: str
    status: str = "ready"
    exit_code: Optional[int] = None
    exit_reason: Optional[str] = None
    nice: int = 0  # process priority (lower = higher priority)
    start_time: float = 0.0  # epoch seconds when process started
    thread: Optional[object] = None  # reference to the backing thread
    vsize: int = 0  # virtual memory size in KB
    rss: int = 0  # resident set size in KB
    is_foreground: bool = False  # Track if it is a shell foreground process


class Scheduler:
    def __init__(self):
        self._pid_iter = itertools.count(1)
        self.processes = {}
        self._threads = {}
        self._stop_events = {}
        self._resume_events = {}
        self.memory: Optional[MemoryDriver] = None

    def spawn(
        self,
        name: str,
        target_func: Optional[Callable] = None,
        is_foreground: bool = False,
        *args,
        **kwargs,
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
            start_time=time.time(),
            is_foreground=is_foreground,
        )
        self.processes[pid] = proc
        stop_event = threading.Event()
        self._stop_events[pid] = stop_event
        resume_event = threading.Event()
        resume_event.set()  # Initially running
        self._resume_events[pid] = resume_event

        if self.memory:
            if not self.memory.alloc(pid, 1024):
                raise MemoryError("Kernel: Out of memory during process spawn")

        def target():
            try:
                if actual_target:
                    import inspect

                    sig = inspect.signature(actual_target)
                    pass_kwargs = kwargs.copy()
                    if "stop_event" in sig.parameters:
                        pass_kwargs["stop_event"] = stop_event
                    if "resume_event" in sig.parameters:
                        pass_kwargs["resume_event"] = resume_event

                    actual_target(*args, **pass_kwargs)
                else:
                    start = time.time()
                    while not stop_event.is_set() and time.time() - start < runtime:
                        if proc.status == "suspended":
                            resume_event.wait()
                        time.sleep(0.1)
                if proc.status == "running":
                    proc.status = "completed"
                    proc.exit_code = 0
                    proc.exit_reason = "completed"
            except Exception as exc:
                proc.status = "failed"
                proc.exit_code = 1
                proc.exit_reason = str(exc)
            finally:
                if self.memory:
                    self.memory.free_all(pid)

        thread = threading.Thread(
            target=target,
            name=f"process-{pid}",
            daemon=True,
        )
        thread.start()
        self._threads[pid] = thread
        proc.thread = thread
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

    def suspend(self, pid: int) -> bool:
        """Suspend a process (SIGSTOP simulation)."""
        p = self.processes.get(pid)
        if not p or p.status not in ("running", "ready"):
            return False
        p.status = "suspended"
        event = self._resume_events.get(pid)
        if event:
            event.clear()
        return True

    def resume(self, pid: int) -> bool:
        """Resume a suspended process (SIGCONT simulation)."""
        p = self.processes.get(pid)
        if not p or p.status != "suspended":
            return False
        p.status = "running"
        event = self._resume_events.get(pid)
        if event:
            event.set()
        return True

    def kill(self, pid: int, signal: int = 15) -> bool:
        """Send a signal to a process.

        signal=15 (SIGTERM): graceful stop via stop_event.
        signal=9  (SIGKILL): immediate mark as killed, no grace period.
        """
        p = self.processes.get(pid)
        if not p:
            return False

        # If suspended, we MUST resume it so it can process the stop_event
        if p.status == "suspended":
            self.resume(pid)

        if p.status in ("running", "ready"):
            p.status = "killed"
            p.exit_code = 1
            p.exit_reason = f"killed (signal {signal})"

        if self.memory:
            self.memory.free_all(pid)

        event = self._stop_events.get(pid)
        if event:
            event.set()

        thread = self._threads.get(pid)
        if thread and thread.is_alive():
            timeout = 0.0 if signal == 9 else 1.0
            thread.join(timeout=timeout)
        
        # Clean up tracking structures if the thread is finished
        if thread and not thread.is_alive():
            self._threads.pop(pid, None)
            self._stop_events.pop(pid, None)
            self._resume_events.pop(pid, None)
            # We keep the process in self.processes so its exit status can be queried,
            # but we remove the thread/event resources.
        return True

    def renice(self, pid: int, priority: int) -> bool:
        """Change the nice value (priority) of a process."""
        p = self.processes.get(pid)
        if not p:
            return False
        p.nice = priority
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
