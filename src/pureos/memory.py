"""Memory management subsystem — MemoryDriver for v2-PureOS."""

import threading
from typing import Dict, Tuple

from .drivers import Driver


class MemoryDriver(Driver):
    """Tracks global and per-process memory usage.

    Allocations draw from physical RAM first, then swap.  Stats are surfaced
    via commands and mirrored into a /proc virtual filesystem written to the
    kernel VirtualFS so that standard commands like ``cat /proc/meminfo`` work
    without any special cases.
    """

    name = "memory"
    description = "Memory management subsystem"

    def __init__(self, kernel):
        super().__init__(kernel)
        self.total_kb = 0
        self.used_kb = 0
        self.cached_kb = 0
        self.swap_total_kb = 0
        self.swap_used_kb = 0
        self._per_process: Dict[int, int] = {}
        self._lock = threading.Lock()

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def free_kb(self) -> int:
        """Physical memory that is currently unallocated."""
        return self.total_kb - self.used_kb - self.cached_kb

    @property
    def available_kb(self) -> int:
        """Memory available for new allocations (free + reclaimable cached)."""
        return self.free_kb + self.cached_kb

    # ------------------------------------------------------------------
    # Driver lifecycle
    # ------------------------------------------------------------------

    def on_load(self):
        cfg = self.kernel.config
        self.total_kb = cfg.memory_total_kb
        self.swap_total_kb = cfg.memory_swap_kb

        fs = self.kernel.fs
        if not fs.exists("/proc/"):
            fs.mkdir("/proc")
        self._write_meminfo()

    def on_unload(self):
        with self._lock:
            pids = list(self._per_process.keys())
        for pid in pids:
            self._delete_proc_status(pid)
        fs = self.kernel.fs
        if fs.exists("/proc/meminfo"):
            fs.delete("/proc/meminfo")
        self._per_process.clear()
        self.used_kb = 0
        self.cached_kb = 0
        self.swap_used_kb = 0

    # ------------------------------------------------------------------
    # Core allocation API
    # ------------------------------------------------------------------

    def alloc(self, pid: int, size_kb: int) -> bool:
        """Allocate *size_kb* to process *pid*.

        Returns ``True`` on success, ``False`` if not enough memory is available
        (physical + swap).

        Updates the Process dataclass fields *vsize* and *rss* and refreshes
        /proc files.
        """
        if size_kb <= 0:
            return False

        with self._lock:
            if self.total_kb > 0:
                total_free = (
                    self.total_kb
                    + self.swap_total_kb
                    - self.used_kb
                    - self.swap_used_kb
                )
                if size_kb > total_free:
                    return False

                phys_free = self.total_kb - self.used_kb - self.cached_kb
                if size_kb <= phys_free:
                    self.used_kb += size_kb
                else:
                    from_physical = max(phys_free, 0)
                    self.used_kb += from_physical
                    remainder = size_kb - from_physical
                    self.swap_used_kb += remainder
            else:
                self.used_kb += size_kb

            self._per_process[pid] = self._per_process.get(pid, 0) + size_kb

            self._sync_process_fields(pid)
            self._update_proc_files()
            return True

    def free(self, pid: int, size_kb: int) -> bool:
        """Release *size_kb* from process *pid*.

        Clamps to the actual allocated amount for the process.  Returns
        ``True`` if any memory was released.
        """
        if size_kb <= 0:
            return False

        with self._lock:
            allocated = self._per_process.get(pid, 0)
            if allocated == 0:
                return False
            to_free = min(size_kb, allocated)

            from_physical = min(to_free, self.used_kb)
            self.used_kb -= from_physical
            self.swap_used_kb = max(0, self.swap_used_kb - (to_free - from_physical))

            self._per_process[pid] = allocated - to_free
            if self._per_process[pid] == 0:
                del self._per_process[pid]

            self._sync_process_fields(pid)
            self._update_proc_files()
            return True

    def free_all(self, pid: int):
        """Release all memory held by *pid*, cleaning up /proc/<pid>/status."""
        with self._lock:
            allocated = self._per_process.pop(pid, 0)
            if allocated > 0:
                from_physical = min(allocated, self.used_kb)
                self.used_kb -= from_physical
                self.swap_used_kb = max(
                    0, self.swap_used_kb - (allocated - from_physical)
                )
                self._sync_process_fields(pid)
                self._delete_proc_status(pid)
                self._write_meminfo()

    # ------------------------------------------------------------------
    # Queries (used by commands)
    # ------------------------------------------------------------------

    def get_stats(self) -> dict:
        """Return a snapshot of global memory statistics."""
        return {
            "total": self.total_kb,
            "used": self.used_kb,
            "free": self.free_kb,
            "cached": self.cached_kb,
            "available": self.available_kb,
            "swap_total": self.swap_total_kb,
            "swap_used": self.swap_used_kb,
            "swap_free": self.swap_total_kb - self.swap_used_kb,
        }

    def get_all_process_memory(self) -> Dict[int, Tuple[int, int]]:
        """Return ``{pid: (vsize, rss)}`` for every tracked process."""
        result: Dict[int, Tuple[int, int]] = {}
        for pid, proc in self.kernel.scheduler.processes.items():
            result[pid] = (proc.vsize, proc.rss)
        return result

    # ------------------------------------------------------------------
    # /proc filesystem helpers
    # ------------------------------------------------------------------

    def _sync_process_fields(self, pid: int):
        """Push tracked values into the Process dataclass."""
        proc = self.kernel.scheduler.processes.get(pid)
        if proc is None:
            return
        allocated = self._per_process.get(pid, 0)
        proc.vsize = allocated
        proc.rss = allocated

    def _update_proc_files(self):
        """Refresh /proc/meminfo and every /proc/<pid>/status."""
        self._write_meminfo()
        for pid in self._per_process:
            self._write_proc_status(pid)

    def _write_meminfo(self):
        self.kernel.fs.write("/proc/meminfo", self._format_meminfo())

    def _write_proc_status(self, pid: int):
        proc = self.kernel.scheduler.processes.get(pid)
        if proc is None:
            return
        self.kernel.fs.write(f"/proc/{pid}/status", self._format_proc_status(pid))

    def _delete_proc_status(self, pid: int):
        fs = self.kernel.fs
        path = f"/proc/{pid}/status"
        if fs.exists(path):
            fs.delete(path)

    def _format_meminfo(self) -> str:
        s = self.get_stats()
        return (
            f"MemTotal:     {s['total']:>8} kB\n"
            f"MemFree:      {s['free']:>8} kB\n"
            f"MemAvailable: {s['available']:>8} kB\n"
            f"Cached:       {s['cached']:>8} kB\n"
            f"SwapTotal:    {s['swap_total']:>8} kB\n"
            f"SwapFree:     {s['swap_free']:>8} kB\n"
        )

    def _format_proc_status(self, pid: int) -> str:
        proc = self.kernel.scheduler.processes.get(pid)
        if proc is None:
            return ""
        return (
            f"Name:\t{proc.name}\n"
            f"Pid:\t{proc.pid}\n"
            f"State:\t{proc.status}\n"
            f"VmSize:\t{proc.vsize:>8} kB\n"
            f"VmRSS:\t{proc.rss:>8} kB\n"
        )
