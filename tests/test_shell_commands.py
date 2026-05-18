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
