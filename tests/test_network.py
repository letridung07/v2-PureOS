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
