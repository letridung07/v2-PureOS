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

    # Test ping (port)
    ping_out2 = sh.registry.execute(["ping", "127.0.0.1", "50007"], capture_output=True)
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

    # Test ping before server starts
    ping_out1 = sh.registry.execute(
        ["ping", "custom.local", "50007"], capture_output=True
    )
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
        res_curl = sh.registry.execute(["curl", f"127.0.0.1:{port}"], capture_output=True)
        assert res_curl == "Hello HTTP"

        # Test curl output to file
        res_curl_o = sh.registry.execute(["curl", "-o", "/out.txt", f"127.0.0.1:{port}"])
        assert res_curl_o is True
        assert k.fs.read("/out.txt") == "Hello HTTP"

        # Test curl head
        res_curl_head = sh.registry.execute(["curl", "-I", f"127.0.0.1:{port}"], capture_output=True)
        assert "HTTP/1.1 200 OK" in res_curl_head
        assert "Content-Type: text/plain" in res_curl_head

        # Test curl POST data
        res_curl_post = sh.registry.execute(["curl", "-d", "mypostdata", f"127.0.0.1:{port}"], capture_output=True)
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
        res_wget_o = sh.registry.execute(["wget", "-O", "/custom.html", f"127.0.0.1:{port}"])
        assert res_wget_o is True
        assert k.fs.read("/custom.html") == "Hello HTTP"

        # Test virtual /etc/hosts resolution mapping
        k.fs.mkdir("/etc")
        k.fs.write("/etc/hosts", f"127.0.0.1 custom.domain")
        res_hosts_curl = sh.registry.execute(["curl", f"custom.domain:{port}/headers"], capture_output=True)
        assert f"custom.domain:{port}" in res_hosts_curl

    finally:
        server.shutdown()
        thread.join()
        k.shutdown()

