"""Lightweight service manager."""

import threading
import time

class ServiceManager:
    def __init__(self):
        self._services = {}
        self._threads = {}

    def register(self, name: str, func, daemon: bool = True):
        self._services[name] = (func, daemon)

    def start(self, name: str):
        func, daemon = self._services[name]
        t = threading.Thread(target=func, name=name, daemon=daemon)
        t.start()
        self._threads[name] = t
        return t

    def start_all(self):
        for name in list(self._services.keys()):
            self.start(name)

    def list(self):
        return list(self._services.keys())
