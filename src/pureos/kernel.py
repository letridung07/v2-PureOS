"""Kernel orchestrator with improved lifecycle and optional persistent FS."""

import logging
import time
from typing import Callable, List, Optional

from .config import Config
from .fs import VirtualFS
from .processes import Scheduler
from .services import ServiceManager
from .shell import Shell


def _noop_service(stop_event=None):
    # simple background task that can be stopped when given an event
    while not (stop_event and stop_event.is_set()):
        if stop_event:
            stop_event.wait(0.1)
        else:
            time.sleep(0.1)


class Kernel:
    def __init__(self, config: Optional[dict] = None):
        self.config = Config.from_dict(config)
        self.logger = logging.getLogger("pureos")
        self.fs = VirtualFS(backing_path=self.config.fs_backing)
        self.scheduler = Scheduler()
        self.services = ServiceManager()
        self.shell = Shell(self)

        # register a tiny noop service so there's at least one background thread
        self.services.register(
            "noop",
            _noop_service,
            daemon=True,
            stoppable=True,
            description="No-op background service",
            auto_start=True,
        )

    def register_service(
        self,
        name: str,
        func: Callable,
        daemon: bool = True,
        stoppable: bool = False,
        description: str = "",
        auto_start: bool = False,
    ):
        self.services.register(
            name,
            func,
            daemon=daemon,
            stoppable=stoppable,
            description=description,
            auto_start=auto_start,
        )

    def register_services(self, services: List[dict]):
        for svc in services:
            self.register_service(**svc)

    def initialize(self):
        self.logger.info("Kernel: initializing")
        if self.config.format_on_boot or not self.fs.has_content():
            print("Kernel: formatting filesystem...")
            self.fs.format()
        elif "/etc/motd" not in self.fs.files:
            self.fs.mkdir("/etc/")
            self.fs.write("/etc/motd", "Welcome to v2-PureOS")
        print("Kernel: starting core services...")
        auto_start = self.config.auto_start_services
        if isinstance(auto_start, list):
            for name in auto_start:
                try:
                    self.services.start(name)
                except KeyError:
                    self.logger.warning("Auto-start service %s is not registered", name)
        elif auto_start:
            self.services.start_all(auto_start_only=True)
        else:
            self.services.start_all()
        print("Kernel: initialization complete")

    def start_service(self, name: str):
        return self.services.start(name)

    def stop_service(self, name: str, timeout: float = 1.0):
        return self.services.stop(name, timeout=timeout)

    def shutdown(self):
        print("Kernel: shutting down services...")
        self.services.stop_all()
        print("Kernel: shutting down processes...")
        self.scheduler.kill_all()
        if hasattr(self.scheduler, "wait_all"):
            self.scheduler.wait_all()
        print("Kernel: shutdown complete")
