"""Tests for process management commands."""

import importlib
import os
import sys
import time

try:
    kernel_mod = importlib.import_module("pureos.core.kernel")
except Exception:
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
    kernel_mod = importlib.import_module("pureos.core.kernel")

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
        procs = [p for p in k.scheduler.list() if p.name == "killme"]
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
        procs = [p for p in k.scheduler.list() if p.name == "sigtest"]
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
        procs = [p for p in k.scheduler.list() if p.name == "bad_sig"]
        pid = procs[0].pid
        result = k.shell.registry.execute(["kill", "-BOGUS", str(pid)])
        assert result is False
        k.shutdown()

    def test_bg_resumes_suspended(self, tmp_path):
        k = self._make_kernel(tmp_path)
        k.shell.registry.execute(["spawn", "bgtest"])
        procs = [p for p in k.scheduler.list() if p.name == "bgtest"]
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

    def test_wait_command(self, tmp_path):
        k = self._make_kernel(tmp_path)
        shell = k.shell
        # Spawn background job
        shell.execute("spawn slow_job 0.1")
        # Find the process by name
        procs = [p for p in k.scheduler.list() if p.name == "slow_job"]
        assert len(procs) == 1
        p = procs[0]

        # Status should be running (or completed if it was very fast)
        assert p.status in ("running", "completed")

        # Wait for this process
        res = shell.execute(f"wait {p.pid}")
        assert res is True

        # After wait, status should be completed
        assert p.status == "completed"

        # Wait for non-existent process should return False
        res2 = shell.execute("wait 999")
        assert res2 is False
        k.shutdown()

    def test_wait_command_all_extended(self, tmp_path):
        k = self._make_kernel(tmp_path)
        shell = k.shell
        # Spawn multiple background jobs
        shell.execute("spawn job1 0.1")
        shell.execute("spawn job2 0.1")

        procs = k.scheduler.list()
        assert len(procs) >= 2

        # Wait all
        res = shell.execute("wait")
        assert res is True

        assert all(p.status == "completed" for p in procs)
        k.shutdown()

    def test_wait_command_multi(self, tmp_path):
        k = self._make_kernel(tmp_path)
        shell = k.shell
        # Spawn multiple background jobs
        shell.execute("spawn job1 0.1")
        shell.execute("spawn job2 0.1")

        # Find the specific processes
        job1 = [p for p in k.scheduler.list() if p.name == "job1"][0]
        job2 = [p for p in k.scheduler.list() if p.name == "job2"][0]

        # Wait for both specific PIDs
        res = shell.execute(f"wait {job1.pid} {job2.pid}")
        assert res is True

        assert job1.status == "completed"
        assert job2.status == "completed"
        k.shutdown()
