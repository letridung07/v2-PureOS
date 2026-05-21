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

        try:
            self.drivers.load_driver(SyslogDriver)
        except Exception as exc:
            self.logger.error("Failed to load SyslogDriver: %s", exc)

        print("Kernel: starting drivers...")
        try:
            self.drivers.start_all()
        except Exception as exc:
            self.logger.error("Error starting drivers: %s", exc)

        print("Kernel: starting core services...")
        auto_start = self.config.auto_start_services
        try:
            if isinstance(auto_start, list):
                for name in auto_start:
                    try:
                        self.services.start(name)
                    except KeyError:
                        self.logger.warning(
                            "Auto-start service %s is not registered", name
                        )
            elif auto_start:
                self.services.start_all(auto_start_only=True)
            else:
                self.services.start_all()
        except Exception as exc:
            self.logger.error("Error starting services: %s", exc)

        print("Kernel: initialization complete")

    def start_service(self, name: str):
        return self.services.start(name)

    def stop_service(self, name: str, timeout: float = 1.0):
        return self.services.stop(name, timeout=timeout)

    def shutdown(self):
        errors = []

        # Stop services first (they may depend on drivers)
        try:
            print("Kernel: shutting down services...")
            self.services.stop_all()
        except Exception as exc:
            self.logger.error("Error shutting down services: %s", exc)
            errors.append(exc)

        # Kill processes next
        try:
            print("Kernel: shutting down processes...")
            self.scheduler.kill_all()
            if hasattr(self.scheduler, "wait_all"):
                self.scheduler.wait_all()
        except Exception as exc:
            self.logger.error("Error shutting down processes: %s", exc)
            errors.append(exc)

        # Finally shutdown drivers
        try:
            print("Kernel: shutting down drivers...")
            self.drivers.shutdown()
        except Exception as exc:
            self.logger.error("Error shutting down drivers: %s", exc)
            errors.append(exc)

        # Unregister VFS Importer
        try:
            VFSImporter.unregister(self.fs)
        except Exception as exc:
            self.logger.error("Error unregistering VFS importer: %s", exc)
            errors.append(exc)

        print("Kernel: shutdown complete")
        if errors:
            self.logger.warning("Kernel.shutdown completed with errors; see logs")
