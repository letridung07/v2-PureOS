"""Tests for Pillar 1: Filesystem Enhancements (symlinks, inodes, du, ln, readlink)."""

import pytest
from pureos.core.kernel import Kernel


@pytest.fixture
def kernel():
    k = Kernel({"format_on_boot": True, "auto_start_services": False})
    k.initialize()
    return k


@pytest.fixture
def shell(kernel):
    return kernel.shell


# ---------------------------------------------------------------------------
# Symlinks
# ---------------------------------------------------------------------------


def test_symlink_create_and_readlink(kernel, shell):
    kernel.fs.write("/tmp/original.txt", "hello symlink")
    kernel.fs.symlink("/tmp/original.txt", "/tmp/link.txt")

    assert kernel.fs.readlink("/tmp/link.txt") == "/tmp/original.txt"
    assert kernel.fs.exists("/tmp/link.txt")


def test_symlink_read_through(kernel, shell):
    kernel.fs.write("/tmp/data.txt", "symlink read-through")
    kernel.fs.symlink("/tmp/data.txt", "/tmp/alias.txt")

    content = kernel.fs.read("/tmp/alias.txt")
    assert content == "symlink read-through"


def test_symlink_stat_shows_type(kernel, shell):
    kernel.fs.write("/tmp/target.txt", "x")
    kernel.fs.symlink("/tmp/target.txt", "/tmp/slink.txt")

    info = kernel.fs.stat("/tmp/slink.txt")
    assert info is not None
    assert info["type"] == "symlink"
    assert info["symlink_target"] == "/tmp/target.txt"
    assert info["mode_str"].startswith("l")


def test_ln_s_command(kernel, shell):
    kernel.fs.write("/tmp/orig.txt", "hard target")
    res = shell.execute("ln -s /tmp/orig.txt /tmp/slink")
    assert res is True
    assert kernel.fs.readlink("/tmp/slink") == "/tmp/orig.txt"


def test_readlink_command(kernel, shell):
    kernel.fs.write("/tmp/f.txt", "content")
    kernel.fs.symlink("/tmp/f.txt", "/tmp/l.txt")

    target = shell.registry.execute(["readlink", "/tmp/l.txt"], capture_output=True)
    assert target == "/tmp/f.txt"


def test_readlink_on_non_symlink(kernel, shell, capsys):
    kernel.fs.write("/tmp/plain.txt", "plain")
    res = shell.execute("readlink /tmp/plain.txt")
    assert res is False
    captured = capsys.readouterr()
    assert "not a symbolic link" in captured.out


def test_ln_hard_link(kernel, shell):
    kernel.fs.write("/tmp/source.txt", "hard link data")
    res = shell.execute("ln /tmp/source.txt /tmp/hardlink.txt")
    assert res is True
    # Hard link should share content
    assert kernel.fs.read("/tmp/hardlink.txt") == "hard link data"
    # Hard links share inode
    src_inode = kernel.fs.state.inodes.get("/tmp/source.txt")
    dst_inode = kernel.fs.state.inodes.get("/tmp/hardlink.txt")
    assert src_inode == dst_inode


# ---------------------------------------------------------------------------
# Inodes
# ---------------------------------------------------------------------------


def test_inodes_assigned_on_write(kernel):
    kernel.fs.write("/tmp/inode_test.txt", "data")
    inode = kernel.fs.state.inodes.get("/tmp/inode_test.txt")
    assert inode is not None
    assert inode > 0


def test_stat_shows_inode(kernel, shell):
    kernel.fs.write("/tmp/stat_test.txt", "stat content")
    info = kernel.fs.stat("/tmp/stat_test.txt")
    assert "inode" in info
    assert info["inode"] > 0


def test_stat_shows_link_count(kernel, shell):
    kernel.fs.write("/tmp/lc_test.txt", "link count")
    info = kernel.fs.stat("/tmp/lc_test.txt")
    assert "link_count" in info
    assert info["link_count"] >= 1


# ---------------------------------------------------------------------------
# du command
# ---------------------------------------------------------------------------


def test_du_file(kernel, shell):
    kernel.fs.write("/tmp/du_file.txt", "1234567890")
    out = shell.registry.execute(["du", "/tmp/du_file.txt"], capture_output=True)
    assert "10" in out


def test_du_directory(kernel, shell):
    kernel.fs.mkdir("/tmp/dudir")
    kernel.fs.write("/tmp/dudir/a.txt", "hello")
    kernel.fs.write("/tmp/dudir/b.txt", "world!")
    out = shell.registry.execute(["du", "/tmp/dudir"], capture_output=True)
    # Total = 5 + 6 = 11 bytes
    assert "11" in out


def test_du_human_readable(kernel, shell):
    kernel.fs.write("/tmp/big.txt", "x" * 2048)
    out = shell.registry.execute(["du", "-h", "/tmp/big.txt"], capture_output=True)
    assert "K" in out or "B" in out


# ---------------------------------------------------------------------------
# Sticky bit
# ---------------------------------------------------------------------------


def test_sticky_bit_in_format_mode(kernel):
    from pureos.fs.permissions import FSPermissions

    perm = FSPermissions(kernel.fs.state)
    mode_str = perm.format_mode(0o1777, is_dir=True)
    assert mode_str[0] == "d"
    assert mode_str[-1] == "t"  # sticky bit with execute = 't'


def test_chmod_sets_sticky_bit(kernel, shell):
    kernel.fs.mkdir("/tmp/stickydir")
    shell.execute("chmod 1777 /tmp/stickydir")
    mode = kernel.fs.state.modes.get("/tmp/stickydir/")
    assert mode is not None
    assert mode & 0o1000  # sticky bit set


def test_hard_link_persistence(tmp_path):
    # Test persistence of hard link inode sharing across reboots
    from pureos.core.kernel import Kernel

    store = str(tmp_path / "store.json")
    k = Kernel(config={"fs_backing": store})
    k.initialize()

    # Create file and hard link
    k.fs.write("/file1", "content")
    k.fs.link("/file1", "/link1")

    inode1 = k.fs.state.inodes["/file1"]
    inode_link = k.fs.state.inodes["/link1"]
    assert inode1 == inode_link
    k.fs.persistence.save()

    # Reload kernel
    k2 = Kernel(config={"fs_backing": store})
    k2.initialize()

    assert k2.fs.read("/file1") == "content"
    assert k2.fs.read("/link1") == "content"
    assert k2.fs.state.inodes["/file1"] == k2.fs.state.inodes["/link1"]

    # Update one, check other
    k2.fs.write("/file1", "new content")
    assert k2.fs.read("/link1") == "new content"

    # Delete one, check other stays
    k2.fs.delete("/file1")
    assert k2.fs.exists("/link1")
    assert k2.fs.read("/link1") == "new content"
    assert "/file1" not in k2.fs.state.inodes
