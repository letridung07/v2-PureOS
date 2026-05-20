from typing import List

from .base import Command


class PsCommand(Command):
    name = "ps"
    usage = "ps"
    description = "List running and managed processes."

    def execute(
        self, parts: List[str], input_data=None, capture_output=False, raw_line=None
    ):
        import time as _time

        now = _time.time()
        header = (
            f"{'PID':<6} {'NAME':<20} {'STATUS':<12} "
            f"{'START':<10} {'TIME':<8} {'NI':>4}"
        )
        lines = [header]
        for p in self.kernel.scheduler.list():
            elapsed = now - p.start_time if p.start_time else 0
            start_str = (
                _time.strftime("%H:%M:%S", _time.localtime(p.start_time))
                if p.start_time
                else "--:--:--"
            )
            time_str = f"{int(elapsed)}s"
            lines.append(
                f"{p.pid:<6} {p.name:<20} {p.status:<12} "
                f"{start_str:<10} {time_str:<8} {p.nice:>4}"
            )
        out = "\n".join(lines)
        if capture_output:
            return out
        print(out)
        return True


class SpawnCommand(Command):
    name = "spawn"
    usage = "spawn <name>"
    description = "Create a new background process."

    def execute(
        self, parts: List[str], input_data=None, capture_output=False, raw_line=None
    ):
        if len(parts) < 2:
            print("Usage: spawn <name>")
            return False
        name = parts[1]
        p = self.kernel.scheduler.spawn(name)
        print(f"Spawned process {p.pid} ({p.name})")
        return True


class KillCommand(Command):
    name = "kill"
    usage = "kill [-<signal>] <pid>"
    description = (
        "Terminate a managed process. Use -9 for SIGKILL, -15 for SIGTERM (default)."
    )

    def execute(
        self, parts: List[str], input_data=None, capture_output=False, raw_line=None
    ):
        args = parts[1:]
        signal = 15  # default SIGTERM
        pid_args = []
        for arg in args:
            if arg.startswith("-") and arg[1:].isdigit():
                signal = int(arg[1:])
            else:
                pid_args.append(arg)
        if not pid_args:
            print("Usage: kill [-<signal>] <pid>")
            return False
        try:
            pid = int(pid_args[0])
        except ValueError:
            print("Usage: kill [-<signal>] <pid>")
            return False
        ok = self.kernel.scheduler.kill(pid, signal=signal)
        if ok:
            sig_name = "SIGKILL" if signal == 9 else f"signal {signal}"
            print(f"Killed process {pid} ({sig_name})")
            return True
        print(f"No such process: {pid}")
        return False


class JobsCommand(Command):
    name = "jobs"
    usage = "jobs"
    description = "List active background jobs."

    def execute(
        self,
        parts: List[str],
        input_data=None,
        capture_output=False,
        raw_line=None,
    ):
        count = 0
        for p in self.kernel.scheduler.list():
            if p.status in ("running", "ready"):
                out = f"[{p.pid}] {p.status}\t{p.name}"
                if capture_output:
                    # Usually jobs prints directly. If capture_output is True,
                    # we can gather and return the output.
                    pass
                print(out)
                count += 1
        return True


class WaitCommand(Command):
    name = "wait"
    usage = "wait [pid]"
    description = "Wait for background processes to complete."

    def execute(
        self,
        parts: List[str],
        input_data=None,
        capture_output=False,
        raw_line=None,
    ):
        if len(parts) > 1:
            pids = []
            for arg in parts[1:]:
                try:
                    pid = int(arg)
                    pids.append(pid)
                except ValueError:
                    print("Usage: wait [pid]...")
                    return False

            for pid in pids:
                p = self.kernel.scheduler.status(pid)
                if not p:
                    print(f"wait: no such process: {pid}")
                    return False

            for pid in pids:
                self.kernel.scheduler.wait(pid)
            return True
        else:
            self.kernel.scheduler.wait_all()
            return True


def register_process_commands(registry):
    registry.register(PsCommand(registry.kernel))
    registry.register(SpawnCommand(registry.kernel))
    registry.register(KillCommand(registry.kernel))
    registry.register(JobsCommand(registry.kernel))
    registry.register(WaitCommand(registry.kernel))
    registry.register(TopCommand(registry.kernel))
    registry.register(ReniceCommand(registry.kernel))


class TopCommand(Command):
    name = "top"
    usage = "top"
    description = "One-shot snapshot of processes ranked by elapsed time."

    def execute(
        self, parts: List[str], input_data=None, capture_output=False, raw_line=None
    ):
        import time as _time

        now = _time.time()
        procs = sorted(
            self.kernel.scheduler.list(),
            key=lambda p: (p.start_time or now),
        )
        header = f"{'PID':<6} {'NI':>4} {'STATUS':<12} {'TIME':<8} NAME"
        lines = [f"Tasks: {len(procs)} total", header]
        for p in procs:
            elapsed = now - p.start_time if p.start_time else 0
            time_str = f"{elapsed:.1f}s"
            lines.append(
                f"{p.pid:<6} {p.nice:>4} {p.status:<12} {time_str:<8} {p.name}"
            )
        out = "\n".join(lines)
        if capture_output:
            return out
        print(out)
        return True


class ReniceCommand(Command):
    name = "renice"
    usage = "renice <priority> <pid>"
    description = "Change the nice value (priority) of a process."

    def execute(
        self, parts: List[str], input_data=None, capture_output=False, raw_line=None
    ):
        if len(parts) < 3:
            print("Usage: renice <priority> <pid>")
            return False
        try:
            priority = int(parts[1])
            pid = int(parts[2])
        except ValueError:
            print("Usage: renice <priority> <pid>")
            return False
        ok = self.kernel.scheduler.renice(pid, priority)
        if ok:
            print(f"Process {pid} nice value set to {priority}")
            return True
        print(f"No such process: {pid}")
        return False
