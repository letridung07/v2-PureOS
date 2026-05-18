"""Kernel orchestrator."""

import logging
import time

from .config import DEFAULT_CONFIG
from .fs import VirtualFS
from .processes import Scheduler
from .services import ServiceManager
from .shell import Shell


def _noop_service():
    # simple background task
    while True:
        time.sleep(1)

class Kernel:
    def __init__(self, config=None):
        self.config = config or DEFAULT_CONFIG.copy()
        self.logger = logging.getLogger("pureos")
        self.fs = VirtualFS()
        self.scheduler = Scheduler()
        self.services = ServiceManager()
        self.shell = Shell(self)

        # register a tiny noop service so there's at least one background thread
        self.services.register("noop", _noop_service, daemon=True)

    def initialize(self):
        self.logger.info("Kernel: initializing")
        print("Kernel: formatting filesystem...")
        self.fs.format()
        print("Kernel: starting core services...")
        self.services.start_all()
        print("Kernel: initialization complete")
