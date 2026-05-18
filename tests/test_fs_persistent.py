import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from pureos.fs import VirtualFS


def test_persistent_fs(tmp_path):
    store = tmp_path / "store.json"
    a = VirtualFS(backing_path=str(store))
    a.format()
    a.write("/var/data", "hello")

    b = VirtualFS(backing_path=str(store))
    assert b.read("/var/data") == "hello"
