import os
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
import pureos


def test_smoke():
    k = pureos.run(shell=False)
    assert k is not None
