"""Tiny interactive shell for v2-PureOS."""

from .commands import CommandRegistry


class Shell:
    def __init__(self, kernel):
        self.kernel = kernel
        self.cwd = "/"
        self.prompt = kernel.config.get("shell_prompt", "v2-pureos> ")
        self.registry = CommandRegistry(kernel)

    def resolve_path(
        self, path: str, is_dir: bool = False, allow_dir: bool = False
    ) -> str:
        if path is None:
            path = ""
        if path.startswith("/"):
            return self.kernel.fs._normalize_path(
                path, is_dir=is_dir, allow_dir=allow_dir
            )
        base = self.cwd if self.cwd.endswith("/") else self.cwd + "/"
        return self.kernel.fs._normalize_path(
            f"{base}{path}", is_dir=is_dir, allow_dir=allow_dir
        )

    def execute(self, line: str):
        return self.registry.execute(line)

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
