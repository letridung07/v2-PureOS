import importlib
import os
import sys

try:
    fs_mod = importlib.import_module("pureos.fs")
except Exception:
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
    fs_mod = importlib.import_module("pureos.fs")

VirtualFS = fs_mod.VirtualFS


def test_persistent_fs(tmp_path):
    store = tmp_path / "store.json"
    a = VirtualFS(backing_path=str(store))
    a.format()
    a.write("/var/data", "hello")
    a.copy("/var/data", "/var/data2")
    a.rename("/var/data2", "/var/data3")

    b = VirtualFS(backing_path=str(store))
    assert b.read("/var/data") == "hello"
    assert b.read("/var/data3") == "hello"
