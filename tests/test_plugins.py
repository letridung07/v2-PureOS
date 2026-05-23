import sys
import pytest
from pureos.core.kernel import Kernel
from pureos.drivers.base import Driver


@pytest.fixture
def kernel():
    k = Kernel({"format_on_boot": True, "auto_start_services": False})
    k.initialize()
    yield k
    k.shutdown()


@pytest.fixture
def shell(kernel):
    return kernel.shell


def test_vfs_importer_basic(kernel):
    """Test that we can import a simple module from the VFS."""
    vfs_path = "/usr/lib/python/simple_mod.py"
    kernel.fs.write(vfs_path, "x = 100\ndef get_x(): return x")

    # Use the pureos_vfs namespace
    import pureos_vfs.simple_mod

    assert pureos_vfs.simple_mod.x == 100
    assert pureos_vfs.simple_mod.get_x() == 100


def test_vfs_importer_package(kernel):
    """Test that we can import a package with __init__.py from the VFS."""
    kernel.fs.mkdir("/usr/lib/python/mypkg/")
    kernel.fs.write("/usr/lib/python/mypkg/__init__.py", "pkg_val = 'hello'")
    kernel.fs.write("/usr/lib/python/mypkg/submod.py", "sub_val = 'world'")

    import pureos_vfs.mypkg
    import pureos_vfs.mypkg.submod

    assert pureos_vfs.mypkg.pkg_val == "hello"
    assert pureos_vfs.mypkg.submod.sub_val == "world"


def test_driver_lifecycle(kernel):
    """Test the full lifecycle of a driver."""

    class MockDriver(Driver):
        name = "mock_drv"

        def __init__(self, k):
            super().__init__(k)
            self.loaded = False
            self.started = False
            self.stopped = False
            self.unloaded = False

        def on_load(self):
            self.loaded = True

        def start(self):
            self.started = True

        def stop(self):
            self.stopped = True

        def on_unload(self):
            self.unloaded = True

    dm = kernel.drivers
    drv = dm.load_driver(MockDriver)

    assert drv.loaded is True
    assert "mock_drv" in dm.drivers
    assert drv.state == "running"
    assert drv.started is True

    dm.unload_driver("mock_drv")
    assert drv.stopped is True
    assert drv.unloaded is True
    assert drv.state == "unloaded"
    assert "mock_drv" not in dm.drivers


def test_driver_manager_lazy_start_and_stop():
    """Test driver manager behavior before drivers are started."""

    class LazyDriver(Driver):
        name = "lazy_drv"

        def __init__(self, kernel):
            super().__init__(kernel)
            self.started = False
            self.stopped = False

        def on_load(self):
            pass

        def start(self):
            self.started = True

        def stop(self):
            self.stopped = True

    kernel = Kernel({"format_on_boot": True, "auto_start_services": False})
    dm = kernel.drivers
    drv = dm.load_driver(LazyDriver)

    assert drv.state == "loaded"
    assert not drv.is_running
    assert dm.start_driver("lazy_drv") is True
    assert drv.state == "running"
    assert drv.started is True

    assert dm.stop_driver("lazy_drv") is True
    assert drv.state == "stopped"
    assert drv.stopped is True

    dm.unload_driver("lazy_drv")
    assert "lazy_drv" not in dm.drivers


def test_driver_manager_missing_driver_start_stop():
    """Test start/stop behavior for drivers that are not loaded."""
    kernel = Kernel({"format_on_boot": True, "auto_start_services": False})
    dm = kernel.drivers

    assert dm.start_driver("no_such_driver") is False
    assert dm.stop_driver("no_such_driver") is False


