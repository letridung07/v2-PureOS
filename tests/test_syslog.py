import logging
import pytest
from pureos.kernel import Kernel


@pytest.fixture
def kernel():
    k = Kernel({"format_on_boot": True, "auto_start_services": False})
    k.initialize()
    yield k
    k.shutdown()


@pytest.fixture
def shell(kernel):
    return kernel.shell


def test_syslog_driver_loaded(kernel):
    syslog = kernel.drivers.drivers.get("syslog")
    assert syslog is not None
    assert syslog.name == "syslog"
    assert kernel.fs.exists("/var/log/syslog")


def test_syslog_captures_logs(kernel, shell):
    syslog = kernel.drivers.drivers.get("syslog")
    
    # Generate some logs using kernel logger
    kernel.logger.warning("Test warning message")
    kernel.logger.info("Test info message")

    # Verify they exist in-memory
    assert any("Test warning message" in log["message"] for log in syslog.logs)
    assert any("Test info message" in log["message"] for log in syslog.logs)

    # Verify they exist in /var/log/syslog
    syslog_content = kernel.fs.read("/var/log/syslog")
    assert "Test warning message" in syslog_content
    assert "Test info message" in syslog_content


def test_dmesg_command(kernel, shell):
    kernel.logger.info("Test syslog log entry")

    # Run dmesg command in shell and capture output
    out = shell.registry.execute(["dmesg"], capture_output=True)
    assert "Test syslog log entry" in out


def test_dmesg_level_filtering(kernel, shell):
    kernel.logger.warning("Warning message log")
    kernel.logger.info("Info message log")

    # Filter by WARNING
    out_warn = shell.registry.execute(["dmesg", "-l", "warning"], capture_output=True)
    assert "Warning message log" in out_warn
    assert "Info message log" not in out_warn

    # Filter by INFO
    out_info = shell.registry.execute(["dmesg", "-l", "info"], capture_output=True)
    assert "Info message log" in out_info
    assert "Warning message log" not in out_info


def test_dmesg_clear(kernel, shell):
    kernel.logger.info("Some message to clear")

    # Clear logs
    res = shell.registry.execute(["dmesg", "-c"])
    assert res is True

    # Verify memory buffer is empty
    syslog = kernel.drivers.drivers.get("syslog")
    assert len(syslog.logs) == 0

    # Verify VFS syslog file is empty
    assert kernel.fs.read("/var/log/syslog") == ""


def test_dmesg_invalid_usage(kernel, shell):
    res = shell.registry.execute(["dmesg", "-invalid-flag"])
    assert res is False


def test_recursive_logging_prevention(kernel, shell):
    syslog = kernel.drivers.drivers.get("syslog")

    # Trigger a log write which accesses VFS. Even if VFS operations logged things,
    # the guard prevents recursive infinite loop. We can test this by calling
    # add_log inside write context manually or just asserting that writing doesn't loop.
    assert getattr(syslog._local, "writing", False) is False
    kernel.logger.info("Safe log message")
    assert getattr(syslog._local, "writing", False) is False


def test_actual_recursive_logging_append(kernel):
    # Patch kernel.fs.append to log something
    original_append = kernel.fs.append
    log_called = False
    
    def mock_append(path, content):
        nonlocal log_called
        if not log_called:
            log_called = True
            kernel.logger.info("Log message inside append")
        original_append(path, content)
        
    kernel.fs.append = mock_append
    
    # This log should trigger fs.append, which logs "Log message inside append",
    # which should be handled without infinite recursion or deadlock.
    kernel.logger.info("Trigger log")
    
    assert log_called is True


def test_actual_recursive_logging_clear(kernel):
    original_write = kernel.fs.write
    log_called = False
    
    def mock_write(path, content):
        nonlocal log_called
        if not log_called and path == "/var/log/syslog":
            log_called = True
            kernel.logger.info("Log message inside write")
        original_write(path, content)
        
    kernel.fs.write = mock_write
    
    syslog = kernel.drivers.drivers.get("syslog")
    syslog.clear()
    
    assert log_called is True


def test_syslog_write_by_unprivileged_user(kernel, shell):
    # Switch to guest user
    users = kernel.users
    guest = users.users.get("guest")
    assert guest is not None
    users.current_user = guest
    
    # Generate log
    kernel.logger.warning("Log from guest user")
    
    # Switch back to root to verify
    users.current_user = users.users.get("root")
    
    syslog = kernel.drivers.drivers.get("syslog")
    # Verify in memory
    assert any("Log from guest user" in log["message"] for log in syslog.logs)
    # Verify in file
    syslog_content = kernel.fs.read("/var/log/syslog")
    assert "Log from guest user" in syslog_content
