from typing import List

from .base import Command


class PsCommand(Command):
    name = "ps"
    usage = "ps"
    description = "List running and managed processes."

    def execute(
        self, parts: List[str], input_data=None, capture_output=False, raw_line=None
    ):
        for p in self.kernel.scheduler.list():
            print(f"{p.pid}\t{p.name}\t{p.status}")
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
    usage = "kill <pid>"
    description = "Terminate a managed process."

    def execute(
        self, parts: List[str], input_data=None, capture_output=False, raw_line=None
    ):
        if len(parts) < 2:
            print("Usage: kill <pid>")
            return False
        try:
            pid = int(parts[1])
        except ValueError:
            print("Usage: kill <pid>")
            return False
        ok = self.kernel.scheduler.kill(pid)
        if ok:
            print(f"Killed process {pid}")
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
