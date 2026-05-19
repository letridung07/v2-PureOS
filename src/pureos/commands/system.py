from typing import List

from .base import Command


class HelpCommand(Command):
    name = "help"
    description = "Show available commands and usage"
    usage = "help"

    def execute(
        self, parts: List[str], input_data=None, capture_output=False, raw_line=None
    ):
        seen = set()
        commands = []
        for command in self.kernel.shell.registry.commands.values():
            if id(command) in seen:
                continue
            seen.add(id(command))
            commands.append(command)
        commands.sort(key=lambda command: command.name)
        print("Available commands:")
        for command in commands:
            alias_text = ""
            if command.aliases:
                alias_text = f" (aliases: {', '.join(command.aliases)})"
            usage = getattr(command, "usage", command.name) or command.name
            description = getattr(command, "description", "")
            print(f"  {usage}{alias_text}")
            if description:
                print(f"    {description}")
        print("Command chaining: cmd1 ; cmd2 && cmd3 || cmd4")
        return True


class InfoCommand(Command):
    name = "info"
    usage = "info"
    description = "Show kernel state and loaded components."

    def execute(
        self, parts: List[str], input_data=None, capture_output=False, raw_line=None
    ):
        print("Kernel info:")
        print(f"FS entries: {len(self.kernel.fs.files)}")
        print(f"Processes: {len(self.kernel.scheduler.processes)}")
        print(f"Services: {self.kernel.services.list()}")
        return True


class ExportCommand(Command):
    name = "export"
    usage = "export [VAR=value]..."
    description = "Set or list shell environment variables."

    def execute(
        self, parts: List[str], input_data=None, capture_output=False, raw_line=None
    ):
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
    usage = "alias [name command]"
    description = "Create or list shell command aliases."

    def execute(
        self, parts: List[str], input_data=None, capture_output=False, raw_line=None
    ):
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
        if name in shell.registry.commands and name not in shell.aliases:
            print(f"Warning: alias '{name}' overrides existing command")
        shell.aliases[name] = value
        print(f"Alias {name}='{value}'")
        return True


class UnaliasCommand(Command):
    name = "unalias"
    usage = "unalias <name>"
    description = "Remove a shell alias."

    def execute(
        self,
        parts: List[str],
        input_data=None,
        capture_output=False,
        raw_line=None,
    ):
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
    usage = "history"
    description = "Show the shell command history."

    def execute(
        self,
        parts: List[str],
        input_data=None,
        capture_output=False,
        raw_line=None,
    ):
        shell = self.kernel.shell
        for index, entry in enumerate(shell.history, 1):
            print(f"{index}  {entry}")
        return True


class UptimeCommand(Command):
    name = "uptime"
    usage = "uptime"
    description = "Show system uptime."

    def execute(
        self,
        parts: List[str],
        input_data=None,
        capture_output=False,
        raw_line=None,
    ):
        import time

        uptime_seconds = int(time.time() - self.kernel.boot_time)
        hours = uptime_seconds // 3600
        minutes = (uptime_seconds % 3600) // 60
        seconds = uptime_seconds % 60
        out = f"uptime: {hours:02d}:{minutes:02d}:{seconds:02d} ({uptime_seconds}s)"
        if capture_output:
            return out
        print(out)
        return True


class DateCommand(Command):
    name = "date"
    usage = "date"
    description = "Show current date and time."

    def execute(
        self,
        parts: List[str],
        input_data=None,
        capture_output=False,
        raw_line=None,
    ):
        import time

        out = time.strftime("%a %b %d %H:%M:%S %Z %Y")
        if capture_output:
            return out
        print(out)
        return True


class DfCommand(Command):
    name = "df"
    usage = "df"
    description = "Show virtual disk usage statistics."

    def execute(
        self,
        parts: List[str],
        input_data=None,
        capture_output=False,
        raw_line=None,
    ):
        fs = self.kernel.fs
        num_files = len(fs.files)
        num_dirs = len(fs.dirs)
        total_bytes = sum(len(content) for content in fs.files.values())
        out = (
            f"Filesystem      Directories       Files        Used (Bytes)\n"
            f"virtualfs       {num_dirs:<17} {num_files:<12} {total_bytes}"
        )
        if capture_output:
            return out
        print(out)
        return True


class FreeCommand(Command):
    name = "free"
    usage = "free"
    description = "Show mock memory usage statistics."

    def execute(
        self,
        parts: List[str],
        input_data=None,
        capture_output=False,
        raw_line=None,
    ):
        out = (
            "              total        used        free      "
            "shared  buff/cache   available\n"
            "Mem:        8192000     2048000     4096000           "
            "0     2048000     6144000\n"
            "Swap:       2048000      512000     1536000"
        )
        if capture_output:
            return out
        print(out)
        return True


