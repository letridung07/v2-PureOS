"""Memory management subsystem — MemoryDriver for v2-PureOS."""

import threading
import time
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
        # Keep a short-lived record of recently freed process allocations
        # so commands that query memory immediately after a process exits
        # can still display the process briefly (helps avoid race conditions
        # on fast platforms like Windows where a process may exit before a
        # monitoring command runs).
        self._recently_freed: Dict[int, tuple[int, int, float]] = {}
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
        else:
            for entry in list(fs.list("/proc/")):
                path = entry if entry.endswith("/") else entry + "/"
                if fs.is_dir(path):
                    fs.delete(path)
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
        (physical + swap) or if user memory quota is exceeded.

        Updates the Process dataclass fields *vsize* and *rss* and refreshes
        /proc files.
        """
        if size_kb <= 0:
            return False

        with self._lock:
            # Check user memory quota
            proc = self.kernel.scheduler.processes.get(pid)
            if proc and proc.uid != 0:
                uid = proc.uid
                user = None
                if self.kernel.users:
                    for u in self.kernel.users.users.values():
                        if u.uid == uid:
                            user = u
                            break

                if user and user.mem_quota > 0:
                    # Calculate total memory used by this user
                    user_used_kb = 0
                    for p_pid, p_size in self._per_process.items():
                        p = self.kernel.scheduler.processes.get(p_pid)
                        if p and p.uid == uid:
                            user_used_kb += p_size

                    if user_used_kb + size_kb > user.mem_quota:
                        import logging

                        logging.getLogger("pureos.audit").warning(
                            f"Memory quota exceeded for user {user.username}: "
                            f"requested {user_used_kb + size_kb} KB, "
                            f"limit {user.mem_quota} KB"
                        )
                        return False

            if self.total_kb > 0:
                total_free = (
                    self.total_kb
                    + self.swap_total_kb
                    - self.used_kb
                    - self.swap_used_kb
                )
                if size_kb > total_free:
                    self.logger.error(
                        "Out of memory: process %s requested %s KB, "
                        "but only %s KB free",
                        pid,
                        size_kb,
                        total_free,
                    )
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

            from_swap = min(to_free, self.swap_used_kb)
            self.swap_used_kb -= from_swap
            self.used_kb = max(0, self.used_kb - (to_free - from_swap))

            self._per_process[pid] = allocated - to_free
            if self._per_process[pid] == 0:
                # Move to recently freed tombstone with timestamp
                freed_amount = allocated
                self._recently_freed[pid] = (freed_amount, freed_amount, time.time())
                del self._per_process[pid]

            # Ensure any tombstone is removed if we re-allocate later
            if pid in self._recently_freed and self._per_process.get(pid, 0) > 0:
                del self._recently_freed[pid]

            self._sync_process_fields(pid)
            self._update_proc_files()
            return True

    def free_all(self, pid: int):
        """Release all memory held by *pid*, cleaning up /proc/<pid>/status."""
        with self._lock:
            allocated = self._per_process.pop(pid, 0)
            if allocated > 0:
                from_swap = min(allocated, self.swap_used_kb)
                self.swap_used_kb -= from_swap
                self.used_kb = max(0, self.used_kb - (allocated - from_swap))
                # Record a short-lived tombstone so monitoring commands can
                # still show this process for a brief interval after exit.
                self._recently_freed[pid] = (allocated, allocated, time.time())
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
        """Return ``{pid: (vsize, rss)}`` for processes with active allocations."""
        result: Dict[int, Tuple[int, int]] = {}
        now = time.time()
        grace = 0.5
        with self._lock:
            # Active allocations
            for pid in list(self._per_process):
                proc = self.kernel.scheduler.processes.get(pid)
                if proc:
                    result[pid] = (proc.vsize, proc.rss)

            # Recently freed allocations (within a short grace window)
            stale = []
            for pid, (vsize, rss, ts) in list(self._recently_freed.items()):
                if now - ts <= grace:
                    result[pid] = (vsize, rss)
                else:
                    stale.append(pid)

            # Cleanup stale tombstones
            for pid in stale:
                try:
                    del self._recently_freed[pid]
                except KeyError:
                    pass
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
        for pid in list(self._per_process.keys()):
            self._write_proc_status(pid)

    def _write_meminfo(self):
        self._run_as_root(
            self.kernel.fs.write, "/proc/meminfo", self._format_meminfo()
        )

    def _write_proc_status(self, pid: int):
        proc = self.kernel.scheduler.processes.get(pid)
        if proc is None:
            return
        self._run_as_root(
            self.kernel.fs.write, f"/proc/{pid}/status", self._format_proc_status(pid)
        )

    def _delete_proc_status(self, pid: int):
        fs = self.kernel.fs
        proc_dir = f"/proc/{pid}/"
        if self._run_as_root(fs.is_dir, proc_dir):
            self._run_as_root(fs.delete, proc_dir)

    def _run_as_root(self, func, *args, **kwargs):
        users = getattr(self.kernel, "users", None)
        if not users:
            return func(*args, **kwargs)
        old_uid = users._effective_uid
        old_gid = users._effective_gid
        users.set_effective_ids(uid=0, gid=0)
        try:
            return func(*args, **kwargs)
        finally:
            users.set_effective_ids(uid=old_uid, gid=old_gid)

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
