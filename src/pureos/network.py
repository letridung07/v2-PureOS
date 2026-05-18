"""Minimal networking helpers for v2-PureOS."""

import socket
import threading
from typing import Tuple


def start_echo_server(
    host: str = "127.0.0.1", port: int = 0
) -> Tuple[int, threading.Thread, threading.Event]:
    """Start a simple TCP echo server in a background thread.

    Returns (port, thread, stop_event). If port is 0 an ephemeral port is selected.
    """
    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    srv.bind((host, port))
    srv.listen(1)
    selected_port = srv.getsockname()[1]
    stop_event = threading.Event()

    def serve():
        srv.settimeout(0.5)
        try:
            while not stop_event.is_set():
                try:
                    conn, _ = srv.accept()
                except socket.timeout:
                    continue
                with conn:
                    data = conn.recv(4096)
                    if data:
                        conn.sendall(data)
        finally:
            try:
                srv.close()
            except Exception:
                pass

    t = threading.Thread(target=serve, daemon=True)
    t.start()
    return selected_port, t, stop_event
