"""Lightweight service manager with optional stoppable services."""

import threading
from typing import Callable, Dict, Optional


class ServiceManager:
    def __init__(self):
        # _services[name] = {"func": func, "daemon": daemon, "stoppable": stoppable}
        self._services: Dict[str, Dict] = {}
        self._threads: Dict[str, threading.Thread] = {}
        self._stop_events: Dict[str, threading.Event] = {}

    def register(
        self, name: str, func: Callable, daemon: bool = True, stoppable: bool = False
    ):
        self._services[name] = {"func": func, "daemon": daemon, "stoppable": stoppable}

    def start(self, name: str):
        svc = self._services[name]
        func = svc["func"]
        daemon = svc["daemon"]
        stoppable = svc["stoppable"]
        if stoppable:
            stop_event = threading.Event()
            self._stop_events[name] = stop_event

            def target():
                return func(stop_event)

        else:

            def target():
                return func()

        t = threading.Thread(target=target, name=name, daemon=daemon)
        t.start()
        self._threads[name] = t
        return t

    def start_all(self):
        for name in list(self._services.keys()):
            self.start(name)

    def stop(self, name: str, timeout: Optional[float] = 1.0):
        if name not in self._services:
            return
        if self._services[name]["stoppable"]:
            ev = self._stop_events.get(name)
            if ev:
                ev.set()
            t = self._threads.get(name)
            if t and t.is_alive():
                t.join(timeout)
        else:
            # cannot stop non-stoppable service
            return

    def stop_all(self, timeout: Optional[float] = 1.0):
        for name in list(self._services.keys()):
            self.stop(name, timeout=timeout)

    def list(self):
        return list(self._services.keys())
