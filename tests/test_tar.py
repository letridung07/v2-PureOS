import pytest
from pureos.kernel import Kernel


def test_tar_create_list_extract(kernel, shell):
    # Prepare directory structure
    kernel.fs.mkdir("/tmp/tardir")
    kernel.fs.write("/tmp/tardir/file1.txt", "hello tar")
    kernel.fs.write("/tmp/tardir/file2.txt", "second file content")
    kernel.fs.mkdir("/tmp/tardir/sub")
    kernel.fs.write("/tmp/tardir/sub/file3.txt", "nested content")

    # Create tar
    res = shell.execute("tar -cf /tmp/archive.tar /tmp/tardir")
    assert res is True
    assert kernel.fs.exists("/tmp/archive.tar")

    # List tar
    list_out = shell.registry.execute(
        ["tar", "-tf", "/tmp/archive.tar"], capture_output=True
    )
    assert "tardir/file1.txt" in list_out
    assert "tardir/file2.txt" in list_out
    assert "tardir/sub/file3.txt" in list_out
    assert "tardir/sub/" in list_out

    # Delete original tardir
    kernel.fs.delete("/tmp/tardir")
    assert not kernel.fs.exists("/tmp/tardir")

    # Extract tar
    shell.execute("cd /tmp")
    res_extract = shell.execute("tar -xf /tmp/archive.tar")
    assert res_extract is True

    # Verify restoration
    assert kernel.fs.exists("/tmp/tardir/file1.txt")
    assert kernel.fs.read("/tmp/tardir/file1.txt") == "hello tar"
    assert kernel.fs.exists("/tmp/tardir/sub/file3.txt")
    assert kernel.fs.read("/tmp/tardir/sub/file3.txt") == "nested content"


def test_tar_gzip(kernel, shell):
    # Prepare files
    kernel.fs.mkdir("/tmp/tardir_gz")
    kernel.fs.write("/tmp/tardir_gz/data.txt", "gzip test content" * 100)

    # Create gzip tar
    res = shell.execute("tar -czf /tmp/archive.tar.gz /tmp/tardir_gz")
    assert res is True
    assert kernel.fs.exists("/tmp/archive.tar.gz")

    # List gzip tar
    list_out = shell.registry.execute(
        ["tar", "-tzf", "/tmp/archive.tar.gz"], capture_output=True
    )
    assert "tardir_gz/data.txt" in list_out

    # Delete and extract
    kernel.fs.delete("/tmp/tardir_gz")
    res_extract = shell.execute("tar -xzf /tmp/archive.tar.gz -C /tmp")
    assert res_extract is True

    # Verify
    assert kernel.fs.exists("/tmp/tardir_gz/data.txt")
    assert kernel.fs.read("/tmp/tardir_gz/data.txt") == "gzip test content" * 100


def test_tar_verbose(kernel, shell, capsys):
    kernel.fs.mkdir("/tmp/tardir_verbose")
    kernel.fs.write("/tmp/tardir_verbose/a.txt", "a")

    # Create verbose
    shell.execute("tar -cvf /tmp/archive_verbose.tar /tmp/tardir_verbose")
    captured = capsys.readouterr()
    assert "tardir_verbose/a.txt" in captured.out

    # Extract verbose
    kernel.fs.delete("/tmp/tardir_verbose")
    shell.execute("cd /tmp")
    shell.execute("tar -xvf /tmp/archive_verbose.tar")
    captured = capsys.readouterr()
    assert "tardir_verbose/a.txt" in captured.out
