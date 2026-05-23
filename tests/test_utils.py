import importlib
import os
import sys

try:
    utils_mod = importlib.import_module("pureos.core.utils")
except Exception:
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
    utils_mod = importlib.import_module("pureos.core.utils")

human_list = utils_mod.human_list


def test_human_list_empty():
    assert human_list([]) == ""


def test_human_list_numbers():
    assert human_list([1, 2, 3]) == "1, 2, 3"


def test_human_list_strings():
    assert human_list(["a", "b", "c"]) == "a, b, c"
