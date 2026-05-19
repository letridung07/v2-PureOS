import time
import socket
from unittest.mock import patch
import pytest

from pureos.kernel import Kernel

def test_general_redirection(tmp_path, capsys):
    k = Kernel(config={"fs_backing": str(tmp_path / "store.json")})
    k.initialize()
    sh = k.shell
    
    # Test ls redirection
    sh.execute("mkdir /tmp")
    sh.execute("touch /tmp/a")
    sh.execute("ls /tmp > /tmp/out")
    assert k.fs.read("/tmp/out") == "/tmp/a"
    
    # Test ps redirection
    sh.execute("spawn test_proc")
    sh.execute("ps > /tmp/ps_out")
    ps_content = k.fs.read("/tmp/ps_out")
    assert "test_proc" in ps_content
    
    # Test append redirection
    sh.execute("echo hello > /tmp/out")
    sh.execute("echo world >> /tmp/out")
    assert k.fs.read("/tmp/out") == "helloworld"
    
    # Clean shutdown
    k.shutdown()

def test_system_stats(tmp_path):
    k = Kernel(config={"fs_backing": str(tmp_path / "store.json")})
    k.initialize()
    sh = k.shell

    # uptime
    assert "uptime: " in k.shell.registry.execute(["uptime"], capture_output=True)

    # date
    assert len(k.shell.registry.execute(["date"], capture_output=True)) > 0

    # df
    df_out = k.shell.registry.execute(["df"], capture_output=True)
    assert "filesystem" in df_out.lower()
    assert "virtualfs" in df_out

    # free
    free_out = k.shell.registry.execute(["free"], capture_output=True)
    assert "Mem:" in free_out
    assert "Swap:" in free_out

    k.shutdown()

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
    mock_inputs = [
        "line 1",
        "line 2",
        ":l",
        ":d 1",
        ":a 1 line 3",
        ":wq"
    ]
    with patch("builtins.input", side_effect=mock_inputs):
        sh.execute("edit /file.txt")

    # Content should be:
    # originally: ["line 1", "line 2"]
    # after :d 1: ["line 2"]
    # after :a 1 line 3: ["line 2", "line 3"]
    # So the saved content is "line 2\nline 3"
    assert k.fs.read("/file.txt") == "line 2\nline 3"

    # Test quit without saving (:q)
    mock_inputs_q = [
        "new line",
        ":q"
    ]
    with patch("builtins.input", side_effect=mock_inputs_q):
        sh.execute("edit /file.txt")
    # Content should remain the same
    assert k.fs.read("/file.txt") == "line 2\nline 3"

    k.shutdown()

def test_networking(tmp_path, capsys):
    k = Kernel(config={"fs_backing": str(tmp_path / "store.json")})
    k.initialize()
    sh = k.shell

    # Test ifconfig
    if_out = sh.registry.execute(["ifconfig"], capture_output=True)
    assert "lo0" in if_out
    assert "eth0" in if_out

    # Test ping (resolution)
    ping_out1 = sh.registry.execute(["ping", "localhost"], capture_output=True)
    assert "Ping successful" in ping_out1

    # Test ping (port)
    ping_out2 = sh.registry.execute(["ping", "127.0.0.1", "50007"], capture_output=True)
    assert "Ping failed" in ping_out2  # Echo server is not running yet

    # Start echo_server service
    sh.execute("service start echo_server")
    time.sleep(0.5)

    # Now ping should succeed
    ping_out3 = sh.registry.execute(["ping", "127.0.0.1", "50007"], capture_output=True)
    assert "Ping successful" in ping_out3

    # Test netcat (nc)
    nc_out = sh.registry.execute(["nc", "127.0.0.1", "50007", "hello OS"], capture_output=True)
    assert nc_out == "hello OS"

    # Test netcat via pipeline
    sh.execute("echo piped hello | nc 127.0.0.1 50007 > /tmp/nc_out")
    assert k.fs.read("/tmp/nc_out") == "piped hello"

    # Stop echo_server service
    sh.execute("service stop echo_server")
    k.shutdown()
