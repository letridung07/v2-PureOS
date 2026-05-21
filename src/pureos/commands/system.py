import importlib
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
        for command in self.kernel.registry.commands.values():
            if id(command) in seen:
                continue
            seen.add(id(command))
            commands.append(command)
        commands.sort(key=lambda command: command.name)
        out = ["Available commands:"]
        for command in commands:
            alias_text = ""
            if command.aliases:
                alias_text = f" (aliases: {', '.join(command.aliases)})"
            usage = getattr(command, "usage", command.name) or command.name
            description = getattr(command, "description", "")
            out.append(f"  {usage}{alias_text}")
            if description:
                out.append(f"    {description}")
        out.append("Command chaining: cmd1 ; cmd2 && cmd3 || cmd4")
        return self.emit("\n".join(out), capture_output)


class InfoCommand(Command):
    name = "info"
    usage = "info"
    description = "Show kernel state and loaded components."

    def execute(
        self, parts: List[str], input_data=None, capture_output=False, raw_line=None
    ):
        out = (
            "Kernel info:\n"
            f"FS entries: {len(self.kernel.fs.files)}\n"
            f"Processes: {len(self.kernel.scheduler.processes)}\n"
            f"Services: {self.kernel.services.list()}"
        )
        mem = self.kernel.drivers.drivers.get("memory")
        if mem:
            s = mem.get_stats()
            out += (
                f"\nMemory: {s['used']}K used / {s['total']}K total "
                f"({s['free']}K free)"
            )
        return self.emit(out, capture_output)


class ExportCommand(Command):
    name = "export"
    usage = "export [VAR=value]..."
    description = "Set or list shell environment variables."

    def execute(
        self, parts: List[str], input_data=None, capture_output=False, raw_line=None
    ):
        shell = self.kernel.shell
        if len(parts) == 1:
            out = "\n".join(f"{name}={value}" for name, value in shell.env.items())
            return self.emit(out, capture_output)
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
            out = "\n".join(
                f"alias {name}='{value}'" for name, value in shell.aliases.items()
            )
            return self.emit(out, capture_output)
        if len(parts) < 3:
            print("Usage: alias name command")
            return False
        name = parts[1]
        value = " ".join(parts[2:])
        if name in shell.registry.commands and name not in shell.aliases:
            print(f"Warning: alias '{name}' overrides existing command")
        shell.aliases[name] = value
        return self.emit(f"Alias {name}='{value}'", capture_output)


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
        out = "\n".join(
            f"{index}  {entry}" for index, entry in enumerate(shell.history, 1)
        )
        return self.emit(out, capture_output)


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
        return self.emit(out, capture_output)


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
        return self.emit(out, capture_output)


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
        return self.emit(out, capture_output)


class FreeCommand(Command):
    name = "free"
    usage = "free"
    description = "Show memory usage statistics."

    def execute(
        self,
        parts: List[str],
        input_data=None,
        capture_output=False,
        raw_line=None,
    ):
        mem = self.kernel.drivers.drivers.get("memory")
        if mem:
            s = mem.get_stats()
            out = (
                f"              total        used        free      "
                f"shared  buff/cache   available\n"
                f"Mem:     {s['total']:>10d} {s['used']:>10d} "
                f"{s['free']:>10d}          0 "
                f"{s['cached']:>10d} {s['available']:>10d}\n"
                f"Swap:    {s['swap_total']:>10d} {s['swap_used']:>10d} "
                f"{s['swap_free']:>10d}"
            )
            return self.emit(out, capture_output)
        return self.emit("Memory driver not loaded.", capture_output)


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
        resume_event = None
        if current_name.startswith("process-"):
            try:
                pid = int(current_name.split("-")[1])
                stop_event = self.kernel.scheduler._stop_events.get(pid)
                resume_event = self.kernel.scheduler._resume_events.get(pid)
            except (ValueError, IndexError):
                pass

        start = time.time()
        while time.time() - start < seconds:
            if stop_event and stop_event.is_set():
                break

            # Suspension support
            proc = None
            if current_name.startswith("process-"):
                try:
                    pid = int(current_name.split("-")[1])
                    proc = self.kernel.scheduler.status(pid)
                except Exception:
                    pass

            if proc and proc.status == "suspended" and resume_event:
                resume_event.wait()

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
            return self.emit(out, capture_output)

        # Check commands registry
        if cmd_name in shell.registry.commands:
            handler = shell.registry.commands[cmd_name]
            out = f"{cmd_name}: shell built-in command ({handler.__class__.__name__})"
            return self.emit(out, capture_output)

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
        return self.emit(out, capture_output)


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
                return self.emit(content, capture_output)
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


