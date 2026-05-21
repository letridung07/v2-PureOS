from typing import List

from .base import Command


class MemCommand(Command):
    name = "mem"
    aliases = ["memory"]
    usage = "mem [pid]"
    description = "Show memory statistics and per-process memory usage."

    def execute(
        self, parts: List[str], input_data=None, capture_output=False, raw_line=None
    ):
        mem = self.kernel.drivers.drivers.get("memory")
        if not mem:
            return self.emit("Memory driver not loaded.", capture_output)

        if len(parts) > 1:
            try:
                pid = int(parts[1])
            except ValueError:
                print("Usage: mem [pid]")
                return False
            return self._show_process(mem, pid, capture_output)

        return self._show_global(mem, capture_output)

    def _show_global(self, mem, capture_output):
        s = mem.get_stats()
        lines = [
            "Memory Statistics",
            "=================",
            f"  Total:       {s['total']:>10d} KB",
            f"  Used:        {s['used']:>10d} KB",
            f"  Free:        {s['free']:>10d} KB",
            f"  Cached:      {s['cached']:>10d} KB",
            f"  Available:   {s['available']:>10d} KB",
            f"  Swap Total:  {s['swap_total']:>10d} KB",
            f"  Swap Used:   {s['swap_used']:>10d} KB",
            "",
        ]

        per_proc = mem.get_all_process_memory()
        if per_proc:
            sched = self.kernel.scheduler
            header = f"{'PID':<6} {'NAME':<20} {'VSZ':>8} {'RSS':>8} {'%MEM':>6}"
            lines.append(header)
            for pid, (vsize, rss) in sorted(per_proc.items()):
                proc = sched.processes.get(pid)
                name = proc.name if proc else "?"
                pct = (rss / s["total"] * 100) if s["total"] > 0 else 0.0
                lines.append(f"{pid:<6} {name:<20} {vsize:>7}K {rss:>7}K {pct:>5.1f}%")
        else:
            lines.append("No processes with allocated memory.")

        return self.emit("\n".join(lines), capture_output)

    def _show_process(self, mem, pid, capture_output):
        proc = self.kernel.scheduler.processes.get(pid)
        if proc is None:
            return self.emit(f"No such process: {pid}", capture_output)

        s = mem.get_stats()
        vsize = proc.vsize
        rss = proc.rss
        pct = (rss / s["total"] * 100) if s["total"] > 0 else 0.0
        out = (
            f"Process {pid} ({proc.name}):\n"
            f"  Status:  {proc.status}\n"
            f"  VSZ:     {vsize:>8d} KB\n"
            f"  RSS:     {rss:>8d} KB\n"
            f"  %MEM:    {pct:>8.1f}%\n"
            f"  Nice:    {proc.nice}"
        )
        return self.emit(out, capture_output)


def register_memory_commands(registry):
    registry.register(MemCommand(registry.kernel))
