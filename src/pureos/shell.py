"""Tiny interactive shell for v2-PureOS."""

class Shell:
    def __init__(self, kernel):
        self.kernel = kernel
        self.prompt = kernel.config.get("shell_prompt", "v2-pureos> ")

    def run(self):
        print("Starting v2-PureOS shell (type 'help' for commands)")
        while True:
            try:
                line = input(self.prompt).strip()
            except (EOFError, KeyboardInterrupt):
                print()
                break
            if not line:
                continue
            if line in ("exit", "quit"):
                break
            if line == "help":
                print("help, info, ls [prefix], ps, services, exit")
                continue
            if line == "info":
                print("Kernel info:")
                print(f"FS entries: {len(self.kernel.fs.files)}")
                print(f"Processes: {len(self.kernel.scheduler.processes)}")
                print(f"Services: {self.kernel.services.list()}")
                continue
            if line.startswith("ls"):
                parts = line.split(maxsplit=1)
                prefix = parts[1] if len(parts) > 1 else "/"
                for p in self.kernel.fs.list(prefix):
                    print(p)
                continue
            if line == "ps":
                for p in self.kernel.scheduler.list():
                    print(f"{p.pid}\t{p.name}\t{p.status}")
                continue
            if line == "services":
                print(", ".join(self.kernel.services.list()))
                continue
            print("Unknown command:", line)
