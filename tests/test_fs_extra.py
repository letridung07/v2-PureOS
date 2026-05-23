import importlib
import os
import sys

import pytest

try:
    fs_mod = importlib.import_module("pureos.fs")
except Exception:
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
    fs_mod = importlib.import_module("pureos.fs")

VirtualFS = fs_mod.VirtualFS


def test_virtualfs_persistence(tmp_path):
    backing = tmp_path / "store.json"
    v = VirtualFS(backing_path=str(backing))
    v.format()
    v.write("/foo", "bar")
    v.append("/foo", "baz")
    assert v.read("/foo") == "barbaz"
    v.copy("/foo", "/foo_copy")
    assert v.read("/foo_copy") == "barbaz"
    v.rename("/foo_copy", "/foo2")
    assert v.read("/foo2") == "barbaz"
    v.delete("/foo2")
    assert v.read("/foo2") is None

    # ensure backing file exists and reload
    v2 = VirtualFS(backing_path=str(backing))
    assert "/etc/" in v2.list()


def test_virtualfs_directories_and_normalization(tmp_path):
    backing = tmp_path / "store.json"
    v = VirtualFS(backing_path=str(backing))
    v.format()
    v.mkdir("/tmp/dir")
    assert v.exists("/tmp/dir")
    assert v.is_dir("/tmp/dir")
    assert v.exists("/tmp/dir/")


def test_virtualfs_load_ignores_corrupted_backing(tmp_path):
    backing = tmp_path / "store.json"
    backing.write_text("{ invalid json")
    v = VirtualFS(backing_path=str(backing))
    assert v.has_content() is False
    assert v.read("/etc/motd") is None

    v.write("/tmp/dir/file.txt", "hello")
    assert v.read("/tmp/dir/file.txt") == "hello"
    assert v.is_file("/tmp/dir/file.txt")

    # list should include the direct directory child, not nested descendants
    listed = v.list("/tmp")
    assert "/tmp/dir/" in listed
    assert "/tmp/dir/file.txt" not in listed

    v.copy("/tmp/dir", "/backup/dir")
    assert v.read("/backup/dir/file.txt") == "hello"

    v.rename("/backup/dir", "/backup/dir2")
    assert v.exists("/backup/dir2/")
    assert v.read("/backup/dir2/file.txt") == "hello"

    v.delete("/backup/dir2")
    assert not v.exists("/backup/dir2")

    v2 = VirtualFS(backing_path=str(backing))
    assert v2.exists("/tmp/dir/")
    assert "/etc/" not in v2.list("/")


def test_virtualfs_copy_rename_subdir_disallowed(tmp_path):
    backing = tmp_path / "store.json"
    v = VirtualFS(backing_path=str(backing))
    v.format()
    v.mkdir("/tmp")
    v.write("/tmp/file.txt", "hello")

    with pytest.raises(ValueError):
        v.rename("/tmp", "/tmp/backup")

    with pytest.raises(ValueError):
        v.copy("/tmp", "/tmp/backup")


def test_virtualfs_permissions_and_listing(tmp_path):
    backing = tmp_path / "store.json"
    v = VirtualFS(backing_path=str(backing))
    v.format()
    v.mkdir("/tmp")
    v.write("/tmp/a", "hello")
    v.chmod("/tmp/a", 0o000)

    with pytest.raises(PermissionError):
        v.read("/tmp/a")
    with pytest.raises(PermissionError):
        v.write("/tmp/a", "x")

    v.chmod("/tmp/", 0o500)
    with pytest.raises(PermissionError):
        v.write("/tmp/new", "x")

    v.chmod("/tmp/", 0o700)
    v.write("/tmp/new", "x")
    assert v.read("/tmp/new") == "x"

    v.mkdir("/tmp/dir")
    v.mkdir("/tmp/dir/sub")
    v.write("/tmp/dir/file.txt", "hello")
    v.write("/tmp/dir/sub/file2.txt", "world")

    assert sorted(v.list("/tmp/dir/")) == ["/tmp/dir/file.txt", "/tmp/dir/sub/"]
    assert "/tmp/dir/sub/file2.txt" in v.find("/tmp/dir/")

    v.write("/foo", "bar")
    with pytest.raises(PermissionError):
        v.write("/foo/bar", "baz")
    with pytest.raises(PermissionError):
        v.mkdir("/foo/sub")


def test_grep_advanced_flags(tmp_path):
    from pureos.core.kernel import Kernel

    k = Kernel(config={"fs_backing": str(tmp_path / "store.json")})
    k.initialize()
    sh = k.shell

    # Create file
    k.fs.write("/tmp/grep_test", "Apple\nBanana\ncherry\napple pie\n")

    # Test basic matching
    out = sh.registry.execute(["grep", "Apple", "/tmp/grep_test"], capture_output=True)
    assert out == "Apple"

    # Test case-insensitive matching (-i)
    out = sh.registry.execute(
        ["grep", "-i", "apple", "/tmp/grep_test"], capture_output=True
    )
    assert "Apple" in out
    assert "apple pie" in out
    assert "Banana" not in out

    # Test invert match (-v)
    out = sh.registry.execute(
        ["grep", "-v", "Apple", "/tmp/grep_test"], capture_output=True
    )
    assert "Banana" in out
    assert "cherry" in out
    assert "apple pie" in out
    assert "Apple" not in out

    # Test line numbers (-n)
    out = sh.registry.execute(
        ["grep", "-n", "Banana", "/tmp/grep_test"], capture_output=True
    )
    assert out == "2:Banana"

    # Test combination (-inv)
    out = sh.registry.execute(
        ["grep", "-inv", "apple", "/tmp/grep_test"], capture_output=True
    )
    assert "2:Banana" in out
    assert "3:cherry" in out
    assert "1:Apple" not in out
    assert "4:apple pie" not in out

    # Test stdin / pipe capability
    out = sh.registry.execute(
        ["grep", "-i", "cherry"], input_data="Cherry\nbanana", capture_output=True
    )
    assert out == "Cherry"

    k.shutdown()


def test_which_command(tmp_path):
    from pureos.core.kernel import Kernel

    k = Kernel(config={"fs_backing": str(tmp_path / "store.json")})
    k.initialize()
    sh = k.shell

    # Test regular command locate
    out = sh.registry.execute(["which", "ls"], capture_output=True)
    assert "shell built-in command" in out
    assert "LsCommand" in out

    # Test alias locate
    sh.execute("alias fools ls -la")
    out = sh.registry.execute(["which", "fools"], capture_output=True)
    assert "aliased to ls -la" in out

    # Test nonexistent command
    out = sh.registry.execute(["which", "nonexistent"], capture_output=True)
    assert "not found" in out

    k.shutdown()


def test_sleep_command(tmp_path):
    from pureos.core.kernel import Kernel
    import time

    k = Kernel(config={"fs_backing": str(tmp_path / "store.json")})
    k.initialize()
    sh = k.shell

    # Test that sleep blocks for the given time
    t0 = time.time()
    sh.execute("sleep 0.2")
    duration = time.time() - t0
    assert duration >= 0.15

    # Test scheduler background sleep / kill responsiveness
    p = k.scheduler.spawn("sleep 10")
    assert p.status == "running"
    time.sleep(0.05)
    # Kill the sleep process
    k.scheduler.kill(p.pid)
    assert p.status == "killed"

    k.shutdown()
