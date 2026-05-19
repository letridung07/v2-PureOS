from typing import Dict, Optional, Sequence, Union

from ..parser import tokenize
from .base import Command, CommandResult
from .fs import register_fs_commands
from .process import register_process_commands
from .service import register_service_commands
from .system import register_system_commands
from .network import register_network_commands


class CommandRegistry:
    def __init__(self, kernel):
        self.kernel = kernel
        self.commands: Dict[str, Command] = {}
        self._register_default_commands()

    def execute(
        self,
        line: Union[str, Sequence[str]],
        input_data: Optional[str] = None,
        capture_output: bool = False,
        raw_line: Optional[str] = None,
    ) -> CommandResult:
        if isinstance(line, str):
            parts = tokenize(line)
            if not parts:
                return None
            if parts[0] in ("exit", "quit"):
                return "exit"
        else:
            parts = list(line)
            if not parts:
                return None
            if parts[0] in ("exit", "quit"):
                return "exit"
        cmd = parts[0]
        handler = self.commands.get(cmd)
        if not handler:
            print("Unknown command:", " ".join(parts))
            return False
        
        if capture_output:
            import io
            import contextlib
            
            f = io.StringIO()
            with contextlib.redirect_stdout(f):
                result = handler.execute(
                    parts,
                    input_data=input_data,
                    capture_output=capture_output,
                    raw_line=raw_line,
                )
            if result is False:
                return False
            if isinstance(result, str):
                return result
            val = f.getvalue()
            if val.endswith("\n"):
                val = val[:-1]
            return val
        else:
            return handler.execute(
                parts,
                input_data=input_data,
                capture_output=capture_output,
                raw_line=raw_line,
            )

    def register(self, command: Command):
        self.commands[command.name] = command
        for alias in getattr(command, "aliases", []):
            self.commands[alias] = command

    def _register_default_commands(self):
        register_system_commands(self)
        register_fs_commands(self)
        register_service_commands(self)
        register_process_commands(self)
        register_network_commands(self)
