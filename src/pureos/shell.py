"""Tiny interactive shell for v2-PureOS."""

from .commands import CommandRegistry


class Shell:
    def __init__(self, kernel):
        self.kernel = kernel
        self.prompt = kernel.config.get("shell_prompt", "v2-pureos> ")
        self.registry = CommandRegistry(kernel)

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
