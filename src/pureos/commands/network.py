import random
import socket
import time
import urllib.parse
import urllib.request
from typing import List

from ..drivers.network import resolve_host
from .base import Command, PureOSArgumentParser


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
            from ..drivers.network import check_firewall

            resolved_host = resolve_host(self.kernel.fs, host)
            if not check_firewall(self.kernel.fs, "OUTPUT", resolved_host, port):
                print(
                    f"Connection failed: Firewall blocked output to "
                    f"{resolved_host}:{port}"
                )
                return False

            s = socket.create_connection((resolved_host, port), timeout=2)
            s.sendall(msg.encode("utf-8"))
            response = s.recv(4096).decode("utf-8")
            s.close()
            return self.emit(response, capture_output)
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
                from ..drivers.network import check_firewall

                resolved_host = resolve_host(self.kernel.fs, host)
                if not check_firewall(self.kernel.fs, "OUTPUT", resolved_host, port):
                    out = (
                        f"Ping failed: Firewall blocked output to "
                        f"{resolved_host}:{port}"
                    )
                    return self.emit(out, capture_output)

                s = socket.create_connection((resolved_host, port), timeout=2)
                s.close()
                out = f"Ping successful: host {host} port {port} is open"
                return self.emit(out, capture_output)
            except Exception as exc:
                out = f"Ping failed: cannot connect to {host}:{port} ({exc})"
                result = self.emit(out, capture_output)
                return result if capture_output else False
        else:
            try:
                ip = resolve_host(self.kernel.fs, host)
                out = f"Ping successful: host {host} resolved to {ip}"
                return self.emit(out, capture_output)
            except Exception as exc:
                out = f"Ping failed: cannot resolve host {host} ({exc})"
                result = self.emit(out, capture_output)
                return result if capture_output else False


class IfconfigCommand(Command):
    name = "ifconfig"
    usage = "ifconfig [interface]"
    description = "Display network interface configuration."

    def execute(
        self,
        parts: List[str],
        input_data=None,
        capture_output=False,
        raw_line=None,
    ):
        net_driver = self.kernel.drivers.drivers.get("network")
        if not net_driver:
            # Fallback to legacy mock if driver is not loaded
            out = (
                "eth0: flags=4163<UP,BROADCAST,RUNNING,MULTICAST>  mtu 1500\n"
                "        inet 192.168.1.105  netmask 255.255.255.0  "
                "broadcast 192.168.1.255\n"
                "        ether 00:11:22:33:44:55  txqueuelen 1000  (Ethernet)\n"
                "        RX packets 1234  bytes 123456 (123.4 KB)\n"
                "        TX packets 567   bytes 56789 (56.7 KB)\n"
                "\n"
                "lo: flags=73<UP,LOOPBACK,RUNNING>  mtu 65536\n"
                "        inet 127.0.0.1  netmask 255.0.0.0\n"
                "        loop  txqueuelen 1000  (Local Loopback)\n"
                "        RX packets 10    bytes 1000 (1.0 KB)\n"
                "        TX packets 10    bytes 1000 (1.0 KB)"
            )
            return self.emit(out, capture_output)

        out_lines = []
        target_iface = parts[1] if len(parts) > 1 else None

        for name, info in net_driver.interfaces.items():
            if target_iface and name != target_iface:
                continue

            status = "UP" if info["up"] else "DOWN"
            out_lines.append(
                f"{name}: flags=4163<{status},BROADCAST,RUNNING,MULTICAST>  mtu 1500"
            )
            out_lines.append(
                f"        inet {info['ip']}  netmask {info['mask']}  "
                "broadcast 192.168.1.255"
            )
            out_lines.append(
                f"        ether {info['mac']}  txqueuelen 1000  (Ethernet)"
            )
            out_lines.append("")

        out = "\n".join(out_lines).strip()
        return self.emit(out, capture_output)


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
                "  -X, --request <cmd>    Specify request command to use "
                "(GET, POST, etc.)\n"
                "  -H, --header <header>  Pass custom header(s) to server\n"
                "  -d, --data <data>      HTTP POST data\n"
                "  -s, --silent           Silent mode"
            )
            return self.emit(help_text, capture_output)

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
            # Only treat -d "" as POST if explicitly specified (even empty string)
            if args.data is not None and args.data:
                data_bytes = args.data.encode("utf-8")
                if method == "GET":
                    method = "POST"
            elif input_data is not None and input_data:
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
                    raw_bytes = response.read()
                    try:
                        output_str = raw_bytes.decode("utf-8")
                    except UnicodeDecodeError:
                        output_str = raw_bytes.decode("latin-1")

            if args.output:
                out_path = self.resolve_path(args.output)
                self.kernel.fs.write(out_path, output_str)
                return True
            else:
                return self.emit(output_str, capture_output)

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
            return self.emit(help_text, capture_output)

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
                    # Strip query string from filename (e.g. /file.txt?v=1 -> file.txt)
                    filename = path.split("/")[-1].split("?")[0]
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
                raw_bytes = response.read()
                try:
                    content = raw_bytes.decode("utf-8")
                except UnicodeDecodeError:
                    content = raw_bytes.decode("latin-1")

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
    registry.register(HostCommand(registry.kernel))
    registry.register(NslookupCommand(registry.kernel))
    registry.register(IpCommand(registry.kernel))
    registry.register(SsCommand(registry.kernel))
    registry.register(TracerouteCommand(registry.kernel))


