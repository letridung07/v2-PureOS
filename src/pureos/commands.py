"""Shell command registry for v2-PureOS."""

from typing import Callable, Dict, List, Optional, Union


class CommandRegistry:
    def __init__(self, kernel):
        self.kernel = kernel
        self.commands: Dict[str, Callable[..., Optional[Union[str, bool]]]] = {}
        self._register_default_commands()

    def execute(
        self,
        line: str,
        input_data: Optional[str] = None,
        capture_output: bool = False,
    ) -> Optional[Union[str, bool]]:
        line = line.strip()
        if not line:
            return None
        if line in ("exit", "quit"):
            return "exit"
        parts = line.split()
        cmd = parts[0]
        handler = self.commands.get(cmd)
        if not handler:
            print("Unknown command:", line)
            return False
        return handler(parts, input_data=input_data, capture_output=capture_output)

    def register(self, name: str, handler: Callable[..., Optional[Union[str, bool]]]):
        self.commands[name] = handler

    def _register_default_commands(self):
        self.register("help", self._cmd_help)
        self.register("info", self._cmd_info)
        self.register("export", self._cmd_export)
        self.register("alias", self._cmd_alias)
        self.register("unalias", self._cmd_unalias)
        self.register("history", self._cmd_history)
        self.register("grep", self._cmd_grep)
        self.register("cat", self._cmd_cat)
        self.register("write", self._cmd_write)
        self.register("append", self._cmd_append)
        self.register("echo", self._cmd_echo)
        self.register("ls", self._cmd_ls)
        self.register("pwd", self._cmd_pwd)
        self.register("cd", self._cmd_cd)
        self.register("find", self._cmd_find)
        self.register("mkdir", self._cmd_mkdir)
        self.register("touch", self._cmd_touch)
        self.register("rm", self._cmd_rm)
        self.register("rmdir", self._cmd_rmdir)
        self.register("mv", self._cmd_mv)
        self.register("cp", self._cmd_cp)
        self.register("chmod", self._cmd_chmod)
        self.register("stat", self._cmd_stat)
        self.register("source", self._cmd_source)
        self.register("head", self._cmd_head_tail)
        self.register("tail", self._cmd_head_tail)
        self.register("ps", self._cmd_ps)
        self.register("services", self._cmd_services)
        self.register("service", self._cmd_service)
        self.register("spawn", self._cmd_spawn)
        self.register("kill", self._cmd_kill)

    def _resolve_path(
        self, path: str, is_dir: bool = False, allow_dir: bool = False
    ) -> str:
        return self.kernel.shell.resolve_path(path, is_dir=is_dir, allow_dir=allow_dir)

    def _cmd_help(
        self,
        parts: List[str],
        input_data: Optional[str] = None,
        capture_output: bool = False,
    ) -> bool:
        print(
            "help, info, export, alias, unalias, history, grep, ls [-l] [prefix], pwd, cd <path>, find [path], ps, services, exit"
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

    def _cmd_info(
        self,
        parts: List[str],
        input_data: Optional[str] = None,
        capture_output: bool = False,
    ) -> bool:
        print("Kernel info:")
        print(f"FS entries: {len(self.kernel.fs.files)}")
        print(f"Processes: {len(self.kernel.scheduler.processes)}")
        print(f"Services: {self.kernel.services.list()}")
        return True

    def _cmd_export(
        self,
        parts: List[str],
        input_data: Optional[str] = None,
        capture_output: bool = False,
    ) -> bool:
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

    def _cmd_alias(
        self,
        parts: List[str],
        input_data: Optional[str] = None,
        capture_output: bool = False,
    ) -> bool:
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

    def _cmd_unalias(
        self,
        parts: List[str],
        input_data: Optional[str] = None,
        capture_output: bool = False,
    ) -> bool:
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

    def _cmd_history(
        self,
        parts: List[str],
        input_data: Optional[str] = None,
        capture_output: bool = False,
    ) -> bool:
        shell = self.kernel.shell
        for index, entry in enumerate(shell.history, 1):
            print(f"{index}  {entry}")
        return True

    def _cmd_grep(
        self,
        parts: List[str],
        input_data: Optional[str] = None,
        capture_output: bool = False,
    ) -> Optional[Union[str, bool]]:
        if len(parts) < 2:
            print("Usage: grep <pattern> [path]")
            return False
        pattern = parts[1]
        if len(parts) > 2:
            path = self._resolve_path(parts[2])
            try:
                content = self.kernel.fs.read(path)
            except PermissionError as exc:
                print(str(exc))
                return False
            if content is None:
                print(f"{parts[2]}: not found")
                return False
        else:
            content = input_data or ""
        matches = [line for line in content.splitlines() if pattern in line]
        output = "\n".join(matches)
        if capture_output:
            return output
        if output:
            print(output)
        return True

    def _cmd_cat(
        self,
        parts: List[str],
        input_data: Optional[str] = None,
        capture_output: bool = False,
    ) -> Optional[Union[str, bool]]:
        if len(parts) < 2:
            if input_data is None:
                print("Usage: cat <path>")
                return False
            content = input_data
        else:
            path = self._resolve_path(parts[1])
            try:
                content = self.kernel.fs.read(path)
            except PermissionError as exc:
                print(str(exc))
                return False
            if content is None:
                print(f"{parts[1]}: not found")
                return False
        if capture_output:
            return content
        print(content)
        return True

    def _cmd_write(
        self,
        parts: List[str],
        input_data: Optional[str] = None,
        capture_output: bool = False,
    ) -> bool:
        if len(parts) < 3:
            print("Usage: write <path> <content>")
            return False
        path = self._resolve_path(parts[1])
        content = " ".join(parts[2:])
        try:
            self.kernel.fs.write(path, content)
            print(f"Wrote {len(content)} bytes to {parts[1]}")
            return True
        except (ValueError, PermissionError) as exc:
            print(str(exc))
            return False

    def _cmd_append(
        self,
        parts: List[str],
        input_data: Optional[str] = None,
        capture_output: bool = False,
    ) -> bool:
        if len(parts) < 3:
            print("Usage: append <path> <content>")
            return False
        path = self._resolve_path(parts[1])
        content = " ".join(parts[2:])
        try:
            self.kernel.fs.append(path, content)
            print(f"Appended {len(content)} bytes to {parts[1]}")
            return True
        except (ValueError, PermissionError) as exc:
            print(str(exc))
            return False

    def _cmd_echo(
        self,
        parts: List[str],
        input_data: Optional[str] = None,
        capture_output: bool = False,
    ) -> Optional[Union[str, bool]]:
        if len(parts) < 2:
            if input_data is not None:
                if capture_output:
                    return input_data
                print(input_data)
                return True
            print()
            return True
        line = " ".join(parts[1:])
        if ">" in line:
            content, path = line.split(">", maxsplit=1)
            content = content.strip()
            path = path.strip()
            try:
                self.kernel.fs.write(self._resolve_path(path), content)
                print(f"Wrote {len(content)} bytes to {path}")
                return True
            except ValueError as exc:
                print(str(exc))
                return False
        if capture_output:
            return line
        print(line)
        return True

    def _cmd_ls(
        self,
        parts: List[str],
        input_data: Optional[str] = None,
        capture_output: bool = False,
    ) -> bool:
        long_listing = False
        path_arg = None
        for arg in parts[1:]:
            if arg == "-l":
                long_listing = True
            elif path_arg is None:
                path_arg = arg
        if path_arg:
            prefix = self._resolve_path(path_arg, allow_dir=True)
        else:
            prefix = self.kernel.shell.cwd
        if not self.kernel.fs.exists(prefix):
            print(f"{path_arg}: not found")
            return False
        try:
            entries = self.kernel.fs.list(prefix)
        except PermissionError as exc:
            print(str(exc))
            return False
        if long_listing:
            if self.kernel.fs.is_file(prefix):
                entries = [prefix]
            for p in entries:
                info = self.kernel.fs.stat(p)
                if info is None:
                    continue
                print(f"{info['mode_str']} {info['size']:>5} {info['path']}")
        else:
            for p in entries:
                print(p)
        return True

    def _cmd_pwd(
        self,
        parts: List[str],
        input_data: Optional[str] = None,
        capture_output: bool = False,
    ) -> bool:
        print(self.kernel.shell.cwd)
        return True

    def _cmd_cd(
        self,
        parts: List[str],
        input_data: Optional[str] = None,
        capture_output: bool = False,
    ) -> bool:
        if len(parts) < 2:
            print("Usage: cd <path>")
            return False
        path = self._resolve_path(parts[1], is_dir=True)
        if not self.kernel.fs.exists(path) or not self.kernel.fs.is_dir(path):
            print(f"{parts[1]}: not found")
            return False
        self.kernel.shell.cwd = path
        return True

    def _cmd_find(
        self,
        parts: List[str],
        input_data: Optional[str] = None,
        capture_output: bool = False,
    ) -> bool:
        if len(parts) > 1:
            path = self._resolve_path(parts[1], allow_dir=True)
        else:
            path = self.kernel.shell.cwd
        if not self.kernel.fs.exists(path):
            print(f"{parts[1] if len(parts) > 1 else path}: not found")
            return False
        if self.kernel.fs.is_dir(path):
            try:
                print(path)
                for p in self.kernel.fs.find(path):
                    print(p)
            except PermissionError as exc:
                print(str(exc))
                return False
        else:
            print(path)
        return True

    def _cmd_mkdir(
        self,
        parts: List[str],
        input_data: Optional[str] = None,
        capture_output: bool = False,
    ) -> bool:
        if len(parts) < 2:
            print("Usage: mkdir <path>")
            return False
        dirpath = self._resolve_path(parts[1], is_dir=True)
        try:
            self.kernel.fs.mkdir(dirpath)
            print(f"Created directory {parts[1]}")
            return True
        except (ValueError, PermissionError) as exc:
            print(str(exc))
            return False

    def _cmd_touch(
        self,
        parts: List[str],
        input_data: Optional[str] = None,
        capture_output: bool = False,
    ) -> bool:
        if len(parts) < 2:
            print("Usage: touch <path>")
            return False
        path = self._resolve_path(parts[1])
        if not self.kernel.fs.exists(path):
            try:
                self.kernel.fs.write(path, "")
                print(f"Created file {parts[1]}")
                return True
            except (ValueError, PermissionError) as exc:
                print(str(exc))
                return False
        print(f"Touched {parts[1]}")
        return True

    def _cmd_rm(
        self,
        parts: List[str],
        input_data: Optional[str] = None,
        capture_output: bool = False,
    ) -> bool:
        if len(parts) < 2:
            print("Usage: rm <path>")
            return False
        path = self._resolve_path(parts[1], allow_dir=True)
        if self.kernel.fs.exists(path):
            try:
                self.kernel.fs.delete(path)
                print(f"Removed {parts[1]}")
                return True
            except PermissionError as exc:
                print(str(exc))
                return False
        print(f"{parts[1]}: not found")
        return False

    def _cmd_rmdir(
        self,
        parts: List[str],
        input_data: Optional[str] = None,
        capture_output: bool = False,
    ) -> bool:
        if len(parts) < 2:
            print("Usage: rmdir <path>")
            return False
        path = self._resolve_path(parts[1], is_dir=True)
        if path == "/":
            print("Cannot remove root directory")
            return False
        if not self.kernel.fs.exists(path) or not self.kernel.fs.is_dir(path):
            print(f"{parts[1]}: not found")
            return False
        if self.kernel.fs.list(path):
            print("Directory not empty")
            return False
        try:
            self.kernel.fs.delete(path)
            print(f"Removed directory {parts[1]}")
            return True
        except PermissionError as exc:
            print(str(exc))
            return False

    def _cmd_mv(
        self,
        parts: List[str],
        input_data: Optional[str] = None,
        capture_output: bool = False,
    ) -> bool:
        if len(parts) < 3:
            print("Usage: mv <src> <dst>")
            return False
        src = self._resolve_path(parts[1], allow_dir=True)
        dst = self._resolve_path(parts[2], allow_dir=True)
        if not self.kernel.fs.exists(src):
            print(f"{parts[1]}: not found")
            return False
        try:
            self.kernel.fs.rename(src, dst)
            print(f"Moved {parts[1]} -> {parts[2]}")
            return True
        except PermissionError as exc:
            print(str(exc))
            return False

    def _cmd_cp(
        self,
        parts: List[str],
        input_data: Optional[str] = None,
        capture_output: bool = False,
    ) -> bool:
        if len(parts) < 3:
            print("Usage: cp <src> <dst>")
            return False
        src = self._resolve_path(parts[1], allow_dir=True)
        dst = self._resolve_path(parts[2], allow_dir=True)
        if not self.kernel.fs.exists(src):
            print(f"{parts[1]}: not found")
            return False
        try:
            self.kernel.fs.copy(src, dst)
            print(f"Copied {parts[1]} -> {parts[2]}")
            return True
        except PermissionError as exc:
            print(str(exc))
            return False

    def _cmd_chmod(
        self,
        parts: List[str],
        input_data: Optional[str] = None,
        capture_output: bool = False,
    ) -> bool:
        if len(parts) < 3:
            print("Usage: chmod <mode> <path>")
            return False
        try:
            mode = int(parts[1], 8)
        except ValueError:
            print("Usage: chmod <mode> <path>")
            return False
        path = self._resolve_path(parts[2], allow_dir=True)
        try:
            self.kernel.fs.chmod(path, mode)
            print(f"Mode set to {oct(mode)} for {parts[2]}")
            return True
        except FileNotFoundError:
            print(f"{parts[2]}: not found")
            return False

    def _cmd_stat(
        self,
        parts: List[str],
        input_data: Optional[str] = None,
        capture_output: bool = False,
    ) -> bool:
        if len(parts) < 2:
            print("Usage: stat <path>")
            return False
        path = self._resolve_path(parts[1], allow_dir=True)
        info = self.kernel.fs.stat(path)
        if info is None:
            print(f"{parts[1]}: not found")
            return False
        print(f"path: {info['path']}")
        print(f"type: {info['type']}")
        print(f"mode: {oct(info['mode'])}")
        print(f"mode_str: {info['mode_str']}")
        print(f"size: {info['size']}")
        return True

    def _cmd_source(
        self,
        parts: List[str],
        input_data: Optional[str] = None,
        capture_output: bool = False,
    ) -> Optional[Union[str, bool]]:
        if len(parts) < 2:
            print("Usage: source <path>")
            return False
        path = self._resolve_path(parts[1])
        try:
            content = self.kernel.fs.read(path)
        except PermissionError as exc:
            print(str(exc))
            return False
        if content is None:
            print(f"{parts[1]}: not found")
            return False
        for line in content.splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            result = self.kernel.shell.execute(line)
            if result == "exit":
                return "exit"
        return True

    def _cmd_head_tail(
        self,
        parts: List[str],
        input_data: Optional[str] = None,
        capture_output: bool = False,
    ) -> Optional[Union[str, bool]]:
        cmd = parts[0]
        n = 10
        if len(parts) > 1 and parts[1] == "-n":
            if len(parts) < 3:
                print("Usage: head|tail [-n N] [path]")
                return False
            try:
                n = int(parts[2])
            except ValueError:
                print("Usage: head|tail [-n N] [path]")
                return False
            if len(parts) > 3:
                path = self._resolve_path(parts[3])
            else:
                path = None
        elif len(parts) > 1:
            path = self._resolve_path(parts[1])
            if len(parts) > 2:
                try:
                    n = int(parts[2])
                except ValueError:
                    print("Usage: head|tail <path> [n]")
                    return False
        else:
            path = None

        if path is None:
            if input_data is None:
                print("Usage: head|tail <path> [n]")
                return False
            lines = input_data.splitlines()
        else:
            try:
                lines = self.kernel.fs.read_lines(path)
            except PermissionError as exc:
                print(str(exc))
                return False
            if lines is None:
                print(f"{parts[1]}: not found")
                return False
        sel = lines[:n] if cmd == "head" else lines[-n:]
        output = "\n".join(sel)
        if capture_output:
            return output
        if output:
            print(output)
        return True

    def _cmd_ps(
        self,
        parts: List[str],
        input_data: Optional[str] = None,
        capture_output: bool = False,
    ) -> bool:
        for p in self.kernel.scheduler.list():
            print(f"{p.pid}\t{p.name}\t{p.status}")
        return True

    def _cmd_services(
        self,
        parts: List[str],
        input_data: Optional[str] = None,
        capture_output: bool = False,
    ) -> bool:
        print(", ".join(self.kernel.services.list()))
        return True

    def _cmd_service(
        self,
        parts: List[str],
        input_data: Optional[str] = None,
        capture_output: bool = False,
    ) -> bool:
        if len(parts) < 3:
            print("Usage: service start|stop|status|restart <name>")
            return False
        action = parts[1]
        name = parts[2]
        if action == "start":
            try:
                self.kernel.services.start(name)
                print(f"Started service {name}")
                return True
            except KeyError:
                print(f"{name}: not registered")
                return False
        elif action == "stop":
            self.kernel.services.stop(name)
            print(f"Stopped service {name}")
            return True
        elif action == "status":
            st = self.kernel.services.status(name)
            if st is None:
                print(f"{name}: not registered")
                return False
            print(f"running={st['alive']}, stoppable={st['stoppable']}")
            return True
        elif action == "restart":
            self.kernel.services.restart(name)
            print(f"Restarted service {name}")
            return True
        print("Unknown service action")
        return False

    def _cmd_spawn(
        self,
        parts: List[str],
        input_data: Optional[str] = None,
        capture_output: bool = False,
    ) -> bool:
        if len(parts) < 2:
            print("Usage: spawn <name>")
            return False
        name = parts[1]
        p = self.kernel.scheduler.spawn(name)
        print(f"Spawned process {p.pid} ({p.name})")
        return True

    def _cmd_kill(
        self,
        parts: List[str],
        input_data: Optional[str] = None,
        capture_output: bool = False,
    ) -> bool:
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
