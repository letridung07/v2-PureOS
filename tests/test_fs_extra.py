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
    assert "/etc/" in v2.list("/")


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

    v.write('/foo', 'bar')
    with pytest.raises(PermissionError):
        v.write('/foo/bar', 'baz')
    with pytest.raises(PermissionError):
        v.mkdir('/foo/sub')
