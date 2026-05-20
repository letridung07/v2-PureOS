"""Minimal networking utilities for v2-PureOS."""

import socket
import threading
from typing import List, Tuple


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


def resolve_host(fs, host: str) -> str:
    """Resolve a hostname.

    Lookup order:
    1. /etc/hosts (VirtualFS)
    2. /etc/resolv.conf nameserver hints (informational — real socket still used)
    3. Real system resolver via socket.gethostbyname()
    """
    # 1. Check /etc/hosts in the virtual filesystem
    if fs.exists("/etc/hosts"):
        try:
            content = fs.read("/etc/hosts") or ""
            for line in content.splitlines():
                line = line.split("#")[0].strip()
                parts = line.split()
                if len(parts) >= 2 and host in parts[1:]:
                    return parts[0]
        except Exception:
            pass

    # 2. /etc/resolv.conf is present but we still delegate to the real resolver
    # (nameservers are logged for simulation fidelity)
    # 3. Fall back to real system resolver
    return socket.gethostbyname(host)


def get_nameservers(fs) -> List[str]:
    """Return configured nameservers from /etc/resolv.conf."""
    servers: List[str] = []
    if fs.exists("/etc/resolv.conf"):
        try:
            content = fs.read("/etc/resolv.conf") or ""
            for line in content.splitlines():
                line = line.strip()
                if line.startswith("nameserver"):
                    parts = line.split()
                    if len(parts) >= 2:
                        servers.append(parts[1])
        except Exception:
            pass
    return servers or ["8.8.8.8"]  # sensible default
