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
        line = line.strip()
        if not line:
            return None
        commands = self._parse_command_sequence(line)
        success = True
        for command, separator in commands:
            if separator == "&&" and not success:
                continue
            if separator == "||" and success:
                continue
            result = self.registry.execute(command)
            if result == "exit":
                return "exit"
            success = result is not False
        return None

    def _parse_command_sequence(self, line: str):
        commands = []
        current = []
        quote = None
        separator = None
        index = 0
        while index < len(line):
            char = line[index]
            if quote:
                if char == quote:
                    quote = None
                current.append(char)
                index += 1
                continue
            if char in ('"', "'"):
                quote = char
                current.append(char)
                index += 1
                continue
            if line.startswith("&&", index):
                command = "".join(current).strip()
                if command:
                    commands.append((command, separator))
                separator = "&&"
                current = []
                index += 2
                continue
            if line.startswith("||", index):
                command = "".join(current).strip()
                if command:
                    commands.append((command, separator))
                separator = "||"
                current = []
                index += 2
                continue
            if char == ";":
                command = "".join(current).strip()
                if command:
                    commands.append((command, separator))
                separator = ";"
                current = []
                index += 1
                continue
            current.append(char)
            index += 1
        command = "".join(current).strip()
        if command:
            commands.append((command, separator))
        return commands

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
