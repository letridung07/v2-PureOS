import pytest
from pureos.core.kernel import Kernel
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


def test_pkg_immediate_unregistration(kernel, shell):
    pkg_dir = "/usr/lib/pureos/packages/"
    kernel.fs.mkdir(pkg_dir, parents=True)
    kernel.fs.write(
        f"{pkg_dir}removable.py",
        """
class RemovableCommand(Command):
    name = "removable"
    def execute(self, parts, **kwargs):
        return "I am here"
""",
    )
    shell.registry.load_from_vfs(f"{pkg_dir}removable.py")
    assert "removable" in shell.registry.commands

    # Remove package
    shell.execute("pkg remove removable")

    # Verify it is GONE from registry
    assert "removable" not in shell.registry.commands


def test_pkg_persistence(kernel):
    # Setup persistent state
    pkg_dir = "/usr/lib/pureos/packages/"
    kernel.fs.mkdir(pkg_dir, parents=True)
    kernel.fs.write(
        f"{pkg_dir}greet.py",
        """
class GreetCommand(Command):
    name = "greet"
    def execute(self, parts, input_data=None, capture_output=False, raw_line=None):
        print("Greetings!")
        return True
""",
    )

    # Reset registry to simulate new kernel state but keep FS
    kernel.shell.registry.commands.pop("greet", None)
    assert "greet" not in kernel.shell.registry.commands

    # We must ensure boot sequence DOES NOT format the FS
    kernel.config.format_on_boot = False

    # Re-run boot sequence
    from pureos.core.boot import run_boot_sequence

    run_boot_sequence(kernel)

    # Verify greet was auto-loaded
    assert "greet" in kernel.shell.registry.commands


@patch("urllib.request.urlopen")
def test_pkg_install_command(mock_urlopen, kernel, shell):
    # Mock the web response
    mock_response = MagicMock()
    # Content WITHOUT the problematic import
    mock_response.read.return_value = (
        b"class WebCmd(Command):\n"
        b'    name = "webcmd"\n'
        b"    def execute(self, parts, **kwargs):\n"
        b'        print("web ok")\n'
        b"        return True"
    )
    mock_response.__enter__.return_value = mock_response
    mock_urlopen.return_value = mock_response

    # Run pkg install
    res = shell.execute("pkg install http://example.com/webcmd.py webcmd")
    assert res is True

    # Verify it works
    assert "webcmd" in shell.registry.commands
    out = shell.registry.execute(["webcmd"], capture_output=True)
    assert out == "web ok"


def test_pkg_protect_system_commands(kernel, shell):
    pkg_dir = "/usr/lib/pureos/packages/"
    kernel.fs.mkdir(pkg_dir, parents=True)

    # Try to overwrite 'ls'
    pkg_content = """
class LsCommand(Command):
    name = "ls"
    def execute(self, parts, **kwargs):
        print("I am fake ls")
        return True
"""
    file_path = f"{pkg_dir}fake_ls.py"
    kernel.fs.write(file_path, pkg_content)

    # Should fail to register 'ls'
    res = shell.registry.load_from_vfs(file_path)
    assert res is False

    # Verify original ls is still there
    from pureos.commands.fs.core import LsCommand

    assert isinstance(shell.registry.commands["ls"], LsCommand)


def test_pkg_clobber_revert(kernel, shell):
    pkg_dir = "/usr/lib/pureos/packages/"
    kernel.fs.mkdir(pkg_dir, parents=True)

    # Package A defines 'foo'
    kernel.fs.write(
        f"{pkg_dir}pkgA.py",
        """
class FooA(Command):
    name = "foo"
    def execute(self, parts, **kwargs):
        return "A"
""",
    )
    # Package B defines 'foo' (shadows A)
    kernel.fs.write(
        f"{pkg_dir}pkgB.py",
        """
class FooB(Command):
    name = "foo"
    def execute(self, parts, **kwargs):
        return "B"
""",
    )

    shell.registry.load_from_vfs(f"{pkg_dir}pkgA.py")
    assert shell.registry.execute(["foo"], capture_output=True) == "A"

    shell.registry.load_from_vfs(f"{pkg_dir}pkgB.py")
    assert shell.registry.execute(["foo"], capture_output=True) == "B"

    # Remove Package B - should revert to Package A
    shell.execute("pkg remove pkgB")
    assert "foo" in shell.registry.commands
    assert shell.registry.execute(["foo"], capture_output=True) == "A"

    # Remove Package A - should be gone
    shell.execute("pkg remove pkgA")
    assert "foo" not in shell.registry.commands


def test_pkg_format_clears_registry(kernel, shell):
    pkg_dir = "/usr/lib/pureos/packages/"
    kernel.fs.mkdir(pkg_dir, parents=True)
    kernel.fs.write(
        f"{pkg_dir}fmt.py",
        """
class FmtCommand(Command):
    name = "fmtcmd"
    def execute(self, parts, **kwargs):
        return "alive"
""",
    )
    shell.registry.load_from_vfs(f"{pkg_dir}fmt.py")
    assert "fmtcmd" in shell.registry.commands

    # Run format
    shell.execute("format")

    # Verify both VFS and Registry are clean
    assert not kernel.fs.exists(f"{pkg_dir}fmt.py")
    assert "fmtcmd" not in shell.registry.commands


def test_pkg_background_execution(kernel, shell):
    # Register a dynamic command that writes to a temporary file
    pkg_content = """
class GreetFileCommand(Command):
    name = "greetfile"
    def execute(self, parts, input_data=None, capture_output=False, raw_line=None):
        self.kernel.fs.write("/tmp/dynamic_out", "Greetings from background!")
        return True
"""
    pkg_dir = "/usr/lib/pureos/packages/"
    kernel.fs.mkdir(pkg_dir, parents=True)
    file_path = f"{pkg_dir}greetfile.py"
    kernel.fs.write(file_path, pkg_content)

    # Load the package
    res = shell.registry.load_from_vfs(file_path)
    assert res is True

    # Execute it in the background using '&'
    shell.execute("greetfile &")

    # Give the thread a moment to start and run
    import time

    success = False
    for _ in range(20):
        if kernel.fs.exists("/tmp/dynamic_out"):
            content = kernel.fs.read("/tmp/dynamic_out")
            if content == "Greetings from background!":
                success = True
                break
        time.sleep(0.05)

    assert success is True
