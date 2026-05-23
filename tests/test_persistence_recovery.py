import os
import importlib
import sys

try:
    kernel_mod = importlib.import_module("pureos.core.kernel")
except Exception:
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
    kernel_mod = importlib.import_module("pureos.core.kernel")

Kernel = kernel_mod.Kernel


def test_persistence_recovers_from_corrupt_backing(tmp_path):
    backing = tmp_path / "store.json"
    k1 = Kernel(config={"fs_backing": str(backing)})
    k1.initialize()
    # write a file so persistence has something
    k1.fs.write("/var/data", "hello")
    k1.shutdown()

    # Corrupt the backing file
    with open(backing, "w", encoding="utf-8") as f:
        f.write("not a json")

    # Creating a new Kernel should attempt to load and recover the corrupt file
    k2 = Kernel(config={"fs_backing": str(backing)})
    k2.initialize()

    # Either the persistence code recovered from a .bak or moved the corrupt
    # file to a .corrupt.* path. Accept either behavior and ensure filesystem
    # is valid after initialization.
    corrupt_present = any(
        p.name.startswith(backing.name + ".corrupt.") for p in tmp_path.iterdir()
    )
    data_restored = k2.fs.read("/var/data") == "hello"
    assert corrupt_present or data_restored
    # And the new kernel should have a valid, initialized filesystem (root exists)
    assert k2.fs.is_dir("/")
    k2.shutdown()
