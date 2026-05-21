import importlib
import os
import socket
import socketserver
import struct
import threading
import sys
import time

try:
    net_mod = importlib.import_module("pureos.network")
except Exception:
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
    net_mod = importlib.import_module("pureos.network")

try:
    kernel_mod = importlib.import_module("pureos.kernel")
except Exception:
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
    kernel_mod = importlib.import_module("pureos.kernel")

start_echo_server = net_mod.start_echo_server
Kernel = kernel_mod.Kernel


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


def test_networking(tmp_path):
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

    # Test ping (port) — only assert 'Ping failed' if port is actually free
    import socket as _sock

    _chk = _sock.socket(_sock.AF_INET, _sock.SOCK_STREAM)
    _port_busy = _chk.connect_ex(("127.0.0.1", 50007)) == 0
    _chk.close()
    ping_out2 = sh.registry.execute(["ping", "127.0.0.1", "50007"], capture_output=True)
    if not _port_busy:
        assert "Ping failed" in ping_out2  # Echo server is not running yet

    # Start echo_server service
    sh.execute("service start echo_server")
    time.sleep(0.5)

    # Now ping should succeed
    ping_out3 = sh.registry.execute(["ping", "127.0.0.1", "50007"], capture_output=True)
    assert "Ping successful" in ping_out3

    # Test netcat (nc)
    nc_out = sh.registry.execute(
        ["nc", "127.0.0.1", "50007", "hello OS"], capture_output=True
    )
    assert nc_out == "hello OS"

    # Test netcat via pipeline
    sh.execute("echo piped hello | nc 127.0.0.1 50007 > /tmp/nc_out")
    assert k.fs.read("/tmp/nc_out") == "piped hello\n"

    # Stop echo_server service
    sh.execute("service stop echo_server")
    k.shutdown()


def test_local_dns(tmp_path):
    k = Kernel(config={"fs_backing": str(tmp_path / "store.json")})
    k.initialize()
    sh = k.shell

    # Write to /etc/hosts
    k.fs.mkdir("/etc/")
    k.fs.write("/etc/hosts", "127.0.0.1 custom.local\n127.0.0.2 custom2.local")

    # Test ping before server starts — only if port 50007 is free
    import socket as _sock

    _chk = _sock.socket(_sock.AF_INET, _sock.SOCK_STREAM)
    _port_busy = _chk.connect_ex(("127.0.0.1", 50007)) == 0
    _chk.close()
    ping_out1 = sh.registry.execute(
        ["ping", "custom.local", "50007"], capture_output=True
    )
    if not _port_busy:
        assert "Ping failed" in ping_out1

    # Start service
    sh.execute("service start echo_server")
    time.sleep(0.5)

    # Ping custom.local
    ping_out2 = sh.registry.execute(
        ["ping", "custom.local", "50007"], capture_output=True
    )
    assert "Ping successful" in ping_out2

    # Netcat custom.local
    nc_out = sh.registry.execute(
        ["nc", "custom.local", "50007", "dns_payload"], capture_output=True
    )
    assert nc_out == "dns_payload"

    # Stop service
    sh.execute("service stop echo_server")
    k.shutdown()


def test_resolv_conf_nameserver(tmp_path):
    class DNSUDPHandler(socketserver.BaseRequestHandler):
        def handle(self):
            data, sock = self.request
            if len(data) < 12:
                return
            transaction_id = data[:2]
            qdcount = struct.unpack("!H", data[4:6])[0]
            if qdcount == 0:
                return

            offset = 12
            labels = []
            while offset < len(data):
                length = data[offset]
                offset += 1
                if length == 0:
                    break
                labels.append(data[offset : offset + length].decode())
                offset += length

            if offset + 4 > len(data):
                return
            qtype, qclass = struct.unpack("!HH", data[offset : offset + 4])
            offset += 4
            domain = ".".join(labels)
            ip = "127.0.0.2" if domain == "customdns.local" else "127.0.0.1"

            question = data[12:offset]
            header = transaction_id + b"\x81\x80" + struct.pack("!HHHH", 1, 1, 0, 0)
            answer = b"\xc0\x0c" + struct.pack("!HHIH", qtype, qclass, 60, 4) + socket.inet_aton(ip)
            sock.sendto(header + question + answer, self.client_address)

    server = socketserver.ThreadingUDPServer(("127.0.0.1", 0), DNSUDPHandler)
    port = server.server_address[1]
    thread = threading.Thread(target=server.serve_forever)
    thread.daemon = True
    thread.start()

    try:
        k = Kernel(config={"fs_backing": str(tmp_path / "store.json")})
        k.initialize()
        sh = k.shell
        k.fs.mkdir("/etc")
        k.fs.write("/etc/resolv.conf", f"nameserver 127.0.0.1#{port}\n")

        ping_out = sh.registry.execute(["ping", "customdns.local"], capture_output=True)
        assert "Ping successful" in ping_out
        assert "customdns.local resolved to 127.0.0.2" in ping_out

        host_out = sh.registry.execute(["host", "customdns.local"], capture_output=True)
        assert "customdns.local has address 127.0.0.2" in host_out

        ns_out = sh.registry.execute(["nslookup", "customdns.local"], capture_output=True)
        assert f"Server:\t\t127.0.0.1#{port}" in ns_out
        assert "Address: 127.0.0.2" in ns_out
    finally:
        server.shutdown()
        server.server_close()
        thread.join()
        k.shutdown()


