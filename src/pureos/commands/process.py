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
            f"{'START':<10} {'TIME':<8} {'NI':>4} {'VSZ':>7} {'RSS':>7}"
        )
        lines = [header]
        for p in self.kernel.scheduler.list():
            if p.is_foreground:
                continue
            elapsed = now - p.start_time if p.start_time else 0
            start_str = (
                _time.strftime("%H:%M:%S", _time.localtime(p.start_time))
                if p.start_time
                else "--:--:--"
            )
            time_str = f"{int(elapsed)}s"
            lines.append(
                f"{p.pid:<6} {p.name:<20} {p.status:<12} "
                f"{start_str:<10} {time_str:<8} {p.nice:>4} "
                f"{p.vsize:>6}K {p.rss:>6}K"
            )
        out = "\n".join(lines)
        return self.emit(out, capture_output)


class SpawnCommand(Command):
    name = "spawn"
    usage = "spawn <name> [runtime]"
    description = "Create a new background process."

    def execute(
        self, parts: List[str], input_data=None, capture_output=False, raw_line=None
    ):
        if len(parts) < 2:
            print("Usage: spawn <name> [runtime]")
            return False
        name = parts[1]
        runtime = 5.0
        if len(parts) >= 3:
            try:
                runtime = float(parts[2])
            except ValueError:
                print("Usage: spawn <name> [runtime]")
                return False
        p = self.kernel.scheduler.spawn(name, runtime=runtime)
        print(f"Spawned process {p.pid} ({p.name})")
        return True


class KillCommand(Command):
    name = "kill"
    usage = "kill [-<signal>] <pid>"
    description = (
        "Terminate or signal a managed process. Use -STOP to suspend, -CONT to resume."
    )

    def execute(
        self, parts: List[str], input_data=None, capture_output=False, raw_line=None
    ):
        args = parts[1:]
        signal = 15  # default SIGTERM
        pid_args = []
        for arg in args:
            if arg.startswith("-"):
                sig_str = arg[1:].upper()
                if sig_str.isdigit():
                    signal = int(sig_str)
                elif sig_str == "STOP":
                    signal = 19
                elif sig_str == "CONT":
                    signal = 18
                elif sig_str == "KILL":
                    signal = 9
                elif sig_str == "TERM":
                    signal = 15
                else:
                    print(f"kill: unknown signal: {arg}")
                    return False
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

        if signal == 19:  # SIGSTOP
            ok = self.kernel.scheduler.suspend(pid)
            sig_name = "SIGSTOP"
        elif signal == 18:  # SIGCONT
            ok = self.kernel.scheduler.resume(pid)
            sig_name = "SIGCONT"
        else:
            ok = self.kernel.scheduler.kill(pid, signal=signal)
            sig_name = f"signal {signal}"
            if signal == 9:
                sig_name = "SIGKILL"
            if signal == 15:
                sig_name = "SIGTERM"

        if ok:
            print(f"Sent {sig_name} to process {pid}")
            return True
        print(f"No such process: {pid}")
        return False


class BgCommand(Command):
    name = "bg"
    usage = "bg <pid>"
    description = "Resume a suspended process in the background."

    def execute(
        self, parts: List[str], input_data=None, capture_output=False, raw_line=None
    ):
        if len(parts) < 2:
            print("Usage: bg <pid>")
            return False
        try:
            pid = int(parts[1])
        except ValueError:
            print("Usage: bg <pid>")
            return False

        ok = self.kernel.scheduler.resume(pid)
        if ok:
            print(f"[{pid}] resumed in background")
            return True
        print(f"bg: {pid}: no such job or not suspended")
        return False


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
    registry.register(BgCommand(registry.kernel))
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
        header = f"{'PID':<6} {'NI':>4} {'STATUS':<12} {'TIME':<8} {'RSS':>7} NAME"
        lines = [f"Tasks: {len(procs)} total", header]
        for p in procs:
            if p.is_foreground:
                continue
            elapsed = now - p.start_time if p.start_time else 0
            time_str = f"{elapsed:.1f}s"
            lines.append(
                f"{p.pid:<6} {p.nice:>4} {p.status:<12} {time_str:<8} "
                f"{p.rss:>6}K {p.name}"
            )
        out = "\n".join(lines)
        return self.emit(out, capture_output)


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
