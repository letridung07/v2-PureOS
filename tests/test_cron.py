import importlib
import os
import sys
from unittest.mock import MagicMock, patch

try:
    builtin_services = importlib.import_module("pureos.builtin_services")
    kernel_mod = importlib.import_module("pureos.kernel")
except Exception:
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
    builtin_services = importlib.import_module("pureos.builtin_services")
    kernel_mod = importlib.import_module("pureos.kernel")

_field_matches = builtin_services._field_matches
_cron_service = builtin_services._cron_service
Kernel = kernel_mod.Kernel


def test_field_matches():
    # Test wildcards
    assert _field_matches("*", 10, 0, 59)
    assert _field_matches("*", 0, 0, 59)

    # Test exact value
    assert _field_matches("15", 15, 0, 59)
    assert not _field_matches("15", 16, 0, 59)

    # Test ranges
    assert _field_matches("10-15", 12, 0, 59)
    assert not _field_matches("10-15", 9, 0, 59)

    # Test steps
    assert _field_matches("*/5", 0, 0, 59)
    assert _field_matches("*/5", 25, 0, 59)
    assert not _field_matches("*/5", 26, 0, 59)

    # Test range with steps
    assert _field_matches("1-10/2", 1, 0, 59)
    assert _field_matches("1-10/2", 5, 0, 59)
    assert not _field_matches("1-10/2", 6, 0, 59)

    # Test lists
    assert _field_matches("1,3,5", 3, 0, 59)
    assert not _field_matches("1,3,5", 4, 0, 59)

    # Test complex lists
    assert _field_matches("1,*/15,30-35", 0, 0, 59)
    assert _field_matches("1,*/15,30-35", 30, 0, 59)
    assert _field_matches("1,*/15,30-35", 1, 0, 59)
    assert not _field_matches("1,*/15,30-35", 2, 0, 59)

    # Test Sunday 0 and 7 compatibility
    assert _field_matches("7", 0, 0, 6)
    assert _field_matches("0", 0, 0, 6)


def test_cron_service_executes_job():
    kernel = Kernel(config={"auto_start_services": []})
    kernel.fs.write("/etc/crontab", "* * * * * echo 'hello' >> /tmp/out.log")

    # Mock datetime.datetime using MagicMock
    with patch("pureos.builtin_services.datetime") as mock_datetime:
        mock_dt = MagicMock()
        mock_dt.year = 2026
        mock_dt.minute = 15
        mock_dt.hour = 10
        mock_dt.day = 19
        mock_dt.month = 5
        mock_dt.weekday.return_value = 1  # Tuesday
        mock_datetime.datetime.now.return_value = mock_dt

        # Stop event to run only one loop iteration
        stop_event = MagicMock()
        stop_event.is_set.side_effect = [False, True]

        _cron_service(kernel, stop_event=stop_event)

        # Check that scheduler spawned a task and wait for it
        kernel.scheduler.wait_all(timeout=2.0)

        # Verify log output
        assert kernel.fs.exists("/tmp/out.log")
        assert "hello" in kernel.fs.read("/tmp/out.log")


def test_crontab_command():
    kernel = Kernel(config={"auto_start_services": []})
    shell = kernel.shell

    # Test crontab -l when no crontab exists
    res = shell.execute("crontab -l")
    assert res is False

    # Create crontab file in temp path
    kernel.fs.write("/tmp/mycron", "* * * * * date")

    # Install crontab
    res = shell.execute("crontab /tmp/mycron")
    assert res is True

    # Check that crontab -l outputs the content
    content = shell.registry.execute(["crontab", "-l"], capture_output=True)
    assert "* * * * * date" in content

    # Remove crontab
    res = shell.execute("crontab -r")
    assert res is True
    assert not kernel.fs.exists("/etc/crontab")