def test_curl_and_wget(tmp_path):
    import http.server
    import threading

    # Simple mock server to verify HTTP queries
    class SimpleHTTPHandler(http.server.SimpleHTTPRequestHandler):
        def do_GET(self):
            if self.path == "/":
                self.send_response(200)
                self.send_header("Content-Type", "text/plain")
                self.end_headers()
                self.wfile.write(b"Hello HTTP")
            elif self.path == "/headers":
                self.send_response(200)
                self.send_header("Content-Type", "text/plain")
                self.end_headers()
                # Respond with the value of Host header to check hosts resolution
                self.wfile.write(self.headers.get("Host", "").encode())
            else:
                self.send_response(404)
                self.end_headers()

        def do_HEAD(self):
            if self.path == "/":
                self.send_response(200)
                self.send_header("Content-Type", "text/plain")
                self.end_headers()
            elif self.path == "/headers":
                self.send_response(200)
                self.send_header("Content-Type", "text/plain")
                self.end_headers()
            else:
                self.send_response(404)
                self.end_headers()

        def do_POST(self):
            content_length = int(self.headers.get("Content-Length", 0))
            post_data = self.rfile.read(content_length)
            self.send_response(200)
            self.send_header("Content-Type", "text/plain")
            self.end_headers()
            self.wfile.write(post_data)

        # Suppress log messages
        def log_message(self, format, *args):
            pass

    server = http.server.HTTPServer(("127.0.0.1", 0), SimpleHTTPHandler)
    port = server.server_port
    thread = threading.Thread(target=server.serve_forever)
    thread.daemon = True
    thread.start()

    try:
        # Initialize kernel
        k = Kernel(config={"fs_backing": str(tmp_path / "store.json")})
        k.initialize()
        sh = k.shell

        # Test simple curl
        res_curl = sh.registry.execute(
            ["curl", f"127.0.0.1:{port}"], capture_output=True
        )
        assert res_curl == "Hello HTTP"

        # Test curl output to file
        res_curl_o = sh.registry.execute(
            ["curl", "-o", "/out.txt", f"127.0.0.1:{port}"]
        )
        assert res_curl_o is True
        assert k.fs.read("/out.txt") == "Hello HTTP"

        # Test curl head
        res_curl_head = sh.registry.execute(
            ["curl", "-I", f"127.0.0.1:{port}"], capture_output=True
        )
        assert "HTTP/1.1 200 OK" in res_curl_head
        assert "Content-Type: text/plain" in res_curl_head

        # Test curl POST data
        res_curl_post = sh.registry.execute(
            ["curl", "-d", "mypostdata", f"127.0.0.1:{port}"], capture_output=True
        )
        assert res_curl_post == "mypostdata"

        # Test curl POST via pipe / stdin
        sh.execute(f"echo pipe_payload | curl -X POST 127.0.0.1:{port} > /pipe.txt")
        assert k.fs.read("/pipe.txt") == "pipe_payload\n"

        # Test wget
        res_wget = sh.registry.execute(["wget", f"127.0.0.1:{port}"])
        assert res_wget is True
        assert k.fs.exists("/index.html")
        assert k.fs.read("/index.html") == "Hello HTTP"

        # Test wget with custom filename
        res_wget_o = sh.registry.execute(
            ["wget", "-O", "/custom.html", f"127.0.0.1:{port}"]
        )
        assert res_wget_o is True
        assert k.fs.read("/custom.html") == "Hello HTTP"

        # Test virtual /etc/hosts resolution mapping
        k.fs.mkdir("/etc")
        k.fs.write("/etc/hosts", "127.0.0.1 custom.domain")
        res_hosts_curl = sh.registry.execute(
            ["curl", f"custom.domain:{port}/headers"], capture_output=True
        )
        assert f"custom.domain:{port}" in res_hosts_curl

    finally:
        server.shutdown()
        thread.join()
        k.shutdown()
