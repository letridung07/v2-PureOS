"""Kernel orchestrator with improved lifecycle and optional persistent FS."""

import logging
import time
from typing import Callable, List, Optional

from .config import Config
from .fs import VirtualFS
from .fs.importer import VFSImporter
from .processes import Scheduler
from .services import ServiceManager
from .drivers import DriverManager
from .pkg import PackageManager
from .shell import Shell
from .boot import run_boot_sequence
from .builtin_services import register_builtin_services


class Kernel:
    def __init__(self, config: Optional[dict] = None):
        self.config = Config.from_dict(config)
        self.logger = logging.getLogger("pureos")
        self.users = None
        self.fs = VirtualFS(backing_path=self.config.fs_backing, kernel=self)

        # Register VFS Importer early
        self.importer = VFSImporter.register(self.fs)

        from .users import UserDB

        self.users = UserDB(self)
        self.scheduler = Scheduler()
        self.services = ServiceManager()
        self.drivers = DriverManager(self)
        from .ipc import IPCManager

        self.ipc = IPCManager(self)
        from .commands import CommandRegistry

        self.registry = CommandRegistry(self)
        self.package_manager = PackageManager(self)
        self.shell = Shell(self)

        self.boot_time = time.time()

        # register built-in background services
        register_builtin_services(self)

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
        run_boot_sequence(self)
        if self.users:
            self.users.initialize()

        from .memory import MemoryDriver
        from .syslog import SyslogDriver

        mem_driver = self.drivers.load_driver(MemoryDriver)
        if mem_driver:
            self.scheduler.memory = mem_driver

        self.drivers.load_driver(SyslogDriver)

        print("Kernel: starting drivers...")
        self.drivers.start_all()

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
        print("Kernel: shutting down drivers...")
        self.drivers.shutdown()
        print("Kernel: shutting down services...")
        self.services.stop_all()
        print("Kernel: shutting down processes...")
        self.scheduler.kill_all()
        if hasattr(self.scheduler, "wait_all"):
            self.scheduler.wait_all()

        # Unregister VFS Importer
        VFSImporter.unregister(self.fs)

        print("Kernel: shutdown complete")
