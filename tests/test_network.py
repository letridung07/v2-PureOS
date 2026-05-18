import importlib
import os
import sys
import socket
import time

try:
    net_mod = importlib.import_module("pureos.network")
except Exception:
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
    net_mod = importlib.import_module("pureos.network")

start_echo_server = net_mod.start_echo_server


def test_echo_server():
    port, thread, stop_event = start_echo_server()
    time.sleep(0.05)
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.connect(("127.0.0.1", port))
    s.sendall(b"hello")
    data = s.recv(4096)
    s.close()
    stop_event.set()
    thread.join(timeout=1.0)
    assert data == b"hello"
