"""Tiny interactive shell for v2-PureOS."""


class Shell:
    def __init__(self, kernel):
        self.kernel = kernel
        self.prompt = kernel.config.get("shell_prompt", "v2-pureos> ")

    def execute(self, line: str):
        line = line.strip()
        if not line:
            return
        if line in ("exit", "quit"):
            return "exit"
        if line == "help":
            print("help, info, ls [prefix], ps, services, exit")
            print(
                "mkdir <path>, rm <path>, mv <src> <dst>, cp <src> <dst>, touch <path>"
            )
            print("write <path> <content>, echo <text> > <path>")
            print("head <path> [n], tail <path> [n]")
            print("service start|stop|status|restart <name>")
            print("spawn <name>, kill <pid>")
            return

        if line == "info":
            print("Kernel info:")
            print(f"FS entries: {len(self.kernel.fs.files)}")
            print(f"Processes: {len(self.kernel.scheduler.processes)}")
            print(f"Services: {self.kernel.services.list()}")
            return

        if line.startswith("cat "):
            parts = line.split(maxsplit=1)
            path = parts[1]
            content = self.kernel.fs.read(path)
            if content is None:
                print(f"{path}: not found")
            else:
                print(content)
            return

        if line.startswith("write "):
            parts = line.split(maxsplit=2)
            if len(parts) < 3:
                print("Usage: write <path> <content>")
                return
            path = parts[1]
            content = parts[2]
            self.kernel.fs.write(path, content)
            print(f"Wrote {len(content)} bytes to {path}")
            return

        # echo with optional redirect
        if line.startswith("echo "):
            if ">" in line:
                left, right = line.split(">", maxsplit=1)
                content = left[len("echo ") :].strip()
                path = right.strip()
                self.kernel.fs.write(path, content)
                print(f"Wrote {len(content)} bytes to {path}")
            else:
                print(line[len("echo ") :].strip())
            return

        if line.startswith("ls"):
            parts = line.split(maxsplit=1)
            prefix = parts[1] if len(parts) > 1 else "/"
            for p in self.kernel.fs.list(prefix):
                print(p)
            return

        if line.startswith("mkdir "):
            parts = line.split(maxsplit=1)
            path = parts[1]
            dirpath = path if path.endswith("/") else path + "/"
            try:
                self.kernel.fs.mkdir(dirpath)
                print(f"Created directory {dirpath}")
            except ValueError as exc:
                print(str(exc))
            return

        if line.startswith("touch "):
            parts = line.split(maxsplit=1)
            path = parts[1]
            if not self.kernel.fs.exists(path):
                try:
                    self.kernel.fs.write(path, "")
                    print(f"Created file {path}")
                except ValueError as exc:
                    print(str(exc))
            else:
                print(f"Touched {path}")
            return

        if line.startswith("rm "):
            parts = line.split(maxsplit=1)
            path = parts[1]
            if self.kernel.fs.exists(path):
                self.kernel.fs.delete(path)
                print(f"Removed {path}")
            else:
                print(f"{path}: not found")
            return

        if line.startswith("mv "):
            parts = line.split(maxsplit=2)
            if len(parts) < 3:
                print("Usage: mv <src> <dst>")
                return
            src, dst = parts[1], parts[2]
            if not self.kernel.fs.exists(src):
                print(f"{src}: not found")
                return
            self.kernel.fs.rename(src, dst)
            print(f"Moved {src} -> {dst}")
            return

        if line.startswith("cp "):
            parts = line.split(maxsplit=2)
            if len(parts) < 3:
                print("Usage: cp <src> <dst>")
                return
            src, dst = parts[1], parts[2]
            if not self.kernel.fs.exists(src):
                print(f"{src}: not found")
                return
            self.kernel.fs.copy(src, dst)
            print(f"Copied {src} -> {dst}")
            return

        if line.startswith("head ") or line.startswith("tail "):
            parts = line.split()
            cmd = parts[0]
            if len(parts) < 2:
                print("Usage: head|tail <path> [n]")
                return
            path = parts[1]
            n = int(parts[2]) if len(parts) > 2 else 10
            lines = self.kernel.fs.read_lines(path)
            if lines is None:
                print(f"{path}: not found")
                return
            if cmd == "head":
                sel = lines[:n]
            else:
                sel = lines[-n:]
            for line in sel:
                print(line)
            return

        if line == "ps":
            for p in self.kernel.scheduler.list():
                print(f"{p.pid}\t{p.name}\t{p.status}")
            return

        if line.startswith("services"):
            # 'services' or 'services <name>' ?
            parts = line.split(maxsplit=1)
            if len(parts) == 1:
                print(", ".join(self.kernel.services.list()))
            else:
                print(self.kernel.services.list())
            return

        if line.startswith("service "):
            parts = line.split(maxsplit=2)
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
                    print(f"{name}: running={st['alive']}, stoppable={st['stoppable']}")
            elif action == "restart":
                self.kernel.services.restart(name)
                print(f"Restarted service {name}")
            else:
                print("Unknown service action")
            return

        if line.startswith("spawn "):
            parts = line.split(maxsplit=1)
            name = parts[1]
            p = self.kernel.scheduler.spawn(name)
            print(f"Spawned process {p.pid} ({p.name})")
            return

        if line.startswith("kill "):
            parts = line.split(maxsplit=1)
            try:
                pid = int(parts[1])
            except Exception:
                print("Usage: kill <pid>")
                return
            ok = self.kernel.scheduler.kill(pid)
            if ok:
                print(f"Killed process {pid}")
            else:
                print(f"No such process: {pid}")
            return

        print("Unknown command:", line)

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
