import importlib
import inspect
import pkgutil
import threading
from typing import Dict, List, Optional, Sequence, Union, Set

from ..parser import tokenize
from .base import Command, CommandResult


class CommandRegistry:
    def __init__(self, kernel):
        self.kernel = kernel
        self.commands: Dict[str, Command] = {}
        # Track which commands are "built-in" and cannot be overwritten
        self.system_commands: Set[str] = set()
        # Track which commands (and aliases) were loaded from which VFS file
        self.vfs_source_map: Dict[str, List[str]] = {}
        # Track current owner of each command: cmd_name -> file_path (None for system)
        self.owners: Dict[str, Optional[str]] = {}
        self._lock = threading.Lock()

        self._register_default_commands()

        # Mark all initial commands as system commands
        for cmd_name in self.commands.keys():
            self.system_commands.add(cmd_name)
            self.owners[cmd_name] = None

    def load_from_vfs(self, file_path: str) -> bool:
        """Loads and registers commands from a Python file in the VirtualFS."""
        with self._lock:
            if not self.kernel.fs.exists(file_path):
                return False

            # If already loaded, unregister first to avoid orphans
            if file_path in self.vfs_source_map:
                self._unregister_from_vfs_unlocked(file_path)

            try:
                content = self.kernel.fs.read(file_path)
                module_name = file_path.split("/")[-1].replace(".py", "")

                # Strictly restricted namespace
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
                    "getattr": getattr,
                    "setattr": setattr,
                    "hasattr": hasattr,
                    "isinstance": isinstance,
                    "issubclass": issubclass,
                }

                # Filter __builtins__ for safety while allowing class creation
                if isinstance(__builtins__, dict):
                    safe_keys = [
                        "__build_class__",
                        "__name__",
                        "__doc__",
                        "__package__",
                        "__loader__",
                        "__spec__",
                        "__import__",
                    ]
                    safe_builtins = {
                        k: __builtins__[k] for k in safe_keys if k in __builtins__
                    }
                else:
                    safe_builtins = {
                        "__build_class__": getattr(
                            __builtins__, "__build_class__", None
                        )
                    }

                namespace["__builtins__"] = safe_builtins

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
                            # Safety: Prevent overwriting system commands
                            if cmd_name in self.system_commands:
                                print(
                                    "Error: Package cannot overwrite system "
                                    f"command '{cmd_name}'."
                                )
                                continue

                            if cmd_name in self.commands:
                                print(
                                    f"Warning: Package command '{cmd_name}' "
                                    "is overwriting an existing dynamic command."
                                )

                            command_instance = obj(self.kernel)
                            self._register_unlocked(command_instance, owner=file_path)

                            # Track for future unregistration
                            self.vfs_source_map[file_path].append(cmd_name)
                            for alias in getattr(command_instance, "aliases", []):
                                if alias in self.system_commands:
                                    print(
                                        f"Warning: Alias '{alias}' skipped "
                                        "(system command)."
                                    )
                                    continue
                                self.vfs_source_map[file_path].append(alias)
                                self.owners[alias] = file_path

                            registered_any = True

                return registered_any
            except Exception as e:
                print(f"Error loading command from VFS {file_path}: {e}")
                return False

    def unregister_from_vfs(self, file_path: str):
        """Unregisters all commands that were loaded from the specified VFS file."""
        with self._lock:
            self._unregister_from_vfs_unlocked(file_path)

    def _unregister_from_vfs_unlocked(self, file_path: str):
        if file_path in self.vfs_source_map:
            for cmd_name in self.vfs_source_map[file_path]:
                # ONLY delete if this file is the current owner
                if self.owners.get(cmd_name) == file_path:
                    if cmd_name in self.commands:
                        del self.commands[cmd_name]
                    if cmd_name in self.owners:
                        del self.owners[cmd_name]
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

        with self._lock:
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
        with self._lock:
            self._register_unlocked(command)

    def _register_unlocked(self, command: Command, owner: Optional[str] = None):
        self.commands[command.name] = command
        self.owners[command.name] = owner
        for alias in getattr(command, "aliases", []):
            self.commands[alias] = command
            self.owners[alias] = owner

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
                            self._register_unlocked(command_instance)

            except ImportError as e:
                print(f"Error loading command module {module_name}: {e}")
