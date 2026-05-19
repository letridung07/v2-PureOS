"""Tiny interactive shell for v2-PureOS."""

import re

from .commands import CommandRegistry


class Shell:
    VARIABLE_PATTERN = re.compile(
        r"\$(?:\{(?P<braced>[A-Za-z_][A-Za-z0-9_]*)\}|(?P<plain>[A-Za-z_][A-Za-z0-9_]*))"
    )

    def __init__(self, kernel):
        self.kernel = kernel
        self.cwd = "/"
        self.prompt = kernel.config.shell_prompt
        self.registry = CommandRegistry(kernel)
        self.env = {}
        self.aliases = {}
        self.history = []

    def resolve_path(
        self, path: str, is_dir: bool = False, allow_dir: bool = False
    ) -> str:
        if path is None:
            path = ""
        if path.startswith("/"):
            return self.kernel.fs.normalize_path(
                path, is_dir=is_dir, allow_dir=allow_dir
            )
        base = self.cwd if self.cwd.endswith("/") else self.cwd + "/"
        return self.kernel.fs.normalize_path(
            f"{base}{path}", is_dir=is_dir, allow_dir=allow_dir
        )

    def execute(self, line: str):
        line = line.strip()
        if not line:
            return None
        self.history.append(line)
        commands = self._parse_command_sequence(line)
        success = True
        for command, separator in commands:
            if separator == "&&" and not success:
                continue
            if separator == "||" and success:
                continue
            result = self._execute_pipeline(command)
            if result == "exit":
                return "exit"
            success = result is not False
        return None

    def _execute_pipeline(self, line: str):
        line = self._substitute_env_vars(line)
        stages = self._split_pipeline(line)
        if not stages:
            return None
        input_data = None
        for index, stage in enumerate(stages):
            stage = self._expand_alias(stage)
            capture_output = index < len(stages) - 1
            result = self.registry.execute(
                stage,
                input_data=input_data,
                capture_output=capture_output,
            )
            if result == "exit":
                return "exit"
            if result is False:
                return False
            if capture_output:
                input_data = result if isinstance(result, str) else ""
            else:
                if isinstance(result, str):
                    print(result)
        return True

    def _substitute_env_vars(self, line: str) -> str:
        def replace(match):
            name = match.group("braced") or match.group("plain")
            return str(self.env.get(name, ""))

        return self.VARIABLE_PATTERN.sub(replace, line)

    def _expand_alias(self, line: str) -> str:
        stripped = line.strip()
        if not stripped:
            return line
        parts = stripped.split()
        name = parts[0]
        if name in self.aliases:
            alias_value = self.aliases[name]
            remaining = " ".join(parts[1:])
            return f"{alias_value} {remaining}".strip()
        return line

    def _split_pipeline(self, line: str):
        stages = []
        current = []
        quote = None
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
            if char == "|":
                stage = "".join(current).strip()
                if stage:
                    stages.append(stage)
                current = []
                index += 1
                continue
            current.append(char)
            index += 1
        stage = "".join(current).strip()
        if stage:
            stages.append(stage)
        return stages

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
