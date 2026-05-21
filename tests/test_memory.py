import importlib
import os
import sys

try:
    kernel_mod = importlib.import_module("pureos.kernel")
    memory_mod = importlib.import_module("pureos.memory")
    processes_mod = importlib.import_module("pureos.processes")
except Exception:
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
    kernel_mod = importlib.import_module("pureos.kernel")
    memory_mod = importlib.import_module("pureos.memory")
    processes_mod = importlib.import_module("pureos.processes")

Kernel = kernel_mod.Kernel
MemoryDriver = memory_mod.MemoryDriver
Process = processes_mod.Process
Scheduler = processes_mod.Scheduler


# ------------------------------------------------------------------
# MemoryDriver unit tests
# ------------------------------------------------------------------


class TestMemoryDriver:
    def test_on_load_initializes_from_config(self, tmp_path):
        k = Kernel(
            config={
                "memory_total_kb": 4194304,
                "memory_swap_kb": 1048576,
                "fs_backing": str(tmp_path / "store.json"),
            }
        )
        k.initialize()
        mem = k.drivers.drivers["memory"]
        assert mem.total_kb == 4194304
        assert mem.swap_total_kb == 1048576
        assert mem.used_kb == 0
        assert mem.free_kb == 4194304
        k.shutdown()

    def test_proc_directory_created_on_load(self, tmp_path):
        k = Kernel(config={"fs_backing": str(tmp_path / "store.json")})
        k.initialize()
        assert k.fs.is_dir("/proc")
        assert k.fs.exists("/proc/meminfo")
        k.shutdown()

    def test_alloc_succeeds_with_enough_memory(self, tmp_path):
        k = Kernel(
            config={
                "memory_total_kb": 10240,
                "fs_backing": str(tmp_path / "store.json"),
            }
        )
        k.initialize()
        mem = k.drivers.drivers["memory"]
        p = k.scheduler.spawn("testproc", runtime=0.1)
        assert mem._per_process.get(p.pid, 0) == 1024
        assert mem.used_kb == 1024
        k.shutdown()

    def test_alloc_fails_when_out_of_memory(self, tmp_path):
        k = Kernel(
            config={
                "memory_total_kb": 2048,
                "memory_swap_kb": 0,
                "fs_backing": str(tmp_path / "store.json"),
            }
        )
        k.initialize()
        mem = k.drivers.drivers["memory"]
        assert mem.alloc(1, 3000) is False
        assert mem.used_kb == 0
        k.shutdown()

    def test_alloc_spills_to_swap(self, tmp_path):
        k = Kernel(
            config={
                "memory_total_kb": 2048,
                "memory_swap_kb": 1024,
                "fs_backing": str(tmp_path / "store.json"),
            }
        )
        k.initialize()
        mem = k.drivers.drivers["memory"]
        assert mem.alloc(1, 3000)
        assert mem.used_kb == 2048
        assert mem.swap_used_kb == 952
        assert mem.get_stats()["swap_free"] == 72
        k.shutdown()

    def test_alloc_fails_when_swap_exhausted(self, tmp_path):
        k = Kernel(
            config={
                "memory_total_kb": 2048,
                "memory_swap_kb": 512,
                "fs_backing": str(tmp_path / "store.json"),
            }
        )
        k.initialize()
        mem = k.drivers.drivers["memory"]
        assert mem.alloc(1, 2048)
        assert mem.alloc(2, 600) is False
        k.shutdown()

    def test_free_reclaims_memory(self, tmp_path):
        k = Kernel(
            config={
                "memory_total_kb": 10240,
                "fs_backing": str(tmp_path / "store.json"),
            }
        )
        k.initialize()
        mem = k.drivers.drivers["memory"]
        mem.alloc(1, 4096)
        assert mem.free(1, 2048)
        assert mem._per_process[1] == 2048
        assert mem.used_kb == 2048
        k.shutdown()

    def test_free_all_cleans_up_process(self, tmp_path):
        k = Kernel(
            config={
                "memory_total_kb": 10240,
                "fs_backing": str(tmp_path / "store.json"),
            }
        )
        k.initialize()
        mem = k.drivers.drivers["memory"]
        p = k.scheduler.spawn("cleanup_test", runtime=0.5)
        pid = p.pid
        assert k.fs.exists(f"/proc/{pid}/status")
        assert k.fs.is_dir(f"/proc/{pid}/")
        mem.free_all(pid)
        assert pid not in mem._per_process
        assert mem.used_kb == 0
        assert not k.fs.exists(f"/proc/{pid}/status")
        assert not k.fs.is_dir(f"/proc/{pid}/")
        k.shutdown()

    def test_get_stats_accuracy(self, tmp_path):
        k = Kernel(
            config={
                "memory_total_kb": 10000,
                "memory_swap_kb": 2000,
                "fs_backing": str(tmp_path / "store.json"),
            }
        )
        k.initialize()
        mem = k.drivers.drivers["memory"]
        mem.cached_kb = 1000
        mem.alloc(1, 3000)
        s = mem.get_stats()
        assert s["total"] == 10000
        assert s["used"] == 3000
        assert s["free"] == 6000
        assert s["cached"] == 1000
        assert s["available"] == 7000
        assert s["swap_total"] == 2000
        assert s["swap_used"] == 0
        assert s["swap_free"] == 2000
        k.shutdown()

    def test_proc_meminfo_content(self, tmp_path):
        k = Kernel(
            config={
                "memory_total_kb": 8192,
                "memory_swap_kb": 1024,
                "fs_backing": str(tmp_path / "store.json"),
            }
        )
        k.initialize()
        content = k.fs.read("/proc/meminfo")
        assert "MemTotal:" in content
        assert "MemFree:" in content
        assert "MemAvailable:" in content
        assert "SwapTotal:" in content
        assert "8192" in content
        assert "1024" in content
        k.shutdown()

    def test_proc_status_per_process(self, tmp_path):
        k = Kernel(
            config={
                "memory_total_kb": 10240,
                "fs_backing": str(tmp_path / "store.json"),
            }
        )
        k.initialize()
        p = k.scheduler.spawn("status_test", runtime=1.0)
        assert k.fs.exists(f"/proc/{p.pid}/status")
        content = k.fs.read(f"/proc/{p.pid}/status")
        assert f"Pid:\t{p.pid}" in content
        assert "VmSize:" in content
        assert "VmRSS:" in content
        k.shutdown()

    def test_concurrent_alloc_thread_safety(self, tmp_path):
        import threading

        k = Kernel(
            config={
                "memory_total_kb": 102400,
                "fs_backing": str(tmp_path / "store.json"),
            }
        )
        k.initialize()
        mem = k.drivers.drivers["memory"]
        errors = []

        def worker(pid_offset):
            for i in range(10):
                if not mem.alloc(pid_offset * 100 + i, 100):
                    errors.append(f"alloc fail {pid_offset * 100 + i}")

        threads = [threading.Thread(target=worker, args=(t,)) for t in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0
        assert mem.used_kb == 5 * 10 * 100
        k.shutdown()

    def test_alloc_zero_or_negative_returns_false(self, tmp_path):
        k = Kernel(
            config={
                "memory_total_kb": 10240,
                "fs_backing": str(tmp_path / "store.json"),
            }
        )
        k.initialize()
        mem = k.drivers.drivers["memory"]
        assert mem.alloc(1, 0) is False
        assert mem.alloc(1, -100) is False
        k.shutdown()

    def test_unlimited_memory_when_total_is_zero(self, tmp_path):
        k = Kernel(
            config={
                "memory_total_kb": 0,
                "memory_swap_kb": 0,
                "fs_backing": str(tmp_path / "store.json"),
            }
        )
        k.initialize()
        mem = k.drivers.drivers["memory"]
        assert mem.alloc(1, 999999)
        assert mem.used_kb == 999999
        k.shutdown()


# ------------------------------------------------------------------
# Process / Scheduler integration tests
# ------------------------------------------------------------------


class TestProcessIntegration:
    def test_spawn_allocates_default_working_set(self, tmp_path):
        k = Kernel(
            config={
                "memory_total_kb": 10240,
                "fs_backing": str(tmp_path / "store.json"),
            }
        )
        k.initialize()
        p = k.scheduler.spawn("worker", runtime=0.1)
        assert p.vsize == 1024
        assert p.rss == 1024
        k.shutdown()

    def test_process_exit_frees_memory(self, tmp_path):
        k = Kernel(
            config={
                "memory_total_kb": 10240,
                "fs_backing": str(tmp_path / "store.json"),
            }
        )
        k.initialize()
        p = k.scheduler.spawn("short_lived", runtime=0.05)
        k.scheduler.wait(p.pid, timeout=1.0)
        assert p.status == "completed"
        assert p.vsize == 0
        assert p.rss == 0
        mem = k.drivers.drivers["memory"]
        assert p.pid not in mem._per_process
        k.shutdown()

    def test_kill_frees_memory(self, tmp_path):
        k = Kernel(
            config={
                "memory_total_kb": 10240,
                "fs_backing": str(tmp_path / "store.json"),
            }
        )
        k.initialize()
        mem = k.drivers.drivers["memory"]
        p = k.scheduler.spawn("kill_me", runtime=5.0)
        assert mem._per_process.get(p.pid, 0) == 1024
        k.scheduler.kill(p.pid)
        assert p.pid not in mem._per_process
        assert mem.used_kb == 0
        k.shutdown()

    def test_ps_shows_memory_columns(self, tmp_path):
        k = Kernel(
            config={
                "memory_total_kb": 10240,
                "fs_backing": str(tmp_path / "store.json"),
            }
        )
        k.initialize()
        k.scheduler.spawn("ps_test", runtime=0.1)
        out = k.shell.registry.execute(["ps"], capture_output=True)
        assert "VSZ" in out
        assert "RSS" in out
        assert "1024K" in out
        k.shutdown()

    def test_top_shows_memory_columns(self, tmp_path):
        k = Kernel(
            config={
                "memory_total_kb": 10240,
                "fs_backing": str(tmp_path / "store.json"),
            }
        )
        k.initialize()
        k.scheduler.spawn("top_test", runtime=0.1)
        out = k.shell.registry.execute(["top"], capture_output=True)
        assert "RSS" in out
        assert "1024K" in out
        k.shutdown()


# ------------------------------------------------------------------
# Command output tests
# ------------------------------------------------------------------


class TestCommands:
    def test_free_shows_real_stats(self, tmp_path):
        k = Kernel(
            config={
                "memory_total_kb": 524288,
                "memory_swap_kb": 131072,
                "fs_backing": str(tmp_path / "store.json"),
            }
        )
        k.initialize()
        k.scheduler.spawn("proc_a", runtime=0.1)
        out = k.shell.registry.execute(["free"], capture_output=True)
        assert "Mem:" in out
        assert "524288" in out
        assert "1024" in out
        assert "Swap:" in out
        assert "131072" in out
        k.shutdown()

    def test_info_shows_memory_line(self, tmp_path):
        k = Kernel(
            config={
                "memory_total_kb": 10000,
                "fs_backing": str(tmp_path / "store.json"),
            }
        )
        k.initialize()
        k.scheduler.spawn("info_test", runtime=0.1)
        out = k.shell.registry.execute(["info"], capture_output=True)
        assert "Memory:" in out
        assert "1024K" in out
        k.shutdown()

    def test_mem_global_view(self, tmp_path):
        k = Kernel(
            config={
                "memory_total_kb": 102400,
                "fs_backing": str(tmp_path / "store.json"),
            }
        )
        k.initialize()
        k.scheduler.spawn("mem_a", runtime=0.2)
        k.scheduler.spawn("mem_b", runtime=0.2)
        out = k.shell.registry.execute(["mem"], capture_output=True)
        assert "Memory Statistics" in out
        assert "mem_a" in out
        assert "mem_b" in out
        assert "%MEM" in out
        k.shutdown()

    def test_mem_per_process_view(self, tmp_path):
        k = Kernel(
            config={
                "memory_total_kb": 102400,
                "fs_backing": str(tmp_path / "store.json"),
            }
        )
        k.initialize()
        p = k.scheduler.spawn("detail_proc", runtime=0.3)
        out = k.shell.registry.execute(["mem", str(p.pid)], capture_output=True)
        assert "detail_proc" in out
        assert "VSZ" in out
        assert "RSS" in out
        assert "%MEM" in out
        k.shutdown()

    def test_mem_nonexistent_pid(self, tmp_path):
        k = Kernel(
            config={
                "memory_total_kb": 102400,
                "fs_backing": str(tmp_path / "store.json"),
            }
        )
        k.initialize()
        out = k.shell.registry.execute(["mem", "99999"], capture_output=True)
        assert "No such process" in out
        k.shutdown()

    def test_cat_proc_meminfo(self, tmp_path):
        k = Kernel(
            config={
                "memory_total_kb": 8192,
                "fs_backing": str(tmp_path / "store.json"),
            }
        )
        k.initialize()
        out = k.shell.registry.execute(["cat", "/proc/meminfo"], capture_output=True)
        assert "MemTotal:" in out
        assert "SwapTotal:" in out
        k.shutdown()

    def test_cat_proc_status(self, tmp_path):
        k = Kernel(
            config={
                "memory_total_kb": 10240,
                "fs_backing": str(tmp_path / "store.json"),
            }
        )
        k.initialize()
        p = k.scheduler.spawn("cat_test", runtime=0.3)
        out = k.shell.registry.execute(
            ["cat", f"/proc/{p.pid}/status"], capture_output=True
        )
        assert f"Pid:\t{p.pid}" in out
        assert "VmSize:" in out
        assert "VmRSS:" in out
        k.shutdown()

    def test_free_driver_not_loaded(self, tmp_path):
        k = Kernel(
            config={
                "memory_total_kb": 10240,
                "fs_backing": str(tmp_path / "store.json"),
            }
        )
        k.initialize()
        k.drivers.unload_driver("memory")
        out = k.shell.registry.execute(["free"], capture_output=True)
        assert "not loaded" in out
        k.shutdown()
