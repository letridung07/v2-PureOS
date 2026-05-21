"""Lightweight service manager with optional stoppable services."""

import logging
import threading
import time
from dataclasses import dataclass
from typing import Callable, Dict, Optional


@dataclass
class Service:
    name: str
    func: Callable
    daemon: bool = True
    stoppable: bool = False
    description: str = ""
    auto_start: bool = False
    state: str = "stopped"
    error: Optional[BaseException] = None


class ServiceManager:
    def __init__(self):
        self._services: Dict[str, Service] = {}
        self._threads: Dict[str, threading.Thread] = {}
        self._stop_events: Dict[str, threading.Event] = {}
        self.logger = logging.getLogger("pureos.services")

    def register(
        self,
        name: str,
        func: Callable,
        daemon: bool = True,
        stoppable: bool = False,
        description: str = "",
        auto_start: bool = False,
    ):
        self._services[name] = Service(
            name=name,
            func=func,
            daemon=daemon,
            stoppable=stoppable,
            description=description,
            auto_start=auto_start,
        )

    def start(self, name: str):
        if name not in self._services:
            raise KeyError(f"Service {name} not registered")
        svc = self._services[name]
        existing = self._threads.get(name)
        if existing and existing.is_alive():
            return existing

        svc.state = "starting"
        svc.error = None

        def on_exit():
            if svc.state in ("starting", "running"):
                svc.state = "stopped"

        func = svc.func
        daemon = svc.daemon
        stoppable = svc.stoppable
        if stoppable:
            stop_event = threading.Event()
            self._stop_events[name] = stop_event

            def target():
                try:
                    svc.state = "running"
                    return func(stop_event)
                except Exception as exc:
                    svc.state = "failed"
                    svc.error = exc
                finally:
                    on_exit()

        else:

            def target():
                try:
                    svc.state = "running"
                    return func()
                except Exception as exc:
                    svc.state = "failed"
                    svc.error = exc
                finally:
                    on_exit()

        t = threading.Thread(target=target, name=name, daemon=daemon)
        t.start()
        self._threads[name] = t
        return t

    def start_all(self, auto_start_only: bool = False):
        for name, svc in list(self._services.items()):
            if auto_start_only and not svc.auto_start:
                continue
            self.start(name)

    def stop(self, name: str, timeout: Optional[float] = 1.0):
        if name not in self._services:
            return
        svc = self._services[name]
        if not svc.stoppable:
            return

        svc.state = "stopping"
        ev = self._stop_events.get(name)
        if ev:
            ev.set()
        t = self._threads.get(name)
        if t and t.is_alive():
            t.join(timeout)
        if svc.state == "failed":
            return
        if t and t.is_alive():
            svc.state = "stopping"
        else:
            svc.state = "stopped"

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
            "stoppable": svc.stoppable,
            "state": svc.state,
            "description": svc.description,
            "auto_start": svc.auto_start,
            "error": str(svc.error) if svc.error else None,
        }

    def stop_all(self, timeout: Optional[float] = 1.0):
        """Stop all registered services.

        Stops each service (best-effort) and then attempts to join any remaining
        service threads up to the provided timeout.
        """
        names = list(self._services.keys())
        for name in names:
            try:
                self.stop(name, timeout=timeout)
            except Exception as exc:
                self.logger.error("Error stopping service %s: %s", name, exc)

        # After requesting stop for all services, wait for threads to finish
        if timeout is None:
            # wait indefinitely
            for t in list(self._threads.values()):
                try:
                    t.join()
                except Exception:
                    pass
            return

        deadline = time.time() + float(timeout)
        for name, t in list(self._threads.items()):
            if t is None:
                continue
            if not t.is_alive():
                continue
            remaining = deadline - time.time()
            if remaining <= 0:
                break
            try:
                t.join(timeout=remaining)
            except Exception as exc:
                self.logger.debug("Error joining service thread %s: %s", name, exc)

    def list(self):
        return list(self._services.keys())