class DriverCommand(Command):
    name = "driver"
    usage = "driver [list | status [<name>] | load <module> <class> | start <name> | stop <name> | unload <name>]"
    description = "Manage system drivers."

    def execute(
        self, parts: List[str], input_data=None, capture_output=False, raw_line=None
    ):
        if len(parts) < 2:
            print(f"Usage: {self.usage}")
            return False

        subcommand = parts[1]
        dm = self.kernel.drivers

        if subcommand == "list":
            if not dm.drivers:
                return self.emit("No drivers loaded.", capture_output)
            out = ["Loaded drivers:"]
            for name, driver in dm.drivers.items():
                desc = getattr(driver, "description", "")
                state = getattr(driver, "state", "unknown")
                out.append(f"  {name} [{state}] - {desc}")
            return self.emit("\n".join(out), capture_output)

        elif subcommand == "status":
            if len(parts) == 2:
                if not dm.drivers:
                    return self.emit("No drivers loaded.", capture_output)
                out = ["Driver status:"]
                for name, driver in dm.drivers.items():
                    state = getattr(driver, "state", "unknown")
                    out.append(f"  {name}: {state}")
                return self.emit("\n".join(out), capture_output)
            if len(parts) == 3:
                name = parts[2]
                driver = dm.drivers.get(name)
                if not driver:
                    return self.emit(f"Driver {name} is not loaded.", capture_output)
                state = getattr(driver, "state", "unknown")
                return self.emit(f"{name}: {state}", capture_output)
            print("Usage: driver status [<name>]")
            return False

        elif subcommand == "load":
            if len(parts) < 4:
                print("Usage: driver load <module> <class>")
                return False
            mod_name = parts[2]
            cls_name = parts[3]

            try:
                module = importlib.import_module(mod_name)
                driver_class = getattr(module, cls_name)
                dm.load_driver(driver_class)
                return True
            except Exception as e:
                print(f"Error loading driver: {e}")
                return False

        elif subcommand == "start":
            if len(parts) < 3:
                print("Usage: driver start <name>")
                return False
            name = parts[2]
            if not dm.start_driver(name):
                print(f"Failed to start driver: {name}")
                return False
            return True

        elif subcommand == "stop":
            if len(parts) < 3:
                print("Usage: driver stop <name>")
                return False
            name = parts[2]
            if not dm.stop_driver(name):
                print(f"Failed to stop driver: {name}")
                return False
            return True

        elif subcommand == "unload":
            if len(parts) < 3:
                print("Usage: driver unload <name>")
                return False
            name = parts[2]
            dm.unload_driver(name)
            return True

        else:
            print(f"Unknown subcommand: {subcommand}")
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
    registry.register(SetCommand(registry.kernel))
    registry.register(JobsCommand(registry.kernel))
    registry.register(FgCommand(registry.kernel))
    registry.register(TimeCommand(registry.kernel))
    registry.register(DriverCommand(registry.kernel))
    registry.register(DmesgCommand(registry.kernel))


class SetCommand(Command):
    name = "set"
    usage = "set [-e] [-x] [+e] [+x]"
    description = "Set or unset shell options: -e exit-on-error, -x trace commands."

    def execute(
        self, parts: List[str], input_data=None, capture_output=False, raw_line=None
    ):
        shell = self.kernel.shell
        if len(parts) == 1:
            # Print current flags
            out = "\n".join(
                f"-{flag}: {'on' if val else 'off'}"
                for flag, val in shell._flags.items()
            )
            return self.emit(out, capture_output)
        for arg in parts[1:]:
            if arg.startswith("-") and len(arg) == 2 and arg[1].isalpha():
                shell.set_flag(arg[1], True)
            elif arg.startswith("+") and len(arg) == 2 and arg[1].isalpha():
                shell.set_flag(arg[1], False)
            else:
                print(f"set: unknown option: {arg}")
                return False
        return True


