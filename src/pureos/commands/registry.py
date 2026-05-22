import importlib
import inspect
import pkgutil
import threading
import sys
import traceback
from typing import Dict, List, Optional, Sequence, Union, Set

from ..parser import tokenize
from .base import Command, CommandResult


class CommandRegistry:
    def __init__(self, kernel):
        self.kernel = kernel
        self.commands: Dict[str, Command] = {}
        # Track which commands are "built-in" and cannot be overwritten
        self.system_commands: Set[str] = set()
        # Track which modules (and their commands) were loaded from which VFS file
        # file_path -> {"module": str, "commands": List[str]}
        self.vfs_source_map: Dict[str, dict] = {}
        # Stack of owners for each command name: cmd_name -> [(owner, instance), ...]
        self.registry_stacks: Dict[str, List[tuple]] = {}
        self._lock = threading.Lock()

        self._register_default_commands()

        # Mark all initial commands as system commands
        self.system_commands = set(self.commands.keys())

    def load_from_vfs(self, file_path: str) -> bool:
        """Loads and registers commands from a Python file in the VirtualFS.

        Uses the VFSImporter to load the file as a module.
        """
        with self._lock:
            if not self.kernel.fs.exists(file_path):
                return False

            # If already loaded, unregister first to avoid orphans
            if file_path in self.vfs_source_map:
                self._unregister_from_vfs_unlocked(file_path)

            try:
                # Determine the module name based on file path
                # e.g. /usr/lib/pureos/packages/mycmd.py -> pureos_vfs.packages.mycmd
                if file_path.startswith("/usr/lib/pureos/packages/"):
                    rel_path = file_path[len("/usr/lib/pureos/packages/") :]
                    mod_name = rel_path.replace(".py", "").replace("/", ".")
                    fullname = f"pureos_vfs.packages.{mod_name}"
                elif file_path.startswith("/usr/lib/python/"):
                    rel_path = file_path[len("/usr/lib/python/") :]
                    mod_name = rel_path.replace(".py", "").replace("/", ".")
                    fullname = f"pureos_vfs.{mod_name}"
                else:
                    # Fallback or error
                    print(
                        f"Error: file {file_path} "
                        "is not in a supported VFS import path."
                    )
                    return False

                # Force reload if already in sys.modules
                if fullname in sys.modules:
                    del sys.modules[fullname]

                module = importlib.import_module(fullname)

                registered_any = False
                self.vfs_source_map[file_path] = {"module": fullname, "commands": []}

                for name, obj in inspect.getmembers(module):
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

                            command_instance = obj(self.kernel)
                            self._register_unlocked(command_instance, owner=file_path)

                            # Track for future unregistration
                            self.vfs_source_map[file_path]["commands"].append(cmd_name)
                            for alias in getattr(command_instance, "aliases", []):
                                if alias in self.system_commands:
                                    continue
                                self.vfs_source_map[file_path]["commands"].append(alias)

                            registered_any = True

                return registered_any
            except Exception as e:
                print(f"Error loading command from VFS {file_path}: {e}")
                traceback.print_exc()
                return False

    def unregister_from_vfs(self, file_path: str):
        """Unregisters all commands that were loaded from the specified VFS file."""
        with self._lock:
            self._unregister_from_vfs_unlocked(file_path)

    def clear_dynamic_commands(self):
        """Unregisters all commands loaded from the VirtualFS."""
        with self._lock:
            for file_path in list(self.vfs_source_map.keys()):
                self._unregister_from_vfs_unlocked(file_path)

    def _unregister_from_vfs_unlocked(self, file_path: str):
        if file_path in self.vfs_source_map:
            source_info = self.vfs_source_map[file_path]
            for name in source_info["commands"]:
                self._pop_from_stack(name, file_path)

            # Clean up sys.modules
            fullname = source_info.get("module")
            if fullname and fullname in sys.modules:
                del sys.modules[fullname]

            del self.vfs_source_map[file_path]

    def _push_to_stack(self, name: str, owner: Optional[str], instance: Command):
        if name not in self.registry_stacks:
            self.registry_stacks[name] = []
        self.registry_stacks[name].append((owner, instance))
        # Update active command to the new top of stack
        self.commands[name] = instance

    def _pop_from_stack(self, name: str, owner: str):
        if name in self.registry_stacks:
            # Filter out entries from this owner
            self.registry_stacks[name] = [
                entry for entry in self.registry_stacks[name] if entry[0] != owner
            ]

            if self.registry_stacks[name]:
                # Revert to the previous top of stack
                _, instance = self.registry_stacks[name][-1]
                self.commands[name] = instance
            else:
                # No more owners, delete command
                if name in self.commands:
                    del self.commands[name]
                del self.registry_stacks[name]

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
            # Try to see if 'cmd' is a file path that can be executed as a script
            if "/" in cmd or cmd.startswith("."):
                shell = getattr(self.kernel, "shell", None)
                if shell:
                    resolved_path = shell.resolve_path(cmd)
                    if self.kernel.fs.exists(resolved_path) and self.kernel.fs.is_file(
                        resolved_path
                    ):
                        try:
                            # Check execute permission
                            self.kernel.fs.permissions.ensure_executable_file(
                                resolved_path
                            )

                            # Handle SUID/SGID for scripts
                            stat = self.kernel.fs.stat(resolved_path)
                            mode = stat.get("mode", 0)
                            file_owner = self.kernel.fs.state.owners.get(
                                resolved_path, 0
                            )
                            file_group = self.kernel.fs.state.groups.get(
                                resolved_path, 0
                            )

                            old_euid = self.kernel.users._effective_uid
                            old_egid = self.kernel.users._effective_gid

                            new_euid = file_owner if (mode & 0o4000) else old_euid
                            new_egid = file_group if (mode & 0o2000) else old_egid

                            self.kernel.users.set_effective_ids(new_euid, new_egid)

                            try:
                                # Run as script (delegating to shell.execute)
                                content = self.kernel.fs.read(resolved_path)
                                if content:
                                    for sline in content.splitlines():
                                        sline = sline.strip()
                                        if not sline or sline.startswith("#"):
                                            continue
                                        shell.execute(sline, add_to_history=False)
                                    return True
                                return True
                            finally:
                                self.kernel.users.set_effective_ids(old_euid, old_egid)
                        except (PermissionError, FileNotFoundError) as exc:
                            print(f"{cmd}: {str(exc)}")
                            return False

            print("Unknown command:", " ".join(parts))
            return False

        # Handle SUID/SGID for dynamic commands
        owner_path = None
        with self._lock:
            stack = self.registry_stacks.get(cmd)
            if stack:
                owner_path, _ = stack[-1]

        if owner_path:
            stat = self.kernel.fs.stat(owner_path)
            if stat:
                mode = stat.get("mode", 0)
                if mode & (0o4000 | 0o2000):
                    file_owner = self.kernel.fs.state.owners.get(owner_path, 0)
                    file_group = self.kernel.fs.state.groups.get(owner_path, 0)

                    old_euid = self.kernel.users._effective_uid
                    old_egid = self.kernel.users._effective_gid

                    new_euid = file_owner if (mode & 0o4000) else old_euid
                    new_egid = file_group if (mode & 0o2000) else old_egid

                    self.kernel.users.set_effective_ids(new_euid, new_egid)
                    try:
                        return self._execute_handler(
                            handler, parts, input_data, capture_output, raw_line
                        )
                    finally:
                        self.kernel.users.set_effective_ids(old_euid, old_egid)

        return self._execute_handler(
            handler, parts, input_data, capture_output, raw_line
        )

    def _execute_handler(
        self,
        handler: Command,
        parts: List[str],
        input_data: Optional[str],
        capture_output: bool,
        raw_line: Optional[str],
    ) -> CommandResult:
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
        self._push_to_stack(command.name, owner, command)
        for alias in getattr(command, "aliases", []):
            self._push_to_stack(alias, owner, command)

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
                        cmd_name = getattr(obj, "name", None)
                        if cmd_name:
                            command_instance = obj(self.kernel)
                            self._register_unlocked(command_instance)

            except ImportError as e:
                print(f"Error loading command module {module_name}: {e}")