def test_driver_manager_stop_not_running():
    """Test stopping a loaded driver that has not yet been started."""

    class LazyStopDriver(Driver):
        name = "lazy_stop_drv"

        def __init__(self, kernel):
            super().__init__(kernel)
            self.stopped = False

        def on_load(self):
            pass

        def stop(self):
            self.stopped = True

    kernel = Kernel({"format_on_boot": True, "auto_start_services": False})
    dm = kernel.drivers
    drv = dm.load_driver(LazyStopDriver)

    assert drv.state == "loaded"
    assert dm.stop_driver("lazy_stop_drv") is True
    assert drv.state == "stopped"
    assert drv.stopped is False

    dm.unload_driver("lazy_stop_drv")
    assert "lazy_stop_drv" not in dm.drivers


def test_driver_manager_start_driver_already_running():
    """Test starting a driver that is already running."""

    class RunningDriver(Driver):
        name = "running_drv"

        def __init__(self, kernel):
            super().__init__(kernel)
            self.start_count = 0

        def on_load(self):
            pass

        def start(self):
            self.start_count += 1

    kernel = Kernel({"format_on_boot": True, "auto_start_services": False})
    dm = kernel.drivers
    drv = dm.load_driver(RunningDriver)

    assert drv.state == "loaded"
    assert dm.start_driver("running_drv") is True
    assert drv.state == "running"
    assert dm.start_driver("running_drv") is True
    assert drv.start_count == 1

    dm.unload_driver("running_drv")
    assert "running_drv" not in dm.drivers


def test_driver_runtime_control_commands(kernel, shell):
    """Test runtime driver start/stop/status behavior."""
    driver_content = """
from pureos.drivers.base import Driver

class CmdDriver(Driver):
    name = "cmd_drv"
    description = "Runtime Test Driver"

    def __init__(self, kernel):
        super().__init__(kernel)
        self.started = False
        self.stopped = False

    def on_load(self):
        pass

    def start(self):
        self.started = True

    def stop(self):
        self.stopped = True
"""

    kernel.fs.write("/usr/lib/python/runtime_drv.py", driver_content)

    assert shell.execute("driver load pureos_vfs.runtime_drv CmdDriver") is True
    driver = kernel.drivers.drivers.get("cmd_drv")
    assert driver is not None
    assert driver.started is True
    assert driver.state == "running"

    assert shell.execute("driver stop cmd_drv") is True
    assert driver.stopped is True
    assert driver.state == "stopped"

    assert shell.execute("driver start cmd_drv") is True
    assert driver.state == "running"

    out = shell.registry.execute("driver status cmd_drv", capture_output=True)
    assert "cmd_drv: running" in out

    out = shell.registry.execute("driver list", capture_output=True)
    assert "cmd_drv [running]" in out

    assert shell.execute("driver unload cmd_drv") is True
    assert "cmd_drv" not in kernel.drivers.drivers


def test_driver_command(kernel, shell):
    """Test the 'driver' shell command."""
    # Write a driver to VFS
    driver_content = """
from pureos.drivers.base import Driver
class CmdDriver(Driver):
    name = "cmd_drv"
    description = "Test Driver"
    def on_load(self): print("CMD_DRV_LOADED")
"""
    kernel.fs.write("/usr/lib/python/drv_mod.py", driver_content)

    # Load via command
    shell.execute("driver load pureos_vfs.drv_mod CmdDriver")
    assert "cmd_drv" in kernel.drivers.drivers

    # List via command
    # We capture output to verify
    out = shell.registry.execute("driver list", capture_output=True)
    assert "cmd_drv" in out
    assert "Test Driver" in out

    # Unload via command
    shell.execute("driver unload cmd_drv")
    assert "cmd_drv" not in kernel.drivers.drivers


def test_vfs_importer_cleanup(kernel):
    """Test that sys.meta_path is cleaned up on shutdown."""
    from pureos.fs.importer import VFSImporter

    # Verify importer is present
    importers = [
        i for i in sys.meta_path if isinstance(i, VFSImporter) and i.fs == kernel.fs
    ]
    assert len(importers) == 1

    kernel.shutdown()

    # Verify importer is removed
    importers = [
        i for i in sys.meta_path if isinstance(i, VFSImporter) and i.fs == kernel.fs
    ]
    assert len(importers) == 0
