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


def test_env_and_clear_commands(kernel, shell):
    # Test env / printenv
    shell.execute("export FOO=bar")
    shell.execute("export BAZ=qux")

    env_out = shell.registry.execute(["env"], capture_output=True)
    assert "FOO=bar" in env_out
    assert "BAZ=qux" in env_out

    printenv_out = shell.registry.execute(["printenv"], capture_output=True)
    assert "FOO=bar" in printenv_out
    assert "BAZ=qux" in printenv_out

    # Test clear
    clear_out = shell.registry.execute(["clear"], capture_output=True)
    assert clear_out == "\033[H\033[2J"


def test_wait_command(kernel, shell):
    # Spawn background job
    shell.execute("spawn slow_job 0.1")
    procs = kernel.scheduler.list()
    assert len(procs) >= 1
    p = procs[0]

    # Status should be running
    assert p.status == "running"

    # Wait for this process
    res = shell.execute(f"wait {p.pid}")
    assert res is True

    # After wait, status should be completed
    assert p.status == "completed"

    # Wait for non-existent process should return False
    res2 = shell.execute("wait 999")
    assert res2 is False


def test_wait_command_all(kernel, shell):
    # Spawn multiple background jobs
    shell.execute("spawn job1 0.1")
    shell.execute("spawn job2 0.1")

    procs = kernel.scheduler.list()
    assert len(procs) >= 2

    # Wait all
    res = shell.execute("wait")
    assert res is True

    assert all(p.status == "completed" for p in procs)


def test_wait_command_multi(kernel, shell):
    # Spawn multiple background jobs
    shell.execute("spawn job1 0.1")
    shell.execute("spawn job2 0.1")

    procs = kernel.scheduler.list()
    assert len(procs) >= 2
    pids = [p.pid for p in procs]

    # Wait for both specific PIDs
    res = shell.execute(f"wait {pids[0]} {pids[1]}")
    assert res is True

    assert all(p.status == "completed" for p in procs)


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
