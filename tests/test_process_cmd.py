"""Tests for process management commands."""

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


class TestProcessCommands:
    def _make_kernel(self, tmp_path):
        backing = tmp_path / "store.json"
        k = Kernel(config={"fs_backing": str(backing)})
        k.initialize()
        return k

    def test_ps_shows_processes(self, tmp_path):
        k = self._make_kernel(tmp_path)
        out = k.shell.registry.execute(["ps"], capture_output=True)
        assert "PID" in out
        assert "NAME" in out
        k.shutdown()

    def test_spawn_creates_process(self, tmp_path):
        k = self._make_kernel(tmp_path)
        result = k.shell.registry.execute(["spawn", "myproc"])
        assert result is True
        assert len(k.scheduler.list()) >= 1
        k.shutdown()

    def test_spawn_no_name_shows_usage(self, tmp_path):
        k = self._make_kernel(tmp_path)
        result = k.shell.registry.execute(["spawn"])
        assert result is False
        k.shutdown()

    def test_kill_terminates_process(self, tmp_path):
        k = self._make_kernel(tmp_path)
        k.shell.registry.execute(["spawn", "killme"])
        procs = k.scheduler.list()
        pid = procs[0].pid
        result = k.shell.registry.execute(["kill", str(pid)])
        assert result is True
        k.shutdown()

    def test_kill_nonexistent_pid(self, tmp_path):
        k = self._make_kernel(tmp_path)
        result = k.shell.registry.execute(["kill", "999"])
        assert result is False
        k.shutdown()

    def test_kill_no_pid_shows_usage(self, tmp_path):
        k = self._make_kernel(tmp_path)
        result = k.shell.registry.execute(["kill"])
        assert result is False
        k.shutdown()

    def test_kill_invalid_pid(self, tmp_path):
        k = self._make_kernel(tmp_path)
        result = k.shell.registry.execute(["kill", "abc"])
        assert result is False
        k.shutdown()

    def test_kill_with_signals(self, tmp_path):
        k = self._make_kernel(tmp_path)
        k.shell.registry.execute(["spawn", "sigtest"])
        procs = k.scheduler.list()
        pid = procs[0].pid

        # SIGSTOP
        result = k.shell.registry.execute(["kill", "-STOP", str(pid)])
        assert result is True
        time.sleep(0.05)
        p = k.scheduler.status(pid)
        assert p.status == "suspended"

        # SIGCONT
        result = k.shell.registry.execute(["kill", "-CONT", str(pid)])
        assert result is True
        time.sleep(0.05)
        p = k.scheduler.status(pid)
        assert p.status == "running"

        # SIGKILL
        result = k.shell.registry.execute(["kill", "-KILL", str(pid)])
        assert result is True
        k.shutdown()

    def test_kill_unknown_signal(self, tmp_path):
        k = self._make_kernel(tmp_path)
        k.shell.registry.execute(["spawn", "bad_sig"])
        procs = k.scheduler.list()
        pid = procs[0].pid
        result = k.shell.registry.execute(["kill", "-BOGUS", str(pid)])
        assert result is False
        k.shutdown()

    def test_bg_resumes_suspended(self, tmp_path):
        k = self._make_kernel(tmp_path)
        k.shell.registry.execute(["spawn", "bgtest"])
        procs = k.scheduler.list()
        pid = procs[0].pid
        k.scheduler.suspend(pid)
        result = k.shell.registry.execute(["bg", str(pid)])
        assert result is True
        k.shutdown()

    def test_bg_nonexistent(self, tmp_path):
        k = self._make_kernel(tmp_path)
        result = k.shell.registry.execute(["bg", "999"])
        assert result is False
        k.shutdown()

    def test_bg_no_pid(self, tmp_path):
        k = self._make_kernel(tmp_path)
        result = k.shell.registry.execute(["bg"])
        assert result is False
        k.shutdown()

    def test_bg_invalid_pid(self, tmp_path):
        k = self._make_kernel(tmp_path)
        result = k.shell.registry.execute(["bg", "abc"])
        assert result is False
        k.shutdown()

    def test_wait_all(self, tmp_path):
        k = self._make_kernel(tmp_path)
        k.scheduler.spawn("quick_proc", runtime=0.1)
        result = k.shell.registry.execute(["wait"])
        assert result is True
        k.shutdown()

    def test_wait_specific_pid(self, tmp_path):
        k = self._make_kernel(tmp_path)
        p = k.scheduler.spawn("wait_proc", runtime=0.1)
        result = k.shell.registry.execute(["wait", str(p.pid)])
        assert result is True
        k.shutdown()

    def test_wait_nonexistent(self, tmp_path):
        k = self._make_kernel(tmp_path)
        result = k.shell.registry.execute(["wait", "999"])
        assert result is False
        k.shutdown()

    def test_wait_invalid_pid(self, tmp_path):
        k = self._make_kernel(tmp_path)
        result = k.shell.registry.execute(["wait", "abc"])
        assert result is False
        k.shutdown()

    def test_top_shows_snapshot(self, tmp_path):
        k = self._make_kernel(tmp_path)
        k.shell.registry.execute(["spawn", "topproc"])
        out = k.shell.registry.execute(["top"], capture_output=True)
        assert "Tasks:" in out
        assert "PID" in out
        k.shutdown()

    def test_renice_changes_priority(self, tmp_path):
        k = self._make_kernel(tmp_path)
        p = k.scheduler.spawn("nice_proc")
        result = k.shell.registry.execute(["renice", "5", str(p.pid)])
        assert result is True
        proc = k.scheduler.status(p.pid)
        assert proc.nice == 5
        k.shutdown()

    def test_renice_nonexistent(self, tmp_path):
        k = self._make_kernel(tmp_path)
        result = k.shell.registry.execute(["renice", "5", "999"])
        assert result is False
        k.shutdown()

    def test_renice_usage(self, tmp_path):
        k = self._make_kernel(tmp_path)
        result = k.shell.registry.execute(["renice"])
        assert result is False
        k.shutdown()

    def test_renice_invalid_args(self, tmp_path):
        k = self._make_kernel(tmp_path)
        result = k.shell.registry.execute(["renice", "abc", "1"])
        assert result is False
        k.shutdown()
