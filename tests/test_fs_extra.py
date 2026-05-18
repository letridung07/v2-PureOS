import importlib
import os
import sys

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
    assert "/etc/motd" in v2.list()


def test_virtualfs_directories_and_normalization(tmp_path):
    backing = tmp_path / "store.json"
    v = VirtualFS(backing_path=str(backing))
    v.format()
    v.mkdir("/tmp/dir")
    assert v.exists("/tmp/dir")
    assert v.is_dir("/tmp/dir")
    assert v.exists("/tmp/dir/")

    v.write("/tmp/dir/file.txt", "hello")
    assert v.read("/tmp/dir/file.txt") == "hello"
    assert v.is_file("/tmp/dir/file.txt")

    # list should include nested directory and file paths
    listed = v.list("/tmp")
    assert "/tmp/dir/" in listed
    assert "/tmp/dir/file.txt" in listed

    v.copy("/tmp/dir", "/backup/dir")
    assert v.read("/backup/dir/file.txt") == "hello"

    v.rename("/backup/dir", "/backup/dir2")
    assert v.exists("/backup/dir2/")
    assert v.read("/backup/dir2/file.txt") == "hello"

    v.delete("/backup/dir2")
    assert not v.exists("/backup/dir2")

    v2 = VirtualFS(backing_path=str(backing))
    assert v2.exists("/tmp/dir/")
    assert "/etc/motd" in v2.list("/")
