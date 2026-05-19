from typing import List, Optional

from .base import Command


class HelpCommand(Command):
    name = "help"

    def execute(self, parts: List[str], input_data=None, capture_output=False):
        print(
            "help, info, export, alias, unalias, history, grep, format, ls [-l] [prefix], pwd, cd <path>, find [path], ps, services, exit"
        )
        print(
            "mkdir <path>, rmdir <path>, rm <path>, mv <src> <dst>, cp <src> <dst>, touch <path>"
        )
        print(
            "write <path> <content>, append <path> <content>, echo <text> > <path>, source <path>"
        )
        print("chmod <mode> <path>, stat <path>")
        print("head <path> [n], tail <path> [n], grep <pattern> [path]")
        print("service start|stop|status|restart <name>")
        print("spawn <name>, kill <pid>")
        print("Command chaining: cmd1 ; cmd2 && cmd3 || cmd4")
        return True


class InfoCommand(Command):
    name = "info"

    def execute(self, parts: List[str], input_data=None, capture_output=False):
        print("Kernel info:")
        print(f"FS entries: {len(self.kernel.fs.files)}")
        print(f"Processes: {len(self.kernel.scheduler.processes)}")
        print(f"Services: {self.kernel.services.list()}")
        return True


class ExportCommand(Command):
    name = "export"

    def execute(self, parts: List[str], input_data=None, capture_output=False):
        shell = self.kernel.shell
        if len(parts) == 1:
            for name, value in shell.env.items():
                print(f"{name}={value}")
            return True
        for assignment in parts[1:]:
            if "=" not in assignment:
                print("Usage: export VAR=value")
                return False
            name, value = assignment.split("=", maxsplit=1)
            shell.env[name] = value
        return True


class AliasCommand(Command):
    name = "alias"

    def execute(self, parts: List[str], input_data=None, capture_output=False):
        shell = self.kernel.shell
        if len(parts) == 1:
            for name, value in shell.aliases.items():
                print(f"alias {name}='{value}'")
            return True
        if len(parts) < 3:
            print("Usage: alias name command")
            return False
        name = parts[1]
        value = " ".join(parts[2:])
        shell.aliases[name] = value
        print(f"Alias {name}='{value}'")
        return True


class UnaliasCommand(Command):
    name = "unalias"

    def execute(self, parts: List[str], input_data=None, capture_output=False):
        shell = self.kernel.shell
        if len(parts) != 2:
            print("Usage: unalias name")
            return False
        name = parts[1]
        if name not in shell.aliases:
            print(f"alias: {name}: not found")
            return False
        del shell.aliases[name]
        return True


class HistoryCommand(Command):
    name = "history"

    def execute(self, parts: List[str], input_data=None, capture_output=False):
        shell = self.kernel.shell
        for index, entry in enumerate(shell.history, 1):
            print(f"{index}  {entry}")
        return True


def register_system_commands(registry):
    registry.register(HelpCommand(registry.kernel))
    registry.register(InfoCommand(registry.kernel))
    registry.register(ExportCommand(registry.kernel))
    registry.register(AliasCommand(registry.kernel))
    registry.register(UnaliasCommand(registry.kernel))
    registry.register(HistoryCommand(registry.kernel))
