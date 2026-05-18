import importlib
import os
import sys
import time

try:
    kernel_mod = importlib.import_module("pureos.kernel")
except Exception:
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
    kernel_mod = importlib.import_module("pureos.kernel")

Kernel = kernel_mod.Kernel


def test_shell_fs_and_processes_and_services(tmp_path, capsys):
    backing = tmp_path / "store.json"
    k = Kernel(config={"fs_backing": str(backing)})
    k.initialize()
    sh = k.shell

    # mkdir
    sh.execute("mkdir /tmp/dir")
    assert k.fs.exists("/tmp/dir/")

    # touch
    sh.execute("touch /tmp/a")
    assert k.fs.exists("/tmp/a")

    # write
    sh.execute("write /tmp/a hello")
    assert k.fs.read("/tmp/a") == "hello"

    # append
    sh.execute("append /tmp/a world")
    assert k.fs.read("/tmp/a") == "helloworld"

    # mv
    sh.execute("mv /tmp/a /tmp/b")
    assert k.fs.read("/tmp/b") == "helloworld"
    assert k.fs.read("/tmp/a") is None

    # cp
    sh.execute("cp /tmp/b /tmp/c")
    assert k.fs.read("/tmp/c") == "helloworld"

    # rm
    sh.execute("rm /tmp/b")
    assert k.fs.read("/tmp/b") is None

    # echo redirect
    sh.execute("echo hi > /tmp/d")
    assert k.fs.read("/tmp/d") == "hi"

    # head/tail
    lines = "\n".join(f"line {i}" for i in range(1, 21))
    k.fs.write("/tmp/lines", lines)
    sh.execute("head /tmp/lines 3")
    captured = capsys.readouterr()
    assert "line 1" in captured.out
    sh.execute("tail /tmp/lines 2")
    captured = capsys.readouterr()
    assert "line 20" in captured.out

    # services
    start_file = tmp_path / "started"

    def svc(ev=None):
        start_file.write_text("started")
        if ev:
            ev.wait(0.2)

    k.services.register("testsrv", svc, daemon=False, stoppable=True)
    sh.execute("service start testsrv")
    time.sleep(0.05)
    assert start_file.exists()

    # status
    sh.execute("service status testsrv")
    captured = capsys.readouterr()
    assert "running=" in captured.out

    # stop
    sh.execute("service stop testsrv")
    time.sleep(0.05)
    t = k.services._threads.get("testsrv")
    assert not (t and t.is_alive())

    # spawn and kill
    sh.execute("spawn worker")
    assert len(k.scheduler.list()) >= 1
    pid = k.scheduler.list()[0].pid
    sh.execute(f"kill {pid}")
    assert k.scheduler.processes[pid].status == "killed"


def test_shell_relative_paths_with_cd_and_rmdir(tmp_path, capsys):
    backing = tmp_path / "store.json"
    k = Kernel(config={"fs_backing": str(backing)})
    k.initialize()
    sh = k.shell
    capsys.readouterr()

    sh.execute("pwd")
    captured = capsys.readouterr()
    assert captured.out.strip() == "/"

    sh.execute("mkdir tmp")
    assert k.fs.exists("/tmp/")

    sh.execute("cd tmp")
    assert k.shell.cwd == "/tmp/"
    capsys.readouterr()

    sh.execute("pwd")
    captured = capsys.readouterr()
    assert captured.out.strip() == "/tmp/"

    sh.execute("write foo hello")
    assert k.fs.read("/tmp/foo") == "hello"

    sh.execute("find")
    captured = capsys.readouterr()
    assert "/tmp/foo" in captured.out

    sh.execute("cd /")
    sh.execute("mkdir /tmp/emptydir")
    sh.execute("rmdir /tmp/emptydir")
    assert not k.fs.exists("/tmp/emptydir/")

    sh.execute("mkdir /tmp/nonempty")
    sh.execute("write /tmp/nonempty/file data")
    sh.execute("rmdir /tmp/nonempty")
    captured = capsys.readouterr()
    assert "Directory not empty" in captured.out
    assert k.fs.exists("/tmp/nonempty/")


def test_shell_cwd_edge_cases(tmp_path, capsys):
    backing = tmp_path / "store.json"
    k = Kernel(config={"fs_backing": str(backing)})
    k.initialize()
    sh = k.shell
    capsys.readouterr()

    sh.execute("mkdir /tmp")
    sh.execute("mkdir /tmp/inner")
    sh.execute("cd /tmp/inner")
    assert sh.cwd == "/tmp/inner/"

    sh.execute("cd ..")
    assert sh.cwd == "/tmp/"

    sh.execute("cd .")
    assert sh.cwd == "/tmp/"

    sh.execute("touch ./file")
    assert k.fs.exists("/tmp/file")

    sh.execute("write ../rootfile hello")
    assert k.fs.read("/rootfile") == "hello"

    sh.execute("cd /")
    sh.execute("find .")
    captured = capsys.readouterr()
    assert "/tmp/" in captured.out
    assert "/rootfile" in captured.out

    sh.execute("rmdir /doesnotexist")
    captured = capsys.readouterr()
    assert "not found" in captured.out

    sh.execute("rmdir /")
    captured = capsys.readouterr()
    assert "Cannot remove root directory" in captured.out


def test_shell_permissions_and_chaining(tmp_path, capsys):
    backing = tmp_path / "store.json"
    k = Kernel(config={"fs_backing": str(backing)})
    k.initialize()
    sh = k.shell

    sh.execute("mkdir /tmp")
    sh.execute("write /tmp/a hello")
    sh.execute("chmod 600 /tmp/a")
    sh.execute("stat /tmp/a")
    captured = capsys.readouterr()
    assert "type: file" in captured.out
    assert "mode: 0o600" in captured.out
    assert "mode_str: -rw-------" in captured.out

    sh.execute("ls -l /tmp")
    captured = capsys.readouterr()
    assert "-rw-------" in captured.out
    assert "/tmp/a" in captured.out

    sh.execute("unknowncmd || echo ok > /tmp/ok")
    assert k.fs.read("/tmp/ok") == "ok"

    sh.execute("mkdir /chain ; touch /chain/a && write /chain/a data || echo fail")
    assert k.fs.read("/chain/a") == "data"


def test_shell_source_script(tmp_path):
    backing = tmp_path / "store.json"
    k = Kernel(config={"fs_backing": str(backing)})
    k.initialize()
    sh = k.shell

    k.fs.write("/tmp/script", "# sample script\nmkdir /scriptdir\nwrite /scriptdir/foo bar\n")
    sh.execute("source /tmp/script")
    assert k.fs.read("/scriptdir/foo") == "bar"
