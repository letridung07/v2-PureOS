"""Kernel orchestrator with improved lifecycle and optional persistent FS."""

import logging
import time
from typing import Optional

from .config import DEFAULT_CONFIG
from .fs import VirtualFS
from .processes import Scheduler
from .services import ServiceManager
from .shell import Shell


def _noop_service(stop_event=None):
    # simple background task that can be stopped when given an event
    while not (stop_event and stop_event.is_set()):
        time.sleep(1)


class Kernel:
    def __init__(self, config: Optional[dict] = None):
        self.config = config or DEFAULT_CONFIG.copy()
        self.logger = logging.getLogger("pureos")
        fs_backing = self.config.get("fs_backing")
        self.fs = VirtualFS(backing_path=fs_backing)
        self.scheduler = Scheduler()
        self.services = ServiceManager()
        self.shell = Shell(self)

        # register a tiny noop service so there's at least one background thread
        self.services.register("noop", _noop_service, daemon=True, stoppable=True)

    def initialize(self):
        self.logger.info("Kernel: initializing")
        print("Kernel: formatting filesystem...")
        self.fs.format()
        print("Kernel: starting core services...")
        self.services.start_all()
        print("Kernel: initialization complete")

    def start_service(self, name: str):
        return self.services.start(name)

    def stop_service(self, name: str, timeout: float = 1.0):
        return self.services.stop(name, timeout=timeout)

    def shutdown(self):
        print("Kernel: shutting down services...")
        self.services.stop_all()
        print("Kernel: shutdown complete")
