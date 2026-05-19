import importlib
import inspect
import pkgutil
from typing import Dict, Optional, Sequence, Union

from ..parser import tokenize
from .base import Command, CommandResult


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
        # Dynamically load all modules in the commands package
        import pureos.commands

        package = pureos.commands
        for _, module_name, is_pkg in pkgutil.iter_modules(package.__path__):
            if is_pkg or module_name in ("base", "registry"):
                continue

            try:
                module = importlib.import_module(f".{module_name}", package.__name__)
                # Look for register_{module_name}_commands or generic register_commands
                register_func_name = f"register_{module_name}_commands"
                if hasattr(module, register_func_name):
                    func = getattr(module, register_func_name)
                    func(self)
                elif hasattr(module, "register_commands"):
                    func = getattr(module, "register_commands")
                    func(self)
                else:
                    # Scan for Command subclasses and register them directly
                    for name, obj in inspect.getmembers(module):
                        if (
                            inspect.isclass(obj)
                            and issubclass(obj, Command)
                            and obj is not Command
                        ):
                            if not inspect.isabstract(obj):
                                # Skip or auto-assign if class lacks name.
                                # Assuming commands are instantiated later.
                                # Ignore if register function is not found.
                                pass
            except ImportError as e:
                print(f"Error loading command module {module_name}: {e}")
