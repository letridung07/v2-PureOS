"""Syslog driver subsystem for v2-PureOS."""

import logging
import threading
from typing import List, Dict, Any

from .drivers import Driver


class SyslogHandler(logging.Handler):
    """Custom logging handler to route log records to SyslogDriver."""

    def __init__(self, driver: "SyslogDriver"):
        super().__init__()
        self.driver = driver
        self._local = threading.local()

    def emit(self, record: logging.LogRecord):
        # Re-entrancy guard to prevent recursive log handling (e.g. from FS operations)
        if getattr(self._local, "emit_active", False):
            return
        self._local.emit_active = True
        try:
            msg = self.format(record)
            self.driver.add_log(msg, record)
        except Exception:
            self.handleError(record)
        finally:
            self._local.emit_active = False


class SyslogDriver(Driver):
    """Manages the in-memory log buffer and /var/log/syslog writes."""

    name = "syslog"
    description = "System logging subsystem"

    def __init__(self, kernel):
        super().__init__(kernel)
        self.logs: List[Dict[str, Any]] = []
        self._max_logs = 500
        self._lock = threading.RLock()
        self._handler = None
        self._local = threading.local()

    def on_load(self):
        fs = self.kernel.fs
        try:
            if not fs.exists("/var/log"):
                fs.mkdir("/var/log")
            if not fs.exists("/var/log/syslog"):
                fs.write("/var/log/syslog", "")
        except Exception as e:
            self.logger.error("Failed to initialize syslog directories/files: %s", e)

        self._handler = SyslogHandler(self)
        formatter = logging.Formatter(
            "%(asctime)s %(levelname)s [%(name)s] %(message)s", datefmt="%b %d %H:%M:%S"
        )
        self._handler.setFormatter(formatter)

        root_logger = logging.getLogger("pureos")
        self._old_level = root_logger.level
        # Lower level to INFO only if it's currently less verbose (WARNING, ERROR, etc.)
        if root_logger.level == logging.NOTSET or root_logger.level > logging.INFO:
            root_logger.setLevel(logging.INFO)
        root_logger.addHandler(self._handler)

    def on_unload(self):
        if self._handler:
            root_logger = logging.getLogger("pureos")
            root_logger.removeHandler(self._handler)
            if hasattr(self, "_old_level"):
                root_logger.setLevel(self._old_level)
            self._handler = None

        with self._lock:
            self.logs.clear()

    def add_log(self, formatted_msg: str, record: logging.LogRecord):
        log_entry = {
            "timestamp": record.created,
            "levelname": record.levelname.upper(),
            "name": record.name,
            "message": record.getMessage(),
            "formatted": formatted_msg,
        }
        with self._lock:
            self.logs.append(log_entry)
            if len(self.logs) > self._max_logs:
                self.logs.pop(0)

            # Write to VFS under lock to ensure thread safety
            if getattr(self._local, "writing", False):
                return
            self._local.writing = True

            # Temporarily elevate current user context to root to allow file operations
            users = getattr(self.kernel, "users", None)
            old_user = None
            if users and hasattr(users, "current_user"):
                old_user = users.current_user
                root_user = users.users.get("root")
                if root_user:
                    users.current_user = root_user

            try:
                fs = self.kernel.fs
                if fs.exists("/var/log/syslog"):
                    fs.append("/var/log/syslog", formatted_msg + "\n")
            except Exception:
                pass
            finally:
                if users and old_user is not None:
                    users.current_user = old_user
                self._local.writing = False

    def clear(self):
        """Clear the in-memory log buffer and the /var/log/syslog file."""
        with self._lock:
            self.logs.clear()

            if getattr(self._local, "writing", False):
                return
            self._local.writing = True

            # Temporarily elevate current user context to root to allow file operations
            users = getattr(self.kernel, "users", None)
            old_user = None
            if users and hasattr(users, "current_user"):
                old_user = users.current_user
                root_user = users.users.get("root")
                if root_user:
                    users.current_user = root_user

            try:
                fs = self.kernel.fs
                if fs.exists("/var/log/syslog"):
                    fs.write("/var/log/syslog", "")
            except Exception:
                pass
            finally:
                if users and old_user is not None:
                    users.current_user = old_user
                self._local.writing = False
