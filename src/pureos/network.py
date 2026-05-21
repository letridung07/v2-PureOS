"""Minimal networking utilities for v2-PureOS."""

import random
import socket
import struct
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


def _skip_dns_name(data: bytes, offset: int) -> int:
    while True:
        if offset >= len(data):
            raise ValueError("Malformed DNS payload")
        length = data[offset]
        if length & 0xC0 == 0xC0:
            return offset + 2
        if length == 0:
            return offset + 1
        offset += 1 + length


def _parse_nameserver(nameserver: str) -> Tuple[str, int]:
    parts = nameserver.strip().split("#", 1)
    host = parts[0].strip()
    port = 53
    if len(parts) == 2 and parts[1].strip():
        try:
            port = int(parts[1].strip())
        except ValueError:
            raise ValueError(f"Invalid nameserver port: {nameserver}")
    if not host:
        raise ValueError(f"Invalid nameserver address: {nameserver}")
    return host, port


def query_dns_a(nameserver: str, host: str, timeout: float = 2.0) -> str:
    ns_host, ns_port = _parse_nameserver(nameserver)
    server_addr = (ns_host, ns_port)
    question_labels = host.split(".")
    if not question_labels or any(not label for label in question_labels):
        raise ValueError("Invalid hostname for DNS query")

    transaction_id = random.randrange(0, 0x10000)
    header = struct.pack("!HHHHHH", transaction_id, 0x0100, 1, 0, 0, 0)
    qname = b"".join(
        len(label).to_bytes(1, "big") + label.encode("ascii")
        for label in question_labels
    ) + b"\x00"
    question = qname + struct.pack("!HH", 1, 1)

    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
        sock.settimeout(timeout)
        sock.sendto(header + question, server_addr)
        data, _ = sock.recvfrom(512)

    if len(data) < 12:
        raise ValueError("Invalid DNS response")

    resp_id, flags, qdcount, ancount, _, _ = struct.unpack("!HHHHHH", data[:12])
    if resp_id != transaction_id:
        raise ValueError("DNS transaction ID mismatch")
    rcode = flags & 0x000F
    if rcode != 0:
        raise ValueError(f"DNS query failed with rcode {rcode}")

    offset = 12
    for _ in range(qdcount):
        offset = _skip_dns_name(data, offset)
        offset += 4
    for _ in range(ancount):
        offset = _skip_dns_name(data, offset)
        if offset + 10 > len(data):
            raise ValueError("Malformed DNS answer")
        rtype, rclass, _, rdlength = struct.unpack("!HHIH", data[offset : offset + 10])
        offset += 10
        if rtype == 1 and rclass == 1 and rdlength == 4:
            if offset + 4 > len(data):
                raise ValueError("Malformed DNS A record")
            return socket.inet_ntoa(data[offset : offset + 4])
        offset += rdlength

    raise ValueError("No A record found in DNS answer")


def resolve_host(fs, host: str) -> str:
    """Resolve a hostname.

    Lookup order:
    1. /etc/hosts (VirtualFS)
    2. /etc/resolv.conf nameserver hints
    3. Real system resolver via socket.gethostbyname()
    """
    try:
        socket.inet_aton(host)
        return host
    except OSError:
        pass

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

    nameservers = get_nameservers(fs)
    for nameserver in nameservers:
        try:
            return query_dns_a(nameserver, host)
        except Exception:
            continue

    return socket.gethostbyname(host)


def get_nameservers(fs) -> List[str]:
    """Return configured nameservers from /etc/resolv.conf."""
    servers: List[str] = []
    if fs.exists("/etc/resolv.conf"):
        try:
            content = fs.read("/etc/resolv.conf") or ""
            for line in content.splitlines():
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                if line.startswith("nameserver"):
                    parts = line.split()
                    if len(parts) >= 2:
                        servers.append(parts[1])
        except Exception:
            pass
    return servers or ["8.8.8.8"]  # sensible default
