import importlib
import os
import sys
from unittest.mock import patch

try:
    kernel_mod = importlib.import_module("pureos.core.kernel")
except Exception:
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
    kernel_mod = importlib.import_module("pureos.core.kernel")

Kernel = kernel_mod.Kernel


def test_editor(tmp_path):
    k = Kernel(config={"fs_backing": str(tmp_path / "store.json")})
    k.initialize()
    sh = k.shell

    # Mock inputs for the editor
    # Inputs:
    # 1. line 1
    # 2. line 2
    # 3. :l (list)
    # 4. :d 1 (delete line 1)
    # 5. :a 1 line 3 (insert line 3 after line 1)
    # 6. :wq (write and quit)
    mock_inputs = ["line 1", "line 2", ":l", ":d 1", ":a 1 line 3", ":wq"]
    with patch("builtins.input", side_effect=mock_inputs):
        sh.execute("edit /file.txt")

    # Content should be:
    # originally: ["line 1", "line 2"]
    # after :d 1: ["line 2"]
    # after :a 1 line 3: ["line 2", "line 3"]
    # So the saved content is "line 2\nline 3"
    assert k.fs.read("/file.txt") == "line 2\nline 3"

    # Test quit without saving (:q)
    mock_inputs_q = ["new line", ":q"]
    with patch("builtins.input", side_effect=mock_inputs_q):
        sh.execute("edit /file.txt")
    # Content should remain the same
    assert k.fs.read("/file.txt") == "line 2\nline 3"

    k.shutdown()
