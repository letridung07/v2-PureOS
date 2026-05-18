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
