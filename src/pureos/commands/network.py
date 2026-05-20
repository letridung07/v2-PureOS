import argparse
import socket
import urllib.parse
import urllib.request
from typing import List

from ..network import resolve_host
from .base import Command


class PureOSArgumentParser(argparse.ArgumentParser):
    def error(self, message):
        raise ValueError(message)

    def exit(self, status=0, message=None):
        if message:
            raise ValueError(message)


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
            resolved_host = resolve_host(self.kernel.fs, host)
            s = socket.create_connection((resolved_host, port), timeout=2)
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
                resolved_host = resolve_host(self.kernel.fs, host)
                s = socket.create_connection((resolved_host, port), timeout=2)
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
                ip = resolve_host(self.kernel.fs, host)
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


class CurlCommand(Command):
    name = "curl"
    usage = "curl [options] <url>"
    description = "Transfer data from or to a server using HTTP/HTTPS."

    def execute(
        self,
        parts: List[str],
        input_data=None,
        capture_output=False,
        raw_line=None,
    ):
        if "--help" in parts or "-h" in parts:
            help_text = (
                "Usage: curl [options] <url>\n"
                "Options:\n"
                "  -o, --output <file>    Write to file instead of stdout\n"
                "  -I, --head             Show document info (headers) only\n"
                "  -X, --request <cmd>    Specify request command to use (GET, POST, etc.)\n"
                "  -H, --header <header>  Pass custom header(s) to server\n"
                "  -d, --data <data>      HTTP POST data\n"
                "  -s, --silent           Silent mode"
            )
            if capture_output:
                return help_text
            print(help_text)
            return True

        parser = PureOSArgumentParser(prog="curl", add_help=False)
        parser.add_argument("url", nargs="?", default=None)
        parser.add_argument("-o", "--output")
        parser.add_argument("-I", "--head", action="store_true")
        parser.add_argument("-X", "--request", default="GET")
        parser.add_argument("-H", "--header", action="append", default=[])
        parser.add_argument("-d", "--data")
        parser.add_argument("-s", "--silent", action="store_true")

        try:
            args = parser.parse_args(parts[1:])
        except ValueError as e:
            print(f"curl: {e}")
            print(f"Usage: {self.usage}")
            return False

        if not args.url:
            print("curl: try 'curl --help' or 'curl <url>' for more information")
            print(f"Usage: {self.usage}")
            return False

        url = args.url
        if not (url.startswith("http://") or url.startswith("https://")):
            url = "http://" + url

        try:
            parsed_url = urllib.parse.urlparse(url)
            hostname = parsed_url.hostname
            if not hostname:
                print("curl: invalid URL")
                return False

            resolved_ip = resolve_host(self.kernel.fs, hostname)
            port_str = f":{parsed_url.port}" if parsed_url.port is not None else ""
            reconstructed_netloc = resolved_ip + port_str
            reconstructed_url = urllib.parse.urlunparse(
                (
                    parsed_url.scheme,
                    reconstructed_netloc,
                    parsed_url.path,
                    parsed_url.params,
                    parsed_url.query,
                    parsed_url.fragment,
                )
            )

            req_headers = {}
            req_headers["Host"] = f"{hostname}{port_str}"

            for h in args.header:
                if ":" in h:
                    k, v = h.split(":", 1)
                    req_headers[k.strip()] = v.strip()
                else:
                    req_headers[h.strip()] = ""

            method = args.request.upper()
            data_bytes = None
            if args.data is not None:
                data_bytes = args.data.encode("utf-8")
                if method == "GET":
                    method = "POST"
            elif input_data is not None:
                data_bytes = input_data.encode("utf-8")
                if method == "GET":
                    method = "POST"

            req = urllib.request.Request(
                reconstructed_url,
                headers=req_headers,
                method=method,
                data=data_bytes,
            )

            if args.head:
                req.method = "HEAD"

            with urllib.request.urlopen(req, timeout=5) as response:
                if args.head:
                    out_parts = []
                    out_parts.append(f"HTTP/1.1 {response.status} {response.reason}")
                    for header_name, header_val in response.getheaders():
                        out_parts.append(f"{header_name}: {header_val}")
                    output_str = "\n".join(out_parts)
                else:
                    output_str = response.read().decode("utf-8")

            if args.output:
                out_path = self.resolve_path(args.output)
                self.kernel.fs.write(out_path, output_str)
                return True
            else:
                if capture_output:
                    return output_str
                print(output_str)
                return True

        except Exception as e:
            if not args.silent:
                print(f"curl: (7) Failed to connect: {e}")
            return False


class WgetCommand(Command):
    name = "wget"
    usage = "wget [options] <url>"
    description = "Retrieve files over HTTP/HTTPS."

    def execute(
        self,
        parts: List[str],
        input_data=None,
        capture_output=False,
        raw_line=None,
    ):
        if "--help" in parts or "-h" in parts:
            help_text = (
                "Usage: wget [options] <url>\n"
                "Options:\n"
                "  -O, --output-document <file>  Write documents to <file>\n"
                "  -q, --quiet                   Quiet mode (no output)"
            )
            if capture_output:
                return help_text
            print(help_text)
            return True

        parser = PureOSArgumentParser(prog="wget", add_help=False)
        parser.add_argument("url", nargs="?", default=None)
        parser.add_argument("-O", "--output-document")
        parser.add_argument("-q", "--quiet", action="store_true")

        try:
            args = parser.parse_args(parts[1:])
        except ValueError as e:
            print(f"wget: {e}")
            print(f"Usage: {self.usage}")
            return False

        if not args.url:
            print("wget: missing URL")
            print(f"Usage: {self.usage}")
            return False

        url = args.url
        if not (url.startswith("http://") or url.startswith("https://")):
            url = "http://" + url

        try:
            parsed_url = urllib.parse.urlparse(url)
            hostname = parsed_url.hostname
            if not hostname:
                print("wget: invalid URL")
                return False

            if args.output_document:
                out_path = self.resolve_path(args.output_document)
            else:
                path = parsed_url.path
                if not path or path.endswith("/"):
                    filename = "index.html"
                else:
                    filename = path.split("/")[-1]
                    if not filename:
                        filename = "index.html"
                out_path = self.resolve_path(filename)

            resolved_ip = resolve_host(self.kernel.fs, hostname)
            port_str = f":{parsed_url.port}" if parsed_url.port is not None else ""
            reconstructed_netloc = resolved_ip + port_str
            reconstructed_url = urllib.parse.urlunparse(
                (
                    parsed_url.scheme,
                    reconstructed_netloc,
                    parsed_url.path,
                    parsed_url.params,
                    parsed_url.query,
                    parsed_url.fragment,
                )
            )

            req_headers = {"Host": f"{hostname}{port_str}"}
            req = urllib.request.Request(reconstructed_url, headers=req_headers)

            if not args.quiet:
                print(f"Connecting to {hostname} ({resolved_ip})...")

            with urllib.request.urlopen(req, timeout=5) as response:
                content = response.read().decode("utf-8")

            self.kernel.fs.write(out_path, content)
            if not args.quiet:
                print(f"Saved: '{out_path}'")
            return True

        except Exception as e:
            if not args.quiet:
                print(f"wget: error: {e}")
            return False


def register_network_commands(registry):
    registry.register(NetcatCommand(registry.kernel))
    registry.register(PingCommand(registry.kernel))
    registry.register(IfconfigCommand(registry.kernel))
    registry.register(CurlCommand(registry.kernel))
    registry.register(WgetCommand(registry.kernel))
