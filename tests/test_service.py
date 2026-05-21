"""Tests for service commands and boot sequence."""

import importlib
import os
import sys

try:
    kernel_mod = importlib.import_module("pureos.kernel")
    boot_mod = importlib.import_module("pureos.boot")
except Exception:
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
    kernel_mod = importlib.import_module("pureos.kernel")
    boot_mod = importlib.import_module("pureos.boot")

Kernel = kernel_mod.Kernel


class TestServiceCommand:
    def _make_kernel(self, tmp_path):
        backing = tmp_path / "store.json"
        k = Kernel(config={"fs_backing": str(backing)})
        k.initialize()
        return k

    def test_services_lists_registered(self, tmp_path):
        k = self._make_kernel(tmp_path)
        out = k.shell.registry.execute(["services"], capture_output=True)
        assert "noop" in out
        k.shutdown()

    def test_service_status_running(self, tmp_path):
        k = self._make_kernel(tmp_path)
        out = k.shell.registry.execute(
            ["service", "status", "noop"], capture_output=True
        )
        assert "running=True" in out
        k.shutdown()

    def test_service_status_not_registered(self, tmp_path):
        k = self._make_kernel(tmp_path)
        result = k.shell.registry.execute(
            ["service", "status", "nonexistent"]
        )
        assert result is False
        k.shutdown()

    def test_service_start_stop(self, tmp_path):
        k = self._make_kernel(tmp_path)
        result = k.shell.registry.execute(["service", "stop", "noop"])
        assert result is True
        status = k.services.status("noop")
        assert not status["alive"]

        result = k.shell.registry.execute(["service", "start", "noop"])
        assert result is True
        status = k.services.status("noop")
        assert status["alive"]
        k.shutdown()

    def test_service_start_not_registered(self, tmp_path):
        k = self._make_kernel(tmp_path)
        result = k.shell.registry.execute(
            ["service", "start", "nonexistent"]
        )
        assert result is False
        k.shutdown()

    def test_service_restart(self, tmp_path):
        k = self._make_kernel(tmp_path)
        result = k.shell.registry.execute(["service", "restart", "noop"])
        assert result is True
        k.shutdown()

    def test_service_unknown_action(self, tmp_path):
        k = self._make_kernel(tmp_path)
        result = k.shell.registry.execute(
            ["service", "unknown", "noop"]
        )
        assert result is False
        k.shutdown()

    def test_service_usage_no_args(self, tmp_path):
        k = self._make_kernel(tmp_path)
        result = k.shell.registry.execute(["service"])
        assert result is False
        k.shutdown()


class TestBootSequence:
    def test_ensure_default_files(self, tmp_path):
        backing = tmp_path / "store.json"
        k = Kernel(config={"fs_backing": str(backing)})
        k.initialize()
        assert k.fs.exists("/etc/motd")
        assert k.fs.exists("/etc/pureosrc")
        assert k.fs.read("/etc/motd") == "Welcome to v2-PureOS"
        k.shutdown()

    def test_format_on_boot(self, tmp_path):
        backing = tmp_path / "store.json"
        k = Kernel(
            config={
                "fs_backing": str(backing),
                "format_on_boot": True,
            }
        )
        k.initialize()
        # Should have formatted and created default files
        assert k.fs.exists("/etc/motd")
        k.shutdown()

    def test_load_packages_from_vfs(self, tmp_path):
        backing = tmp_path / "store.json"
        k = Kernel(config={"fs_backing": str(backing)})
        k.initialize()
        # Create a package in VFS
        k.fs.mkdir("/usr/lib/pureos/packages/", parents=True)
        k.fs.write(
            "/usr/lib/pureos/packages/testpkg.py",
            "from pureos.commands.base import Command\n"
            "class TestCmd(Command):\n"
            "    name = 'testcmd'\n"
            "    description = 'test'\n"
            "    def execute(self, parts, input_data=None, capture_output=False, raw_line=None):\n"
            "        return True\n"
            "def register(registry):\n"
            "    registry.register(TestCmd(registry.kernel))\n",
        )
        # Reload boot to test package loading
        boot_mod._load_packages(k)
        assert "testcmd" in k.shell.registry.commands
        k.shutdown()
