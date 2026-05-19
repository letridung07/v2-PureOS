import pytest
from pureos.kernel import Kernel
from unittest.mock import patch, MagicMock


@pytest.fixture
def kernel():
    k = Kernel({"format_on_boot": True, "auto_start_services": False})
    k.initialize()
    return k


@pytest.fixture
def shell(kernel):
    return kernel.shell


def test_pkg_install_and_execute(kernel, shell):
    # Mock content for a new command
    pkg_content = """
class HelloCommand(Command):
    name = "hello"
    description = "A test hello command"
    
    def execute(self, parts, input_data=None, capture_output=False, raw_line=None):
        out = "Hello from dynamic package!"
        if capture_output:
            return out
        print(out)
        return True
"""
    # Simulate pkg install by writing directly to VFS and calling load_from_vfs
    pkg_dir = "/usr/lib/pureos/packages/"
    kernel.fs.mkdir(pkg_dir)
    file_path = f"{pkg_dir}hello.py"
    kernel.fs.write(file_path, pkg_content)
    
    # Load the package
    res = shell.registry.load_from_vfs(file_path)
    assert res is True
    
    # Verify command is registered
    assert "hello" in shell.registry.commands
    
    # Execute the command
    out = shell.registry.execute(["hello"], capture_output=True)
    assert out == "Hello from dynamic package!"


def test_pkg_list_and_remove(kernel, shell):
    pkg_dir = "/usr/lib/pureos/packages/"
    kernel.fs.mkdir(pkg_dir, parents=True)
    kernel.fs.write(f"{pkg_dir}test1.py", "pass")
    kernel.fs.write(f"{pkg_dir}test2.py", "pass")
    
    # Test pkg list
    out = shell.registry.execute(["pkg", "list"], capture_output=True)
    assert "test1" in out
    assert "test2" in out
    
    # Test pkg remove
    shell.execute("pkg remove test1")
    assert not kernel.fs.exists(f"{pkg_dir}test1.py")
    assert kernel.fs.exists(f"{pkg_dir}test2.py")


def test_pkg_persistence(kernel):
    # Setup persistent state
    pkg_dir = "/usr/lib/pureos/packages/"
    kernel.fs.mkdir(pkg_dir, parents=True)
    kernel.fs.write(f"{pkg_dir}greet.py", """
class GreetCommand(Command):
    name = "greet"
    def execute(self, parts, input_data=None, capture_output=False, raw_line=None):
        print("Greetings!")
        return True
""")
    
    # Reset registry to simulate new kernel state but keep FS
    kernel.shell.registry.commands.pop("greet", None)
    assert "greet" not in kernel.shell.registry.commands
    
    # We must ensure boot sequence DOES NOT format the FS
    kernel.config.format_on_boot = False
    
    # Re-run boot sequence
    from pureos.boot import run_boot_sequence
    run_boot_sequence(kernel)
    
    # Verify greet was auto-loaded
    assert "greet" in kernel.shell.registry.commands


@patch("urllib.request.urlopen")
def test_pkg_install_command(mock_urlopen, kernel, shell):
    # Mock the web response
    mock_response = MagicMock()
    # Content WITHOUT the problematic import
    mock_response.read.return_value = b'class WebCmd(Command):\n    name = "webcmd"\n    def execute(self, parts, **kwargs):\n        print("web ok")\n        return True'
    mock_response.__enter__.return_value = mock_response
    mock_urlopen.return_value = mock_response
    
    # Run pkg install
    res = shell.execute("pkg install http://example.com/webcmd.py webcmd")
    assert res is True
    
    # Verify it works
    assert "webcmd" in shell.registry.commands
    out = shell.registry.execute(["webcmd"], capture_output=True)
    assert out == "web ok"
