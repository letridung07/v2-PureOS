import socket
from typing import List

from .base import Command


class NetcatCommand(Command):
    name = "netcat"
    aliases = ["nc"]
    usage = "nc <host> <port> [message]"
    description = "Connect to a TCP port, send data, and print response."

    def execute(
        self,
        parts: List[str],
        input_data=None,
        capture_output=False,
        raw_line=None,
    ):
        if len(parts) < 3:
            print("Usage: nc <host> <port> [message]")
            return False
        host = parts[1]
        try:
            port = int(parts[2])
        except ValueError:
            print("Usage: nc <host> <port> [message]")
            return False

        if len(parts) > 3:
            msg = " ".join(parts[3:])
        elif input_data is not None:
            msg = input_data
        else:
            msg = ""

        try:
            s = socket.create_connection((host, port), timeout=2)
            s.sendall(msg.encode("utf-8"))
            response = s.recv(4096).decode("utf-8")
            s.close()
            if capture_output:
                return response
            print(response)
            return True
        except Exception as exc:
            print(f"Connection failed: {exc}")
            return False


class PingCommand(Command):
    name = "ping"
    usage = "ping <host> [port]"
    description = "Check host or port reachability."

    def execute(
        self,
        parts: List[str],
        input_data=None,
        capture_output=False,
        raw_line=None,
    ):
        if len(parts) < 2:
            print("Usage: ping <host> [port]")
            return False
        host = parts[1]
        port = None
        if len(parts) > 2:
            try:
                port = int(parts[2])
            except ValueError:
                print("Usage: ping <host> [port]")
                return False

        if port is not None:
            try:
                s = socket.create_connection((host, port), timeout=2)
                s.close()
                out = f"Ping successful: host {host} port {port} is open"
                if capture_output:
                    return out
                print(out)
                return True
            except Exception as exc:
                out = f"Ping failed: cannot connect to {host}:{port} ({exc})"
                if capture_output:
                    return out
                print(out)
                return False
        else:
            try:
                ip = socket.gethostbyname(host)
                out = f"Ping successful: host {host} resolved to {ip}"
                if capture_output:
                    return out
                print(out)
                return True
            except Exception as exc:
                out = f"Ping failed: cannot resolve host {host} ({exc})"
                if capture_output:
                    return out
                print(out)
                return False


class IfconfigCommand(Command):
    name = "ifconfig"
    usage = "ifconfig"
    description = "Display network interface configuration."

    def execute(
        self,
        parts: List[str],
        input_data=None,
        capture_output=False,
        raw_line=None,
    ):
        out = (
            "lo0: flags=8049<UP,LOOPBACK,RUNNING,MULTICAST> mtu 16384\n"
            "     inet 127.0.0.1 netmask 0xff000000\n"
            "eth0: flags=8863<UP,BROADCAST,SMART,RUNNING,SIMPLEX,MULTICAST> mtu 1500\n"
            "     inet 192.168.1.105 netmask 0xffffff00 broadcast 192.168.1.255\n"
            "     ether 00:1a:2b:3c:4d:5e"
        )
        if capture_output:
            return out
        print(out)
        return True


def register_network_commands(registry):
    registry.register(NetcatCommand(registry.kernel))
    registry.register(PingCommand(registry.kernel))
    registry.register(IfconfigCommand(registry.kernel))