class SleepCommand(Command):
    name = "sleep"
    usage = "sleep <seconds>"
    description = "Delay execution for a specified number of seconds."

    def execute(
        self, parts: List[str], input_data=None, capture_output=False, raw_line=None
    ):
        if len(parts) < 2:
            print("Usage: sleep <seconds>")
            return False
        try:
            seconds = float(parts[1])
        except ValueError:
            print("Usage: sleep <seconds>")
            return False

        import threading
        import time

        current_name = threading.current_thread().name
        stop_event = None
        if current_name.startswith("process-"):
            try:
                pid = int(current_name.split("-")[1])
                stop_event = self.kernel.scheduler._stop_events.get(pid)
            except (ValueError, IndexError):
                pass

        start = time.time()
        while time.time() - start < seconds:
            if stop_event and stop_event.is_set():
                break
            time.sleep(0.05)
        return True


class WhichCommand(Command):
    name = "which"
    usage = "which <command>"
    description = "Locate a command in the shell command registry or active aliases."

    def execute(
        self, parts: List[str], input_data=None, capture_output=False, raw_line=None
    ):
        if len(parts) < 2:
            print("Usage: which <command>")
            return False
        cmd_name = parts[1]
        shell = self.kernel.shell

        # Check aliases first
        if cmd_name in shell.aliases:
            out = f"{cmd_name}: aliased to {shell.aliases[cmd_name]}"
            if capture_output:
                return out
            print(out)
            return True

        # Check commands registry
        if cmd_name in shell.registry.commands:
            handler = shell.registry.commands[cmd_name]
            out = f"{cmd_name}: shell built-in command ({handler.__class__.__name__})"
            if capture_output:
                return out
            print(out)
            return True

        out = f"{cmd_name}: not found"
        if capture_output:
            return out
        print(out)
        return False


class EnvCommand(Command):
    name = "env"
    aliases = ["printenv"]
    usage = "env"
    description = "List all active environment variables."

    def execute(
        self, parts: List[str], input_data=None, capture_output=False, raw_line=None
    ):
        shell = self.kernel.shell
        out = "\n".join(f"{name}={value}" for name, value in shell.env.items())
        if capture_output:
            return out
        if out:
            print(out)
        return True


class ClearCommand(Command):
    name = "clear"
    usage = "clear"
    description = "Clear the terminal screen."

    def execute(
        self, parts: List[str], input_data=None, capture_output=False, raw_line=None
    ):
        out = "\033[H\033[2J"
        if capture_output:
            return out
        print(out, end="")
        return True


class CrontabCommand(Command):
    name = "crontab"
    usage = "crontab [-l | -r | <file>]"
    description = "List, remove, or install a crontab schedule file."

    def execute(
        self,
        parts: List[str],
        input_data=None,
        capture_output=False,
        raw_line=None,
    ):
        if len(parts) < 2:
            print("Usage: crontab [-l | -r | <file>]")
            return False

        action = parts[1]
        crontab_path = "/etc/crontab"

        if action == "-l":
            if not self.kernel.fs.exists(crontab_path):
                print("crontab: no crontab for current user")
                return False
            try:
                content = self.kernel.fs.read(crontab_path)
                if capture_output:
                    return content
                print(content, end="" if content.endswith("\n") else "\n")
                return True
            except Exception as exc:
                print(f"crontab: error reading crontab: {exc}")
                return False

        elif action == "-r":
            if not self.kernel.fs.exists(crontab_path):
                print("crontab: no crontab to remove")
                return False
            try:
                self.kernel.fs.delete(crontab_path)
                return True
            except Exception as exc:
                print(f"crontab: error removing crontab: {exc}")
                return False

        else:
            file_path = self.resolve_path(action)
            if not self.kernel.fs.exists(file_path):
                print(f"crontab: {action}: No such file or directory")
                return False
            if self.kernel.fs.is_dir(file_path):
                print(f"crontab: {action}: Is a directory")
                return False
            try:
                content = self.kernel.fs.read(file_path)
                self.kernel.fs.write(crontab_path, content)
                return True
            except Exception as exc:
                print(f"crontab: error installing crontab: {exc}")
                return False


def register_system_commands(registry):
    registry.register(HelpCommand(registry.kernel))
    registry.register(InfoCommand(registry.kernel))
    registry.register(ExportCommand(registry.kernel))
    registry.register(AliasCommand(registry.kernel))
    registry.register(UnaliasCommand(registry.kernel))
    registry.register(HistoryCommand(registry.kernel))
    registry.register(UptimeCommand(registry.kernel))
    registry.register(DateCommand(registry.kernel))
    registry.register(DfCommand(registry.kernel))
    registry.register(FreeCommand(registry.kernel))
    registry.register(SleepCommand(registry.kernel))
    registry.register(WhichCommand(registry.kernel))
    registry.register(EnvCommand(registry.kernel))
    registry.register(ClearCommand(registry.kernel))
    registry.register(CrontabCommand(registry.kernel))
