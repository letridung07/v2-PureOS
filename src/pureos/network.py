"""Minimal networking utilities for v2-PureOS."""

import json
import random
import socket
import struct
import threading
from typing import Dict, List, Optional, Tuple

from .drivers import Driver


class NetworkDriver(Driver):
    """Manages simulated network hardware and states."""

    name = "network"
    description = "Network state management driver"

    def __init__(self, kernel):
        super().__init__(kernel)
        self.interfaces = {
            "eth0": {
                "up": True,
                "ip": "192.168.1.105",
                "mac": "00:11:22:33:44:55",
                "mask": "255.255.255.0",
            },
            "lo0": {
                "up": True,
                "ip": "127.0.0.1",
                "mac": "00:00:00:00:00:00",
                "mask": "255.0.0.0",
            },
        }
        self.arp_table: Dict[str, str] = {}
        self.routing_table: List[dict] = [
            {"dest": "0.0.0.0/0", "gw": "192.168.1.1", "iface": "eth0"},
            {"dest": "127.0.0.0/8", "gw": "0.0.0.0", "iface": "lo0"},
        ]
        self.sockets: List[dict] = []  # List of {proto, state, local, remote, pid}
        self._lock = threading.Lock()

    def on_load(self):
        self.load_arp_cache()

    def load_arp_cache(self):
        cache_path = "/etc/arp.cache"
        if self.kernel.fs.exists(cache_path):
            try:
                content = self.kernel.fs.read(cache_path)
                if content:
                    self.arp_table = json.loads(content)
            except Exception:
                self.logger.warning("Failed to load ARP cache")

    def save_arp_cache(self):
        cache_path = "/etc/arp.cache"
        try:
            self.kernel.fs.write(cache_path, json.dumps(self.arp_table))
        except Exception:
            self.logger.warning("Failed to save ARP cache")

    def add_arp_entry(self, ip: str, mac: str):
        with self._lock:
            self.arp_table[ip] = mac
        self.save_arp_cache()

    def add_socket(self, proto, state, local, remote, pid=None):
        with self._lock:
            self.sockets.append(
                {
                    "proto": proto,
                    "state": state,
                    "local": local,
                    "remote": remote,
                    "pid": pid,
                }
            )

    def remove_socket(self, local, remote):
        with self._lock:
            self.sockets = [
                s
                for s in self.sockets
                if not (s["local"] == local and s["remote"] == remote)
            ]


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
    qname = (
        b"".join(
            len(label).to_bytes(1, "big") + label.encode("ascii")
            for label in question_labels
        )
        + b"\x00"
    )
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


def check_firewall(fs, direction: str, ip: str, port: int = None) -> bool:
    """Check if traffic is allowed by iptables rules.

    direction: 'INPUT', 'OUTPUT', or 'FORWARD'
    Returns True if allowed, False if blocked.
    """
    rules_path = "/etc/iptables/rules"
    if not fs.exists(rules_path):
        return True

    try:
        content = fs.read(rules_path) or ""
        # Very simple parser for enforcement
        current_table = "filter"
        for line in content.splitlines():
            line = line.strip()
            if line.startswith("*"):
                current_table = line[1:]
            if current_table != "filter":
                continue

            if line.startswith(f"-A {direction}"):
                parts = line.split()
                # Simple rule matching:
                # -s <ip> -d <ip> -p <proto> --dport <port> -j <target>
                match = True
                target = "ACCEPT"
                idx = 2
                while idx < len(parts):
                    if parts[idx] == "-s" and idx + 1 < len(parts):
                        if parts[idx + 1] != ip and parts[idx + 1] != "0.0.0.0/0":
                            match = False
                        idx += 2
                    elif parts[idx] == "-d" and idx + 1 < len(parts):
                        if parts[idx + 1] != ip and parts[idx + 1] != "0.0.0.0/0":
                            match = False
                        idx += 2
                    elif parts[idx] == "--dport" and idx + 1 < len(parts):
                        if port is not None and str(port) != parts[idx + 1]:
                            match = False
                        idx += 2
                    elif parts[idx] == "-j" and idx + 1 < len(parts):
                        target = parts[idx + 1]
                        idx += 2
                    else:
                        idx += 1

                if match:
                    if target in ("DROP", "REJECT"):
                        import logging

                        logging.getLogger("pureos.audit").warning(
                            f"Firewall {target} for {direction} to/from {ip}"
                            + (f":{port}" if port else "")
                        )
                        return False
                    if target == "ACCEPT":
                        return True
    except Exception:
        pass

    return True


def resolve_host(fs, host: str) -> str:
    """Resolve a hostname.

    Lookup order:
    1. /etc/hosts (VirtualFS)
    2. /etc/resolv.conf nameserver hints
    3. Real system resolver via socket.gethostbyname()
    """
    # Check firewall for DNS output (assuming port 53)
    # We don't know the IP yet for host, but we can check the nameserver IPs
    nameservers = get_nameservers(fs)
    for ns in nameservers:
        ns_ip = ns.split("#")[0]
        if not check_firewall(fs, "OUTPUT", ns_ip, 53):
            import logging

            logging.getLogger("pureos.audit").warning(
                f"DNS resolution to {ns_ip} blocked by firewall"
            )
            raise ConnectionError(f"Firewall blocked DNS query to {ns_ip}")

    try:
        socket.inet_aton(host)
        resolved = host
    except OSError:
        resolved = None

    if resolved is None and fs.exists("/etc/hosts"):
        try:
            content = fs.read("/etc/hosts") or ""
            for line in content.splitlines():
                line = line.split("#")[0].strip()
                parts = line.split()
                if len(parts) >= 2 and host in parts[1:]:
                    resolved = parts[0]
                    break
        except Exception:
            pass

    if resolved is None:
        for nameserver in nameservers:
            try:
                resolved = query_dns_a(nameserver, host)
                if resolved:
                    break
            except Exception:
                continue

    if resolved is None:
        resolved = socket.gethostbyname(host)

    # Check firewall for the resolved IP (generic OUTPUT check)
    if not check_firewall(fs, "OUTPUT", resolved):
        raise ConnectionError(f"Firewall blocked connection to {resolved}")

    return resolved


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
