"""Tests for POSIX File Permissions: Sticky bit, Execute bits, and SUID/SGID."""

import pytest
from pureos.kernel import Kernel

@pytest.fixture
def kernel():
    k = Kernel({"format_on_boot": True, "auto_start_services": False})
    k.initialize()
    return k

@pytest.fixture
def shell(kernel):
    return kernel.shell

def test_sticky_bit_enforcement(kernel):
    """Verify that sticky bit on /tmp prevents deleting others' files."""
    # /tmp/ is initialized with 0o1777 in FSOperations.format()
    
    # root creates a file in /tmp/
    kernel.fs.write("/tmp/root_file", "root")
    kernel.fs.chmod("/tmp/root_file", 0o644)
    kernel.fs.chown("/tmp/root_file", 0)
    
    # switch to guest
    kernel.users.su("guest")
    
    # guest creates a file in /tmp/
    kernel.fs.write("/tmp/guest_file", "guest")
    kernel.fs.chmod("/tmp/guest_file", 0o644)
    # verify ownership (guest is 1000)
    assert kernel.fs.state.owners["/tmp/guest_file"] == 1000
    
    # guest tries to delete root_file - should fail
    try:
        kernel.fs.delete("/tmp/root_file")
        pytest.fail("Should have raised PermissionError for sticky bit")
    except PermissionError as e:
        assert "Permission denied" in str(e)
    
    assert kernel.fs.exists("/tmp/root_file")
    
    # guest can delete their own file
    kernel.fs.delete("/tmp/guest_file")
    assert not kernel.fs.exists("/tmp/guest_file")
    
    # root can delete guest file even with sticky bit
    kernel.users.su("root")
    kernel.fs.write("/tmp/guest_file", "guest2")
    kernel.fs.chown("/tmp/guest_file", 1000)
    kernel.fs.delete("/tmp/guest_file")
    assert not kernel.fs.exists("/tmp/guest_file")

def test_execute_permission_requirement(kernel, shell):
    """Verify that source and direct execution require the x bit."""
    kernel.fs.mkdir("/home/guest", parents=True)
    kernel.fs.write("/home/guest/script.sh", "echo 'SUCCESS'")
    kernel.fs.chown("/home/guest/script.sh", 1000)
    
    kernel.users.su("guest")
    
    # Case 1: No execute bit (644)
    kernel.fs.chmod("/home/guest/script.sh", 0o644)
    
    # source should fail
    res = shell.execute("source /home/guest/script.sh", add_to_history=False)
    assert res is False
    
    # direct execution should fail
    res = shell.execute("/home/guest/script.sh", add_to_history=False)
    assert res is False
    
    # Case 2: With execute bit (755)
    kernel.fs.chmod("/home/guest/script.sh", 0o755)
    
    # source should succeed
    res = shell.execute("source /home/guest/script.sh", add_to_history=False)
    assert res is True
    
    # direct execution should succeed
    res = shell.execute("/home/guest/script.sh", add_to_history=False)
    assert res is True

def test_suid_privilege_elevation(kernel, shell):
    """Verify that SUID root scripts can modify root-only files."""
    # Create a root-only file
    kernel.fs.mkdir("/root", parents=True)
    kernel.fs.write("/root/protected", "original")
    kernel.fs.chmod("/root/protected", 0o600)
    kernel.fs.chown("/root/protected", 0)
    
    # Create an SUID script owned by root
    # This script will try to overwrite the protected file
    kernel.fs.write("/usr/bin/pwn.sh", "write /root/protected 'changed'")
    kernel.fs.chown("/usr/bin/pwn.sh", 0)
    kernel.fs.chmod("/usr/bin/pwn.sh", 0o4755) # SUID root, rwxr-xr-x
    
    kernel.users.su("guest")
    
    # Guest cannot write directly
    try:
        kernel.fs.write("/root/protected", "guest_hack")
        pytest.fail("Guest should not be able to write to /root/protected")
    except PermissionError:
        pass
    
    # Guest runs the SUID script
    res = shell.execute("/usr/bin/pwn.sh", add_to_history=False)
    assert res is True
    
    # Check if file was actually changed
    kernel.users.su("root")
    assert kernel.fs.read("/root/protected") == "changed"

def test_sgid_privilege_elevation(kernel, shell):
    """Verify that SGID scripts can write to group-writable files."""
    # Create a group-writable file owned by root:sudo
    kernel.fs.write("/tmp/group_file", "content")
    kernel.fs.chown("/tmp/group_file", 0)
    kernel.fs.chgrp("/tmp/group_file", 27) # sudo group
    kernel.fs.chmod("/tmp/group_file", 0o660) # rw-rw----
    
    # Create a user 'testuser' who is NOT in sudo group
    kernel.users.add_user("testuser", uid=2000, gid=2000)
    kernel.users.su("testuser")
    
    # Verify testuser cannot write
    try:
        kernel.fs.write("/tmp/group_file", "testuser_hack")
        pytest.fail("testuser should not be able to write")
    except PermissionError:
        pass
        
    # Create an SGID script owned by root:sudo
    kernel.users.su("root")
    kernel.fs.write("/usr/bin/group_pwn.sh", "write /tmp/group_file 'sgid_success'")
    kernel.fs.chown("/usr/bin/group_pwn.sh", 0)
    kernel.fs.chgrp("/usr/bin/group_pwn.sh", 27)
    kernel.fs.chmod("/usr/bin/group_pwn.sh", 0o2755) # SGID sudo, rwxr-xr-x
    
    kernel.users.su("testuser")
    
    # testuser runs the SGID script
    res = shell.execute("/usr/bin/group_pwn.sh", add_to_history=False)
    assert res is True
    
    # Verify success
    kernel.users.su("root")
    assert kernel.fs.read("/tmp/group_file") == "sgid_success"
