import importlib
import os
import sys

try:
    pureos = importlib.import_module("pureos")
except Exception:
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
    pureos = importlib.import_module("pureos")


def test_smoke():
    k = pureos.run(shell=False)
    assert k is not None
