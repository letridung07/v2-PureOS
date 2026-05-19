from typing import Dict, List, Optional, Sequence, Union

from .base import Command, CommandResult
from .fs import register_fs_commands
from .process import register_process_commands
from .service import register_service_commands
from .system import register_system_commands


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
    ) -> CommandResult:
        if isinstance(line, str):
            line = line.strip()
            if not line:
                return None
            if line in ("exit", "quit"):
                return "exit"
            parts = line.split()
        else:
            parts = list(line)
            if not parts:
                return None
        cmd = parts[0]
        handler = self.commands.get(cmd)
        if not handler:
            print("Unknown command:", " ".join(parts))
            return False
        return handler.execute(
            parts, input_data=input_data, capture_output=capture_output
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
