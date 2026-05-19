from typing import List

from .base import Command


class PsCommand(Command):
    name = "ps"

    def execute(self, parts: List[str], input_data=None, capture_output=False):
        for p in self.kernel.scheduler.list():
            print(f"{p.pid}\t{p.name}\t{p.status}")
        return True


class SpawnCommand(Command):
    name = "spawn"

    def execute(self, parts: List[str], input_data=None, capture_output=False):
        if len(parts) < 2:
            print("Usage: spawn <name>")
            return False
        name = parts[1]
        p = self.kernel.scheduler.spawn(name)
        print(f"Spawned process {p.pid} ({p.name})")
        return True


class KillCommand(Command):
    name = "kill"

    def execute(self, parts: List[str], input_data=None, capture_output=False):
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


def register_process_commands(registry):
    registry.register(PsCommand(registry.kernel))
    registry.register(SpawnCommand(registry.kernel))
    registry.register(KillCommand(registry.kernel))
