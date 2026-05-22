"""Audit logging driver for v2-PureOS."""

import logging
import threading
from typing import List, Dict, Any

from .drivers import Driver


class AuditHandler(logging.Handler):
    """Custom logging handler to route audit records to AuditDriver."""

    def __init__(self, driver: "AuditDriver"):
        super().__init__()
        self.driver = driver
        self._local = threading.local()

    def emit(self, record: logging.LogRecord):
        # Re-entrancy guard to prevent recursive log handling
        if getattr(self._local, "emit_active", False):
            return
        self._local.emit_active = True
        try:
            msg = self.format(record)
            self.driver.add_audit_log(msg, record)
        except Exception:
            self.handleError(record)
        finally:
            self._local.emit_active = False


class AuditDriver(Driver):
    """Manages the security audit log at /var/log/audit.log."""

    name = "audit"
    description = "Security audit subsystem"

    def __init__(self, kernel):
        super().__init__(kernel)
        self.audit_logs: List[Dict[str, Any]] = []
        self._max_logs = 1000
        self._lock = threading.RLock()
        self._handler = None
        self._local = threading.local()

    def on_load(self):
        fs = self.kernel.fs
        try:
            if not fs.exists("/var/log"):
                fs.mkdir("/var/log")
            if not fs.exists("/var/log/audit.log"):
                fs.write("/var/log/audit.log", "")
        except Exception as e:
            self.logger.error("Failed to initialize audit log files: %s", e)

        self._handler = AuditHandler(self)
        formatter = logging.Formatter(
            "%(asctime)s AUDIT: %(message)s", datefmt="%b %d %H:%M:%S"
        )
        self._handler.setFormatter(formatter)

        # Use a dedicated audit logger
        audit_logger = logging.getLogger("pureos.audit")
        audit_logger.propagate = False  # Don't send audit logs to main syslog by default
        audit_logger.setLevel(logging.INFO)
        audit_logger.addHandler(self._handler)

    def on_unload(self):
        if self._handler:
            audit_logger = logging.getLogger("pureos.audit")
            audit_logger.removeHandler(self._handler)
            self._handler = None

        with self._lock:
            self.audit_logs.clear()

    def add_audit_log(self, formatted_msg: str, record: logging.LogRecord):
        log_entry = {
            "timestamp": record.created,
            "levelname": record.levelname.upper(),
            "message": record.getMessage(),
            "formatted": formatted_msg,
        }
        with self._lock:
            self.audit_logs.append(log_entry)
            if len(self.audit_logs) > self._max_logs:
                self.audit_logs.pop(0)

            if getattr(self._local, "writing", False):
                return
            self._local.writing = True

            users = getattr(self.kernel, "users", None)
            old_user = None
            if users and hasattr(users, "current_user"):
                old_user = users.current_user
                root_user = users.users.get("root")
                if root_user:
                    users.current_user = root_user

            try:
                fs = self.kernel.fs
                if fs.exists("/var/log/audit.log"):
                    fs.append("/var/log/audit.log", formatted_msg + "\n")
            except Exception:
                pass
            finally:
                if users and old_user is not None:
                    users.current_user = old_user
                self._local.writing = False

    def log_event(self, message: str):
        """Helper to log an event directly to the audit logger."""
        audit_logger = logging.getLogger("pureos.audit")
        audit_logger.info(message)