# ---------------------------------------------------------------------------
# host — DNS lookup
# ---------------------------------------------------------------------------


class HostCommand(Command):
    name = "host"
    usage = "host <domain>"
    description = "Perform a DNS lookup for a domain name."

    def execute(
        self,
        parts: List[str],
        input_data=None,
        capture_output=False,
        raw_line=None,
    ):
        if len(parts) < 2:
            print("Usage: host <domain>")
            return False
        domain = parts[1]
        try:
            ip = resolve_host(self.kernel.fs, domain)
            out = f"{domain} has address {ip}"
            return self.emit(out, capture_output)
        except Exception as exc:
            out = f"host: {domain}: {exc}"
            if capture_output:
                return out
            print(out)
            return False


# ---------------------------------------------------------------------------
# nslookup — interactive-style DNS query
# ---------------------------------------------------------------------------


class NslookupCommand(Command):
    name = "nslookup"
    usage = "nslookup <domain>"
    description = "Query DNS for a domain name."

    def execute(
        self,
        parts: List[str],
        input_data=None,
        capture_output=False,
        raw_line=None,
    ):
        if len(parts) < 2:
            print("Usage: nslookup <domain>")
            return False
        from ..drivers.network import get_nameservers

        domain = parts[1]
        nameservers = get_nameservers(self.kernel.fs)
        try:
            ip = resolve_host(self.kernel.fs, domain)
            out_lines = [
                f"Server:\t\t{nameservers[0]}",
                f"Address:\t{nameservers[0]}#53",
                "",
                "Non-authoritative answer:",
                f"Name:\t{domain}",
                f"Address: {ip}",
            ]
            out = "\n".join(out_lines)
            return self.emit(out, capture_output)
        except Exception as exc:
            out = f"nslookup: can't resolve '{domain}': {exc}"
            if capture_output:
                return out
            print(out)
            return False


# ---------------------------------------------------------------------------
# ip — network interface and route information
# ---------------------------------------------------------------------------


class IpCommand(Command):
    name = "ip"
    usage = "ip <addr|link|route> [show]"
    description = "Show network interface addresses, link status, or routing table."

    # Simulated routing table stored in VFS at /etc/routes
    _DEFAULT_ROUTES = (
        "default via 192.168.1.1 dev eth0\n"
        "192.168.1.0/24 dev eth0 proto kernel scope link src 192.168.1.105\n"
        "127.0.0.0/8 dev lo proto kernel scope link src 127.0.0.1\n"
    )

    def execute(
        self,
        parts: List[str],
        input_data=None,
        capture_output=False,
        raw_line=None,
    ):
        if len(parts) < 2:
            print("Usage: ip <addr|link|route> [show]")
            return False
        sub = parts[1].lower()
        if sub in ("addr", "address", "a"):
            out = (
                "1: lo: <LOOPBACK,UP,LOWER_UP> mtu 16384\n"
                "    inet 127.0.0.1/8 scope host lo\n"
                "2: eth0: <BROADCAST,MULTICAST,UP,LOWER_UP> mtu 1500\n"
                "    inet 192.168.1.105/24 brd 192.168.1.255 scope global eth0\n"
                "    ether 00:1a:2b:3c:4d:5e"
            )
        elif sub in ("link", "l"):
            out = (
                "1: lo: <LOOPBACK,UP,LOWER_UP> mtu 16384 "
                "qdisc noqueue state UNKNOWN\n"
                "    link/loopback 00:00:00:00:00:00 brd 00:00:00:00:00:00\n"
                "2: eth0: <BROADCAST,MULTICAST,UP,LOWER_UP> mtu 1500 "
                "qdisc pfifo_fast state UP\n"
                "    link/ether 00:1a:2b:3c:4d:5e brd ff:ff:ff:ff:ff:ff"
            )
        elif sub in ("route", "r"):
            if self.kernel.fs.exists("/etc/routes"):
                out = (
                    self.kernel.fs.read("/etc/routes") or self._DEFAULT_ROUTES
                ).rstrip()
            else:
                out = self._DEFAULT_ROUTES.rstrip()
        else:
            print(f"ip: unknown object '{sub}'")
            return False

        return self.emit(out, capture_output)


