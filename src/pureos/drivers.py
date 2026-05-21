import threading
from abc import ABC
import logging
from typing import Dict, Optional, Type


class Driver(ABC):
    """Base class for all system drivers."""

    name: str = ""
    description: str = ""

    def __init__(self, kernel):
        self.kernel = kernel
        self.logger = logging.getLogger(f"pureos.driver.{self.name}")
        self.state = "initialized"

    def on_load(self):
        """Called when the driver is loaded into the system."""
        pass

    def on_unload(self):
        """Called when the driver is being unloaded."""
        pass

    def start(self):
        """Called to start driver background operations."""
        pass

    def stop(self):
        """Called to stop driver background operations."""
        pass

    @property
    def is_running(self) -> bool:
        return self.state == "running"


class DriverManager:
    """Manages the lifecycle of system drivers."""

    def __init__(self, kernel):
        self.kernel = kernel
        self.drivers: Dict[str, Driver] = {}
        self.logger = logging.getLogger("pureos.drivers")
        self._lock = threading.RLock()
        self._started = False

    def _start_driver(self, driver: Driver) -> bool:
        if driver.is_running:
            return True
        try:
            driver.start()
            driver.state = "running"
            self.logger.info("Driver %s started", driver.name)
            return True
        except Exception as e:
            self.logger.error("Error starting driver %s: %s", driver.name, e)
            return False

    def _stop_driver(self, driver: Driver) -> bool:
        if not driver.is_running:
            driver.state = "stopped"
            return True
        try:
            driver.stop()
            driver.state = "stopped"
            self.logger.info("Driver %s stopped", driver.name)
            return True
        except Exception as e:
            self.logger.error("Error stopping driver %s: %s", driver.name, e)
            return False

    def load_driver(self, driver_class: Type[Driver]) -> Optional[Driver]:
        with self._lock:
            name = getattr(driver_class, "name", driver_class.__name__)
            if name in self.drivers:
                self.logger.warning("Driver %s is already loaded", name)
                return self.drivers[name]

            try:
                driver = driver_class(self.kernel)
                driver.on_load()
                driver.state = "loaded"
                self.drivers[name] = driver
                self.logger.info("Driver %s loaded successfully", name)
                if self._started:
                    self._start_driver(driver)
                return driver
            except Exception as e:
                self.logger.error("Failed to load driver %s: %s", name, e)
                return None

    def unload_driver(self, name: str):
        with self._lock:
            if name not in self.drivers:
                return

            try:
                driver = self.drivers[name]
                self._stop_driver(driver)
                driver.on_unload()
                driver.state = "unloaded"
                del self.drivers[name]
                self.logger.info("Driver %s unloaded", name)
            except Exception as e:
                self.logger.error("Error unloading driver %s: %s", name, e)

    def start_driver(self, name: str) -> bool:
        with self._lock:
            if name not in self.drivers:
                self.logger.warning("Driver %s cannot be started because it is not loaded", name)
                return False
            driver = self.drivers[name]
            started = self._start_driver(driver)
            if started:
                self._started = True
            return started

    def stop_driver(self, name: str) -> bool:
        with self._lock:
            if name not in self.drivers:
                self.logger.warning("Driver %s cannot be stopped because it is not loaded", name)
                return False
            driver = self.drivers[name]
            return self._stop_driver(driver)

    def start_all(self):
        with self._lock:
            for driver in self.drivers.values():
                self._start_driver(driver)
            self._started = True

    def shutdown(self):
        with self._lock:
            for name in list(self.drivers.keys()):
                self.unload_driver(name)
            self._started = False
