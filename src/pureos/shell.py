"""Tiny interactive shell for v2-PureOS."""

import re
from typing import List, Optional

from .commands import CommandRegistry
from .parser import split_command_sequence, split_pipeline, tokenize, split_redirection


class Shell:
    VARIABLE_PATTERN = re.compile(
        r"\$(?:\{(?P<braced>[A-Za-z_0-9\?]+)\}|(?P<plain>[A-Za-z_][A-Za-z0-9_]*|\?))"
    )

    def __init__(self, kernel):
        self.kernel = kernel
        self.cwd = "/"
        self.env = {"?": "0"}
        self.aliases = {}
        self.history = []
        self._last_exit_code = 0
        # Shell flags: -e (exit-on-error), -x (trace)
        self._flags: dict = {"e": False, "x": False}

    def set_flag(self, flag: str, value: bool):
        if flag in self._flags:
            self._flags[flag] = value

    def get_flag(self, flag: str) -> bool:
        return self._flags.get(flag, False)

    @property
    def registry(self):
        if hasattr(self.kernel, "registry") and self.kernel.registry is not None:
            return self.kernel.registry
        if not hasattr(self, "_registry"):
            self._registry = CommandRegistry(self.kernel)
        return self._registry

    @registry.setter
    def registry(self, value):
        if hasattr(self.kernel, "registry") and self.kernel.registry is not None:
            self.kernel.registry = value
        else:
            self._registry = value

    @property
    def prompt(self) -> str:
        username = "root"
        if (
            self.kernel
            and hasattr(self.kernel, "users")
            and self.kernel.users
            and self.kernel.users.current_user
        ):
            username = self.kernel.users.current_user.username
        exit_suffix = f"[{self._last_exit_code}]" if self._last_exit_code != 0 else ""
        return f"{username}@pureos:{self.cwd}{exit_suffix}> "

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

    def execute(
        self,
        line: str,
        add_to_history: bool = True,
        capture_output: bool = False,
    ):
        line = line.strip()
        if not line:
            return None

        # History recall: !N or !prefix
        if line.startswith("!") and len(line) > 1:
            recall = line[1:]
            recalled = None
            if recall.isdigit():
                idx = int(recall) - 1
                if 0 <= idx < len(self.history):
                    recalled = self.history[idx]
                else:
                    print(f"!{recall}: event not found")
                    self._last_exit_code = 1
                    self.env["?"] = "1"
                    return False
            else:
                # Find last command with this prefix
                for cmd in reversed(self.history):
                    if cmd.startswith(recall):
                        recalled = cmd
                        break
                if recalled is None:
                    print(f"!{recall}: event not found")
                    self._last_exit_code = 1
                    self.env["?"] = "1"
                    return False
            print(recalled)
            return self.execute(
                recalled, add_to_history=add_to_history, capture_output=capture_output
            )

        if add_to_history:
            self.history.append(line)

        if capture_output:
            import contextlib
            import io

            buffer = io.StringIO()
            with contextlib.redirect_stdout(buffer), contextlib.redirect_stderr(buffer):
                self._execute_internal(line)
            return buffer.getvalue().strip()
        else:
            return self._execute_internal(line)

    def _execute_internal(self, line: str):
        commands = split_command_sequence(line)
        success = True
        next_conditional = None
        for command, separator in commands:
            if next_conditional == "&&" and not success:
                next_conditional = separator
                continue
            if next_conditional == "||" and success:
                next_conditional = separator
                continue

            if separator == "&":
                self._execute_background(command)
                success = True
                self.env["?"] = "0"
            else:
                # Trace mode: echo command before executing
                if self._flags.get("x"):
                    print(f"+ {command}")
                result = self._execute_pipeline(command)
                if result == "exit":
                    return "exit"
                success = result is not False
                code = 0 if success else 1
                self._last_exit_code = code
                self.env["?"] = str(code)
                # Exit-on-error mode
                if not success and self._flags.get("e"):
                    return False

            next_conditional = separator
        return success

    def _execute_pipeline(self, line: str, stop_event=None, resume_event=None):
        line = self._substitute_env_vars(line)
        stages = split_pipeline(line)
        if not stages:
            return None

        # If we are in the main shell loop (not a background subshell),
        # wrap the pipeline in a foreground process for SIGINT simulation.
        import threading

        if threading.current_thread().name == "MainThread" and not stop_event:

            def pipeline_runner(stop_event=None, resume_event=None):
                res = self._execute_pipeline_core(stages, stop_event, resume_event)
                if res is False:
                    raise RuntimeError("Pipeline failed")

            p = self.kernel.scheduler.spawn(
                line, target_func=pipeline_runner, is_foreground=True
            )
            try:
                self.kernel.scheduler.wait(p.pid)
            except KeyboardInterrupt:
                print("\n^C")
                self.kernel.scheduler.kill(p.pid, signal=9)
                self._last_exit_code = 130
                self.env["?"] = "130"
                return False

            success = p.status == "completed"
            self._last_exit_code = 0 if success else 1
            self.env["?"] = str(self._last_exit_code)
            return success

        return self._execute_pipeline_core(stages, stop_event, resume_event)

    def _execute_pipeline_core(self, stages, stop_event=None, resume_event=None):
        input_data = None
        for index, stage in enumerate(stages):
            if resume_event:
                resume_event.wait()
            if stop_event and stop_event.is_set():
                return False

            stage, redirect_op, redirect_target, input_op, input_target = (
                split_redirection(stage)
            )
            if input_op:
                if not input_target:
                    print("Syntax error: input redirect target not specified")
                    return False
                in_path = self.resolve_path(input_target)
                try:
                    in_content = self.kernel.fs.read(in_path)
                except PermissionError as exc:
                    print(str(exc))
                    return False
                if in_content is None:
                    print(f"Error: {input_target}: No such file or directory")
                    return False
                input_data = in_content

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

    def _execute_background(self, command: str):
        subshell = Shell(self.kernel)
        subshell.cwd = self.cwd
        subshell.env = self.env.copy()
        subshell.aliases = self.aliases.copy()

        def job_runner(stop_event=None, resume_event=None):
            subshell._execute_pipeline(
                command, stop_event=stop_event, resume_event=resume_event
            )

        p = self.kernel.scheduler.spawn(command, target_func=job_runner)
        print(f"[{p.pid}] running: {command}")

    def completer(self, text: str, state: int) -> Optional[str]:
        try:
            import readline

            buffer = readline.get_line_buffer()
        except ImportError:
            buffer = text

        stripped_buffer = buffer.lstrip()
        words = stripped_buffer.split()
        if not words or (len(words) == 1 and not buffer.endswith(" ")):
            options = [cmd for cmd in self.registry.commands if cmd.startswith(text)]
            if state < len(options):
                return options[state]
            return None

        options = self._complete_path(text)
        if state < len(options):
            return options[state]
        return None

    def _complete_path(self, text: str) -> List[str]:
        search_path = text if text else ""
        if "/" in search_path:
            dir_part, prefix = search_path.rsplit("/", 1)
            if not dir_part:
                dir_to_search = "/"
            else:
                dir_to_search = dir_part
        else:
            dir_to_search = ""
            prefix = search_path

        resolved_dir = self.resolve_path(dir_to_search, allow_dir=True)
        if not self.kernel.fs.exists(resolved_dir) or not self.kernel.fs.is_dir(
            resolved_dir
        ):
            return []

        try:
            entries = self.kernel.fs.list(resolved_dir)
        except PermissionError:
            return []

        matches = []
        for entry in entries:
            basename = entry.rstrip("/").rsplit("/", 1)[-1]
            if basename.startswith(prefix):
                if dir_to_search:
                    completed = f"{dir_to_search}/{basename}"
                else:
                    completed = basename

                if entry.endswith("/") or self.kernel.fs.is_dir(entry):
                    completed += "/"
                matches.append(completed)
        return matches

    def load_history(self):
        history_path = "/etc/history"
        if self.kernel.fs.exists(history_path):
            try:
                content = self.kernel.fs.read(history_path)
                if content:
                    lines = content.splitlines()
                    self.history = lines.copy()
                    try:
                        import readline

                        readline.clear_history()
                        for line in lines:
                            readline.add_history(line)
                    except (ImportError, AttributeError):
                        pass
            except Exception:
                pass

    def save_history(self):
        history_path = "/etc/history"
        try:
            content = "\n".join(self.history)
            self.kernel.fs.write(history_path, content)
        except Exception:
            pass

    def run(self):
        print("Starting v2-PureOS shell (type 'help' for commands)")
        self.load_history()

        rc_path = "/etc/pureosrc"
        if self.kernel.fs.exists(rc_path):
            try:
                content = self.kernel.fs.read(rc_path)
                if content:
                    for line in content.splitlines():
                        line = line.strip()
                        if not line or line.startswith("#"):
                            continue
                        self.execute(line, add_to_history=False)
            except Exception:
                pass

        try:
            import readline

            readline.set_completer(self.completer)
            readline.parse_and_bind("tab: complete")
            readline.set_completer_delims(" \t\n\"'")
        except ImportError:
            pass

        while True:
            try:
                line = input(self.prompt).strip()
            except (EOFError, KeyboardInterrupt):
                print()
                break
            res = self.execute(line)
            if res == "exit":
                break
        self.save_history()
