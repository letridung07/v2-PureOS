import importlib
import inspect
import pkgutil
from typing import Dict, List, Optional, Sequence, Union

from ..parser import tokenize
from .base import Command, CommandResult


class CommandRegistry:
    def __init__(self, kernel):
        self.kernel = kernel
        self.commands: Dict[str, Command] = {}
        # Track which commands (and aliases) were loaded from which VFS file
        self.vfs_source_map: Dict[str, List[str]] = {}
        self._register_default_commands()

    def load_from_vfs(self, file_path: str) -> bool:
        """Loads and registers commands from a Python file in the VirtualFS."""
        if not self.kernel.fs.exists(file_path):
            return False

        # If already loaded, unregister first to avoid orphans if names changed
        if file_path in self.vfs_source_map:
            self.unregister_from_vfs(file_path)

        try:
            content = self.kernel.fs.read(file_path)
            module_name = file_path.split("/")[-1].replace(".py", "")

            namespace = {
                "Command": Command,
                "__name__": module_name,
                "__file__": file_path,
                "print": print,
                "len": len,
                "range": range,
                "str": str,
                "int": int,
                "float": float,
                "list": list,
                "dict": dict,
                "set": set,
                "bool": bool,
                "Exception": Exception,
            }

            exec(content, namespace)

            registered_any = False
            self.vfs_source_map[file_path] = []

            for name, obj in namespace.items():
                if (
                    inspect.isclass(obj)
                    and issubclass(obj, Command)
                    and obj is not Command
                    and not inspect.isabstract(obj)
                ):
                    cmd_name = getattr(obj, "name", None)
                    if cmd_name:
                        if cmd_name in self.commands:
                            print(
                                f"Warning: Package command '{cmd_name}' "
                                "is overwriting an existing command."
                            )

                        command_instance = obj(self.kernel)
                        self.register(command_instance)

                        # Track for future unregistration
                        self.vfs_source_map[file_path].append(cmd_name)
                        for alias in getattr(command_instance, "aliases", []):
                            self.vfs_source_map[file_path].append(alias)

                        registered_any = True

            return registered_any
        except Exception as e:
            print(f"Error loading command from VFS {file_path}: {e}")
            return False

    def unregister_from_vfs(self, file_path: str):
        """Unregisters all commands that were loaded from the specified VFS file."""
        if file_path in self.vfs_source_map:
            for cmd_name in self.vfs_source_map[file_path]:
                if cmd_name in self.commands:
                    del self.commands[cmd_name]
            del self.vfs_source_map[file_path]

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
        import pureos.commands

        package = pureos.commands
        for _, module_name, is_pkg in pkgutil.walk_packages(
            package.__path__, package.__name__ + "."
        ):
            if (
                is_pkg
                or module_name.endswith(".base")
                or module_name.endswith(".registry")
            ):
                continue

            try:
                module = importlib.import_module(module_name)

                short_name = module_name.split(".")[-1]
                register_func_name = f"register_{short_name}_commands"
                if hasattr(module, register_func_name):
                    func = getattr(module, register_func_name)
                    func(self)
                elif hasattr(module, "register_commands"):
                    func = getattr(module, "register_commands")
                    func(self)

                for name, obj in inspect.getmembers(module):
                    if (
                        inspect.isclass(obj)
                        and issubclass(obj, Command)
                        and obj is not Command
                        and not inspect.isabstract(obj)
                    ):
                        if "name" in obj.__dict__ and obj.name:
                            command_instance = obj(self.kernel)
                            self.register(command_instance)

            except ImportError as e:
                print(f"Error loading command module {module_name}: {e}")