class JobsCommand(Command):
    name = "jobs"
    usage = "jobs"
    description = "List active background processes with their status."

    def execute(
        self, parts: List[str], input_data=None, capture_output=False, raw_line=None
    ):
        procs = self.kernel.scheduler.list()
        active_procs = [
            p for p in procs if p.status in ("running", "ready", "suspended")
        ]
        if not active_procs:
            return self.emit("No background jobs.", capture_output)
        lines = []
        for proc in active_procs:
            lines.append(f"[{proc.pid}] {proc.status:<12} {proc.name}")
        return self.emit("\n".join(lines), capture_output)


class FgCommand(Command):
    name = "fg"
    usage = "fg <pid>"
    description = "Bring a background process to the foreground (wait for it)."

    def execute(
        self, parts: List[str], input_data=None, capture_output=False, raw_line=None
    ):
        if len(parts) < 2:
            print("Usage: fg <pid>")
            return False
        try:
            pid = int(parts[1])
        except ValueError:
            print("Usage: fg <pid>")
            return False

        procs = {p.pid: p for p in self.kernel.scheduler.list()}
        if pid not in procs:
            print(f"fg: {pid}: no such job")
            return False
        proc = procs[pid]

        if proc.status == "suspended":
            self.kernel.scheduler.resume(pid)

        out = f"[{pid}] {proc.name}"
        self.emit(out, capture_output)
        proc.thread.join()
        return proc.status != "failed"


class TimeCommand(Command):
    name = "time"
    usage = "time <command> [args...]"
    description = "Measure wall-clock execution time of a shell command."

    def execute(
        self, parts: List[str], input_data=None, capture_output=False, raw_line=None
    ):
        import time as _time

        if len(parts) < 2:
            print("Usage: time <command> [args...]")
            return False
        cmd_line = " ".join(parts[1:])
        start = _time.time()
        result = self.kernel.shell.execute(cmd_line)
        elapsed = _time.time() - start
        timing = f"\nreal\t{elapsed:.3f}s"
        print(timing)
        return result is not False


class DmesgCommand(Command):
    name = "dmesg"
    usage = "dmesg [-c] [-l <level>] [-f]"
    description = "Print or control the kernel/system log ring buffer."

    def execute(
        self, parts: List[str], input_data=None, capture_output=False, raw_line=None
    ):
        syslog = self.kernel.drivers.drivers.get("syslog")
        if not syslog:
            return self.emit("Syslog driver not loaded.", capture_output)

        clear_logs = False
        filter_level = None
        follow = False

        idx = 1
        while idx < len(parts):
            arg = parts[idx]
            if arg == "-c":
                clear_logs = True
            elif arg == "-f":
                follow = True
            elif arg == "-l" and idx + 1 < len(parts):
                filter_level = parts[idx + 1].upper()
                idx += 1
            else:
                print("Usage: dmesg [-c] [-l <level>] [-f]")
                return False
            idx += 1

        if clear_logs:
            syslog.clear()
            return True

        if follow:
            if capture_output:
                print("dmesg: -f not supported in pipes")
                return False

            print("dmesg: starting follow mode (Ctrl+C to stop)")
            last_idx = len(syslog.logs)

            # Print existing logs first
            with syslog._lock:
                logs = list(syslog.logs)
                if filter_level:
                    logs = [e for e in logs if e["levelname"] == filter_level]
                for entry in logs:
                    print(entry["formatted"])

            import time

            try:
                while True:
                    with syslog._lock:
                        num_logs = len(syslog.logs)
                        if num_logs < last_idx:
                            # Logs were cleared, reset pointer
                            last_idx = 0
                            print("dmesg: log buffer cleared")

                        if num_logs > last_idx:
                            new_logs = syslog.logs[last_idx:]
                            for entry in new_logs:
                                if (
                                    not filter_level
                                    or entry["levelname"] == filter_level
                                ):
                                    print(entry["formatted"])
                            last_idx = num_logs
                    time.sleep(0.1)
            except KeyboardInterrupt:
                print()  # Clean newline after ^C
                return True

        with syslog._lock:
            logs = list(syslog.logs)

        if filter_level:
            logs = [entry for entry in logs if entry["levelname"] == filter_level]

        out = "\n".join(entry["formatted"] for entry in logs)
        return self.emit(out, capture_output)
