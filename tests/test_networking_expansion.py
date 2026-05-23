import time


def test_network_driver_initialization(kernel):
    net_driver = kernel.drivers.drivers.get("network")
    assert net_driver is not None
    assert "eth0" in net_driver.interfaces
    assert net_driver.interfaces["eth0"]["up"] is True
    assert net_driver.interfaces["eth0"]["ip"] == "192.168.1.105"


def test_arp_command(kernel, shell):
    # Test listing (empty)
    out = shell.execute("arp", capture_output=True)
    assert "HWaddress" in out

    # Test adding entry
    shell.execute("arp -s 192.168.1.1 00:aa:bb:cc:dd:ee")
    out = shell.execute("arp", capture_output=True)
    assert "192.168.1.1" in out
    assert "00:aa:bb:cc:dd:ee" in out

    # Verify persistence
    net_driver = kernel.drivers.drivers["network"]
    assert "192.168.1.1" in net_driver.arp_table
    assert kernel.fs.exists("/etc/arp.cache")

    # Test deleting entry
    shell.execute("arp -d 192.168.1.1")
    out = shell.execute("arp", capture_output=True)
    assert "192.168.1.1" not in out


def test_nmcli_command(kernel, shell):
    # Check status
    out = shell.execute("nmcli dev status", capture_output=True)
    assert "eth0" in out
    assert "connected" in out

    # Take interface down
    shell.execute("nmcli dev set eth0 down")
    out = shell.execute("nmcli dev status", capture_output=True)
    assert "disconnected" in out

    # Check with ifconfig
    out = shell.execute("ifconfig eth0", capture_output=True)
    assert "<DOWN," in out

    # Bring back up
    shell.execute("nmcli dev set eth0 up")
    out = shell.execute("ifconfig eth0", capture_output=True)
    assert "<UP," in out


def test_dig_command(kernel, shell):
    # Dig usually hits the real network if DNS is not blocked
    # In CI/Tests, it might fail or hit 8.8.8.8
    # We'll mock query_dns_a to ensure it works predictably
    from unittest.mock import patch

    with patch("pureos.drivers.network.query_dns_a", return_value="1.2.3.4"):
        out = shell.execute("dig google.com", capture_output=True)
        assert "ANSWER SECTION" in out
        assert "1.2.3.4" in out


def test_http_server_and_curl(kernel, shell):
    # Start HTTP server service
    kernel.services.start("http_server")

    # The service might take a moment to bind
    # In tests, we might need a small wait if it's on a thread
    time.sleep(1)

    # Check if ss shows the listening socket
    out = shell.execute("ss", capture_output=True)
    assert "LISTEN" in out

    # Use curl to fetch index.html
    # We need to know the port. Let's find it from ss or net_driver
    net_driver = kernel.drivers.drivers["network"]
    port = None
    for s in net_driver.sockets:
        if s["proto"] == "tcp" and s["state"] == "LISTEN" and "127.0.0.1" in s["local"]:
            port = int(s["local"].split(":")[-1])
            break

    assert port is not None
    out = shell.execute(f"curl http://127.0.0.1:{port}/index.html", capture_output=True)
    assert "Welcome to v2-PureOS" in out
    assert "HTTP server is running successfully!" in out

    # Test 404
    out = shell.execute(
        f"curl http://127.0.0.1:{port}/nonexistent.html", capture_output=True
    )
    # curl command might print the error to stdout or return it as string
    # Depending on implementation of CurlCommand
    assert "404" in out or "File Not Found" in out


def test_arp_persistence_across_reboot(tmp_path):
    # First boot
    backing = tmp_path / "store.json"
    from pureos.core.kernel import Kernel

    k1 = Kernel(config={"fs_backing": str(backing)})
    k1.initialize()
    k1.shell.execute("arp -s 10.0.0.5 11:22:33:44:55:66")
    k1.shutdown()

    # Second boot
    k2 = Kernel(config={"fs_backing": str(backing)})
    k2.initialize()
    out = k2.shell.execute("arp", capture_output=True)
    assert "10.0.0.5" in out
    assert "11:22:33:44:55:66" in out
    k2.shutdown()