# ---------------------------------------------------------------------------
# ss — socket statistics
# ---------------------------------------------------------------------------


class SsCommand(Command):
    name = "ss"
    usage = "ss [-t] [-u] [-l]"
    description = "Show live socket statistics from the network driver."

    def execute(
        self,
        parts: List[str],
        input_data=None,
        capture_output=False,
        raw_line=None,
    ):
        net_driver = self.kernel.drivers.drivers.get("network")
        if not net_driver:
            # Simulated — show a static table if driver is not available
            out_lines = [
                "Netid  State      Recv-Q  Send-Q  Local Address:Port  "
                "Peer Address:Port",
                "tcp    LISTEN     0       128     0.0.0.0:22           " "0.0.0.0:*",
                "tcp    LISTEN     0       128     127.0.0.1:6379       " "0.0.0.0:*",
                "tcp    ESTAB      0       0       192.168.1.105:22     "
                "192.168.1.10:54321",
                "udp    UNCONN     0       0       0.0.0.0:68           " "0.0.0.0:*",
            ]
            return self.emit("\n".join(out_lines), capture_output)

        out_lines = [
            "Netid  State      Recv-Q  Send-Q  Local Address:Port  Peer Address:Port"
        ]
        with net_driver._lock:
            for s in net_driver.sockets:
                out_lines.append(
                    f"{s['proto']:<6} {s['state']:<10} 0       0       "
                    f"{s['local']:<19} {s['remote']:<19}"
                )

        if len(out_lines) == 1:
            out_lines.append("(no active sockets found)")

        return self.emit("\n".join(out_lines), capture_output)


# ---------------------------------------------------------------------------
# traceroute — simulated hop-by-hop route tracing
# ---------------------------------------------------------------------------


class TracerouteCommand(Command):
    name = "traceroute"
    aliases = ["tracert"]
    usage = "traceroute <host>"
    description = "Simulate hop-by-hop route tracing to a host."

    def execute(
        self,
        parts: List[str],
        input_data=None,
        capture_output=False,
        raw_line=None,
    ):
        if len(parts) < 2:
            print("Usage: traceroute <host>")
            return False
        host = parts[1]
        try:
            dest_ip = resolve_host(self.kernel.fs, host)
        except Exception as exc:
            print(f"traceroute: {host}: {exc}")
            return False

        # Build a simulated path: gateway → internet hops → destination
        import random

        hops = [
            "192.168.1.1",
            "10.0.0.1",
            "72.14.204.1",
            "209.85.248.1",
            dest_ip,
        ]
        out_lines = [f"traceroute to {host} ({dest_ip}), 30 hops max, 60 byte packets"]
        for i, hop in enumerate(hops, 1):
            rtt1 = random.uniform(1.0, 30.0)
            rtt2 = random.uniform(1.0, 30.0)
            rtt3 = random.uniform(1.0, 30.0)
            out_lines.append(
                f" {i:2}  {hop}  {rtt1:.3f} ms  {rtt2:.3f} ms  {rtt3:.3f} ms"
            )
        out = "\n".join(out_lines)
        return self.emit(out, capture_output)


