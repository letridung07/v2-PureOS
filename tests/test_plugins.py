import sys
import pytest
from pureos.kernel import Kernel
from pureos.drivers import Driver

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
            
        def on_load(self): self.loaded = True
        def start(self): self.started = True
        def stop(self): self.stopped = True
        def on_unload(self): self.unloaded = True

    dm = kernel.drivers
    drv = dm.load_driver(MockDriver)
    
    assert drv.loaded is True
    assert "mock_drv" in dm.drivers
    
    dm.start_all()
    assert drv.started is True
    
    dm.unload_driver("mock_drv")
    assert drv.stopped is True
    assert drv.unloaded is True
    assert "mock_drv" not in dm.drivers

def test_driver_command(kernel, shell):
    """Test the 'driver' shell command."""
    # Write a driver to VFS
    driver_content = """
from pureos.drivers import Driver
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
    importers = [i for i in sys.meta_path if isinstance(i, VFSImporter) and i.fs == kernel.fs]
    assert len(importers) == 1
    
    kernel.shutdown()
    
    # Verify importer is removed
    importers = [i for i in sys.meta_path if isinstance(i, VFSImporter) and i.fs == kernel.fs]
    assert len(importers) == 0
