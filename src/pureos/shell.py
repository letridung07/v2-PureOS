"""Tiny interactive shell for v2-PureOS."""


class Shell:
    def __init__(self, kernel):
        self.kernel = kernel
        self.prompt = kernel.config.get("shell_prompt", "v2-pureos> ")
        self.commands = {
            "help": self._cmd_help,
            "info": self._cmd_info,
            "cat": self._cmd_cat,
            "write": self._cmd_write,
            "append": self._cmd_append,
            "echo": self._cmd_echo,
            "ls": self._cmd_ls,
            "mkdir": self._cmd_mkdir,
            "touch": self._cmd_touch,
            "rm": self._cmd_rm,
            "mv": self._cmd_mv,
            "cp": self._cmd_cp,
            "head": self._cmd_head_tail,
            "tail": self._cmd_head_tail,
            "ps": self._cmd_ps,
            "services": self._cmd_services,
            "service": self._cmd_service,
            "spawn": self._cmd_spawn,
            "kill": self._cmd_kill,
        }

    def execute(self, line: str):
        line = line.strip()
        if not line:
            return
        if line in ("exit", "quit"):
            return "exit"
        parts = line.split()
        cmd = parts[0]
        handler = self.commands.get(cmd)
        if not handler:
            print("Unknown command:", line)
            return
        return handler(parts)

    def _cmd_help(self, parts):
        print("help, info, ls [prefix], ps, services, exit")
        print("mkdir <path>, rm <path>, mv <src> <dst>, cp <src> <dst>, touch <path>")
        print("write <path> <content>, append <path> <content>, echo <text> > <path>")
        print("head <path> [n], tail <path> [n]")
        print("service start|stop|status|restart <name>")
        print("spawn <name>, kill <pid>")

    def _cmd_info(self, parts):
        print("Kernel info:")
        print(f"FS entries: {len(self.kernel.fs.files)}")
        print(f"Processes: {len(self.kernel.scheduler.processes)}")
        print(f"Services: {self.kernel.services.list()}")

    def _cmd_cat(self, parts):
        if len(parts) < 2:
            print("Usage: cat <path>")
            return
        path = parts[1]
        content = self.kernel.fs.read(path)
        if content is None:
            print(f"{path}: not found")
        else:
            print(content)

    def _cmd_write(self, parts):
        if len(parts) < 3:
            print("Usage: write <path> <content>")
            return
        path = parts[1]
        content = " ".join(parts[2:])
        try:
            self.kernel.fs.write(path, content)
            print(f"Wrote {len(content)} bytes to {path}")
        except ValueError as exc:
            print(str(exc))

    def _cmd_append(self, parts):
        if len(parts) < 3:
            print("Usage: append <path> <content>")
            return
        path = parts[1]
        content = " ".join(parts[2:])
        try:
            self.kernel.fs.append(path, content)
            print(f"Appended {len(content)} bytes to {path}")
        except ValueError as exc:
            print(str(exc))

    def _cmd_echo(self, parts):
        if len(parts) < 2:
            print()
            return
        line = " ".join(parts[1:])
        if ">" in line:
            content, path = line.split(">", maxsplit=1)
            content = content.strip()
            path = path.strip()
            try:
                self.kernel.fs.write(path, content)
                print(f"Wrote {len(content)} bytes to {path}")
            except ValueError as exc:
                print(str(exc))
        else:
            print(line)

    def _cmd_ls(self, parts):
        prefix = parts[1] if len(parts) > 1 else "/"
        for p in self.kernel.fs.list(prefix):
            print(p)

    def _cmd_mkdir(self, parts):
        if len(parts) < 2:
            print("Usage: mkdir <path>")
            return
        dirpath = parts[1]
        if not dirpath.endswith("/"):
            dirpath += "/"
        try:
            self.kernel.fs.mkdir(dirpath)
            print(f"Created directory {dirpath}")
        except ValueError as exc:
            print(str(exc))

    def _cmd_touch(self, parts):
        if len(parts) < 2:
            print("Usage: touch <path>")
            return
        path = parts[1]
        if not self.kernel.fs.exists(path):
            try:
                self.kernel.fs.write(path, "")
                print(f"Created file {path}")
            except ValueError as exc:
                print(str(exc))
        else:
            print(f"Touched {path}")

    def _cmd_rm(self, parts):
        if len(parts) < 2:
            print("Usage: rm <path>")
            return
        path = parts[1]
        if self.kernel.fs.exists(path):
            self.kernel.fs.delete(path)
            print(f"Removed {path}")
        else:
            print(f"{path}: not found")

    def _cmd_mv(self, parts):
        if len(parts) < 3:
            print("Usage: mv <src> <dst>")
            return
        src, dst = parts[1], parts[2]
        if not self.kernel.fs.exists(src):
            print(f"{src}: not found")
            return
        self.kernel.fs.rename(src, dst)
        print(f"Moved {src} -> {dst}")

    def _cmd_cp(self, parts):
        if len(parts) < 3:
            print("Usage: cp <src> <dst>")
            return
        src, dst = parts[1], parts[2]
        if not self.kernel.fs.exists(src):
            print(f"{src}: not found")
            return
        self.kernel.fs.copy(src, dst)
        print(f"Copied {src} -> {dst}")

    def _cmd_head_tail(self, parts):
        if len(parts) < 2:
            print("Usage: head|tail <path> [n]")
            return
        cmd = parts[0]
        path = parts[1]
        n = int(parts[2]) if len(parts) > 2 else 10
        lines = self.kernel.fs.read_lines(path)
        if lines is None:
            print(f"{path}: not found")
            return
        sel = lines[:n] if cmd == "head" else lines[-n:]
        for line in sel:
            print(line)

    def _cmd_ps(self, parts):
        for p in self.kernel.scheduler.list():
            print(f"{p.pid}\t{p.name}\t{p.status}")

    def _cmd_services(self, parts):
        print(", ".join(self.kernel.services.list()))

    def _cmd_service(self, parts):
        if len(parts) < 3:
            print("Usage: service start|stop|status|restart <name>")
            return
        action = parts[1]
        name = parts[2]
        if action == "start":
            try:
                self.kernel.services.start(name)
                print(f"Started service {name}")
            except KeyError:
                print(f"{name}: not registered")
        elif action == "stop":
            self.kernel.services.stop(name)
            print(f"Stopped service {name}")
        elif action == "status":
            st = self.kernel.services.status(name)
            if st is None:
                print(f"{name}: not registered")
            else:
                print(f"running={st['alive']}, stoppable={st['stoppable']}")
        elif action == "restart":
            self.kernel.services.restart(name)
            print(f"Restarted service {name}")
        else:
            print("Unknown service action")

    def _cmd_spawn(self, parts):
        if len(parts) < 2:
            print("Usage: spawn <name>")
            return
        name = parts[1]
        p = self.kernel.scheduler.spawn(name)
        print(f"Spawned process {p.pid} ({p.name})")

    def _cmd_kill(self, parts):
        if len(parts) < 2:
            print("Usage: kill <pid>")
            return
        try:
            pid = int(parts[1])
        except ValueError:
            print("Usage: kill <pid>")
            return
        ok = self.kernel.scheduler.kill(pid)
        if ok:
            print(f"Killed process {pid}")
        else:
            print(f"No such process: {pid}")

    def run(self):
        print("Starting v2-PureOS shell (type 'help' for commands)")
        while True:
            try:
                line = input(self.prompt).strip()
            except (EOFError, KeyboardInterrupt):
                print()
                break
            res = self.execute(line)
            if res == "exit":
                break
