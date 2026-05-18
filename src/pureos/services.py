"""Lightweight service manager with optional stoppable services."""

import threading
from typing import Callable, Dict, Optional


class ServiceManager:
    def __init__(self):
        self._services: Dict[str, Dict] = {}
        self._threads: Dict[str, threading.Thread] = {}
        self._stop_events: Dict[str, threading.Event] = {}

    def register(
        self,
        name: str,
        func: Callable,
        daemon: bool = True,
        stoppable: bool = False,
        description: str = "",
        auto_start: bool = False,
    ):
        self._services[name] = {
            "func": func,
            "daemon": daemon,
            "stoppable": stoppable,
            "description": description,
            "auto_start": auto_start,
            "state": "stopped",
            "error": None,
        }

    def start(self, name: str):
        if name not in self._services:
            raise KeyError(f"Service {name} not registered")
        svc = self._services[name]
        existing = self._threads.get(name)
        if existing and existing.is_alive():
            return existing

        svc["state"] = "starting"
        svc["error"] = None

        def on_exit():
            if svc["state"] in ("starting", "running"):
                svc["state"] = "stopped"

        func = svc["func"]
        daemon = svc["daemon"]
        stoppable = svc["stoppable"]
        if stoppable:
            stop_event = threading.Event()
            self._stop_events[name] = stop_event

            def target():
                try:
                    svc["state"] = "running"
                    return func(stop_event)
                except Exception as exc:
                    svc["state"] = "failed"
                    svc["error"] = exc
                finally:
                    on_exit()

        else:

            def target():
                try:
                    svc["state"] = "running"
                    return func()
                except Exception as exc:
                    svc["state"] = "failed"
                    svc["error"] = exc
                finally:
                    on_exit()

        t = threading.Thread(target=target, name=name, daemon=daemon)
        t.start()
        self._threads[name] = t
        return t

    def start_all(self, auto_start_only: bool = False):
        for name, svc in list(self._services.items()):
            if auto_start_only and not svc.get("auto_start"):
                continue
            self.start(name)

    def stop(self, name: str, timeout: Optional[float] = 1.0):
        if name not in self._services:
            return
        svc = self._services[name]
        if not svc["stoppable"]:
            return

        svc["state"] = "stopping"
        ev = self._stop_events.get(name)
        if ev:
            ev.set()
        t = self._threads.get(name)
        if t and t.is_alive():
            t.join(timeout)
        if svc["state"] != "failed":
            svc["state"] = "stopped"

    def restart(self, name: str, timeout: Optional[float] = 1.0):
        if name not in self._services:
            return
        self.stop(name, timeout=timeout)
        return self.start(name)

    def status(self, name: str):
        if name not in self._services:
            return None
        svc = self._services[name]
        t = self._threads.get(name)
        alive = t.is_alive() if t else False
        return {
            "alive": alive,
            "stoppable": svc["stoppable"],
            "state": svc["state"],
            "description": svc["description"],
            "auto_start": svc["auto_start"],
            "error": str(svc["error"]) if svc["error"] else None,
        }

    def stop_all(self, timeout: Optional[float] = 1.0):
        for name in list(self._services.keys()):
            self.stop(name, timeout=timeout)

    def list(self):
        return list(self._services.keys())
