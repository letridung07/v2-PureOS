import pytest
import os
import time
from pureos.kernel import Kernel

@pytest.fixture
def kernel():
    k = Kernel({"memory_total_kb": 10240, "memory_swap_kb": 0})
    k.initialize()
    yield k
    k.shutdown()

def test_audit_logging(kernel):
    # Test failed login
    kernel.users.authenticate("nonexistent", "password")
    time.sleep(0.1)  # Wait for logging
    content = kernel.fs.read("/var/log/audit.log")
    assert "Failed login attempt for unknown user: nonexistent" in content

    # Test sudo attempt
    kernel.users.add_user("testuser", "password")
    kernel.users.current_user = kernel.users.users["testuser"]
    
    # Attempt unauthorized sudo
    from pureos.commands.users import SudoCommand
    cmd = SudoCommand(kernel)
    cmd.execute(["sudo", "ls"])
    
    time.sleep(0.1)
    content = kernel.fs.read("/var/log/audit.log")
    assert "Unauthorized sudo attempt by user: testuser" in content

def test_disk_quota(kernel):
    kernel.users.add_user("quotauser", "password")
    user = kernel.users.users["quotauser"]
    user.disk_quota = 100  # 100 bytes
    kernel.users.save_to_fs()
    
    kernel.users.current_user = user
    
    # Should succeed
    kernel.fs.write("/tmp/test1", "A" * 50)
    
    # Should fail
    with pytest.raises(OSError) as exc:
        kernel.fs.write("/tmp/test2", "B" * 60)
    assert "Disk quota exceeded" in str(exc.value)

    # Check audit log
    time.sleep(0.1)
    content = kernel.fs.read("/var/log/audit.log")
    assert "Disk quota exceeded for user quotauser" in content

def test_memory_quota(kernel):
    kernel.users.add_user("memuser", "password")
    user = kernel.users.users["memuser"]
    user.mem_quota = 512  # 512 KB
    kernel.users.save_to_fs()
    
    # Spawn a process as this user
    # Memory driver automatically allocates 1024KB on spawn in Scheduler.spawn
    # Since 1024 > 512, it should raise MemoryError immediately
    with pytest.raises(MemoryError) as exc:
        kernel.scheduler.spawn("testproc", runtime=1.0, uid=user.uid)
    assert "Out of memory during process spawn" in str(exc.value)
    
    time.sleep(0.1)
    content = kernel.fs.read("/var/log/audit.log")
    assert "Memory quota exceeded for user memuser" in content

def test_firewall_enforcement(kernel):
    # Add a block rule
    kernel.fs.mkdir("/etc/iptables", parents=True)
    kernel.fs.write("/etc/iptables/rules", "*filter\n-A OUTPUT -d 8.8.8.8 -j DROP\nCOMMIT\n")
    
    # Try to resolve a host which would trigger check_firewall in resolve_host
    kernel.fs.write("/etc/resolv.conf", "nameserver 8.8.8.8\n")
    
    from pureos.network import resolve_host
    with pytest.raises(ConnectionError) as exc:
        resolve_host(kernel.fs, "google.com")
    assert "Firewall blocked DNS query to 8.8.8.8" in str(exc.value)

    # Check audit log
    time.sleep(0.1)
    content = kernel.fs.read("/var/log/audit.log")
    assert "Firewall DROP for OUTPUT to/from 8.8.8.8" in content
