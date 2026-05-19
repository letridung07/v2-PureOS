"""Tiny interactive shell for v2-PureOS."""

import re
from typing import List

from .commands import CommandRegistry
from .parser import split_command_sequence, split_pipeline, tokenize


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
        commands = split_command_sequence(line)
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
        stages = split_pipeline(line)
        if not stages:
            return None
        input_data = None
        for index, stage in enumerate(stages):
            tokens = self._expand_alias(self._tokenize(stage))
            capture_output = index < len(stages) - 1
            result = self.registry.execute(
                tokens,
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

    def _tokenize(self, line: str) -> List[str]:
        return tokenize(line)

    def _expand_alias(self, tokens: List[str]) -> List[str]:
        if not tokens:
            return tokens
        expanded = tokens
        seen = set()
        depth = 0
        while depth < 10 and expanded and expanded[0] in self.aliases:
            alias_name = expanded[0]
            if alias_name in seen:
                break
            seen.add(alias_name)
            alias_tokens = tokenize(self.aliases[alias_name])
            expanded = alias_tokens + expanded[1:]
            depth += 1
        return expanded

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
