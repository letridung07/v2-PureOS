"""Tiny interactive shell for v2-PureOS."""

import re
from typing import List

from .commands import CommandRegistry
from .parser import split_command_sequence, split_pipeline, tokenize, split_redirection


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
            stage, redirect_op, redirect_target = split_redirection(stage)
            tokens = self._expand_alias(self._tokenize(stage))
            capture_output = (index < len(stages) - 1) or bool(redirect_op)
            result = self.registry.execute(
                tokens,
                input_data=input_data,
                capture_output=capture_output,
                raw_line=stage,
            )
            if result == "exit":
                return "exit"
            if result is False:
                return False
            
            if redirect_op:
                if not redirect_target:
                    print("Syntax error: redirect target not specified")
                    return False
                target_path = self.resolve_path(redirect_target)
                content = result if isinstance(result, str) else ""
                try:
                    if redirect_op == ">>":
                        self.kernel.fs.append(target_path, content)
                    else:
                        self.kernel.fs.write(target_path, content)
                except (ValueError, PermissionError) as exc:
                    print(str(exc))
                    return False
                if index < len(stages) - 1:
                    input_data = ""
            else:
                if index < len(stages) - 1:
                    input_data = result if isinstance(result, str) else ""
                else:
                    if isinstance(result, str):
                        print(result)
        return True

    def _substitute_env_vars(self, line: str) -> str:
        result = []
        quote = None
        index = 0
        while index < len(line):
            char = line[index]
            if quote is None:
                if char == "'":
                    quote = "'"
                    result.append(char)
                    index += 1
                    continue
                if char == '"':
                    quote = '"'
                    result.append(char)
                    index += 1
                    continue
                if char == "\\" and index + 1 < len(line):
                    result.append(char)
                    result.append(line[index + 1])
                    index += 2
                    continue
                if char == "$":
                    match = self.VARIABLE_PATTERN.match(line, index)
                    if match:
                        name = match.group("braced") or match.group("plain")
                        result.append(str(self.env.get(name, "")))
                        index = match.end()
                        continue
                result.append(char)
                index += 1
                continue
            if quote == "'":
                result.append(char)
                if char == "'":
                    quote = None
                index += 1
                continue
            if quote == '"':
                if char == '"':
                    quote = None
                    result.append(char)
                    index += 1
                    continue
                if char == "\\" and index + 1 < len(line):
                    result.append(line[index + 1])
                    index += 2
                    continue
                if char == "$":
                    match = self.VARIABLE_PATTERN.match(line, index)
                    if match:
                        name = match.group("braced") or match.group("plain")
                        result.append(str(self.env.get(name, "")))
                        index = match.end()
                        continue
                result.append(char)
                index += 1
                continue
        return "".join(result)

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
