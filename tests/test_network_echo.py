import importlib
import os
import sys
import socket

try:
    net_mod = importlib.import_module("pureos.network")
except Exception:
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
    net_mod = importlib.import_module("pureos.network")

start_echo_server = net_mod.start_echo_server


def test_echo_server():
    port, thread, stop_event = start_echo_server(host="127.0.0.1", port=0)
    s = socket.create_connection(("127.0.0.1", port), timeout=1)
    msg = b"hello"
    s.sendall(msg)
    data = s.recv(1024)
    assert data == msg
    s.close()
    stop_event.set()
    thread.join(timeout=1)
    assert not thread.is_alive()