class ArpCommand(Command):
    name = "arp"
    usage = "arp [-a] [-d <ip>] [-s <ip> <mac>]"
    description = "List and manage the simulated ARP cache."

    def execute(
        self,
        parts: List[str],
        input_data=None,
        capture_output=False,
        raw_line=None,
    ):
        net_driver = self.kernel.drivers.drivers.get("network")
        if not net_driver:
            print("arp: network driver not loaded")
            return False

        if len(parts) == 1 or parts[1] == "-a":
            out_lines = [
                "Address                  HWtype  HWaddress           "
                "Flags Mask            Iface"
            ]
            with net_driver._lock:
                for ip, mac in net_driver.arp_table.items():
                    out_lines.append(
                        f"{ip:<24} ether   {mac:<19} C                     eth0"
                    )
            return self.emit("\n".join(out_lines), capture_output)

        if len(parts) > 2 and parts[1] == "-d":
            ip = parts[2]
            with net_driver._lock:
                if ip in net_driver.arp_table:
                    del net_driver.arp_table[ip]
                    net_driver.save_arp_cache()
            return True

        if len(parts) > 3 and parts[1] == "-s":
            ip = parts[2]
            mac = parts[3]
            net_driver.add_arp_entry(ip, mac)
            return True

        print(f"Usage: {self.usage}")
        return False


class DigCommand(Command):
    name = "dig"
    usage = "dig <host>"
    description = "Detailed DNS query tool."

    def execute(
        self,
        parts: List[str],
        input_data=None,
        capture_output=False,
        raw_line=None,
    ):
        if len(parts) < 2:
            print(f"Usage: {self.usage}")
            return False
        host = parts[1]

        from ..drivers.network import get_nameservers, query_dns_a

        nameservers = get_nameservers(self.kernel.fs)
        ns = nameservers[0] if nameservers else "8.8.8.8"

        out_lines = [
            f"; <<>> DiG 9.16.1-Ubuntu <<>> {host}",
            ";; global options: +cmd",
            ";; Got answer:",
            f";; ->>HEADER<<- opcode: QUERY, status: NOERROR, id: "
            f"{random.randint(1000, 9999)}",
            ";; flags: qr rd ra; QUERY: 1, ANSWER: 1, AUTHORITY: 0, " "ADDITIONAL: 1",
            "",
            ";; QUESTION SECTION:",
            f";{host}.            IN  A",
            "",
        ]

        try:
            ip = query_dns_a(ns, host)
            out_lines.extend(
                [
                    ";; ANSWER SECTION:",
                    f"{host}.         60  IN  A   {ip}",
                    "",
                    f";; Query time: {random.randint(10, 50)} msec",
                    f";; SERVER: {ns}#53({ns})",
                    f";; WHEN: {time.ctime()}",
                    ";; MSG SIZE  rcvd: 56",
                ]
            )
        except Exception as exc:
            out_lines.append(f";; ERROR: {exc}")

        return self.emit("\n".join(out_lines), capture_output)


class NmcliCommand(Command):
    name = "nmcli"
    usage = "nmcli device [status|show|set <iface> <up|down>]"
    description = "Basic network interface management."

    def execute(
        self,
        parts: List[str],
        input_data=None,
        capture_output=False,
        raw_line=None,
    ):
        net_driver = self.kernel.drivers.drivers.get("network")
        if not net_driver:
            print("nmcli: network driver not loaded")
            return False

        if len(parts) < 2:
            print(f"Usage: {self.usage}")
            return False

        sub = parts[1]
        if sub == "device" or sub == "dev":
            if len(parts) == 2 or parts[2] == "status":
                out_lines = ["DEVICE  TYPE      STATE      CONNECTION"]
                for name, info in net_driver.interfaces.items():
                    state = "connected" if info["up"] else "disconnected"
                    out_lines.append(f"{name:<7} ethernet  {state:<10} {name}")
                return self.emit("\n".join(out_lines), capture_output)

            if parts[2] == "show":
                out_lines = []
                for name, info in net_driver.interfaces.items():
                    state_desc = (
                        "100 (connected)" if info["up"] else "30 (disconnected)"
                    )
                    out_lines.extend(
                        [
                            f"GENERAL.DEVICE:                         {name}",
                            "GENERAL.TYPE:                           ethernet",
                            f"GENERAL.STATE:                          {state_desc}",
                            f"IP4.ADDRESS[1]:                         "
                            f"{info['ip']}/{info['mask']}",
                            "",
                        ]
                    )
                return self.emit("\n".join(out_lines), capture_output)

            if len(parts) > 4 and parts[2] == "set":
                iface = parts[3]
                action = parts[4]
                if iface in net_driver.interfaces:
                    net_driver.interfaces[iface]["up"] = action == "up"
                    return True
                else:
                    print(f"Error: Device '{iface}' not found.")
                    return False

        print(f"Usage: {self.usage}")
        return False
