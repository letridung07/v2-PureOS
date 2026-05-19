from typing import List
from .base import FileCommand


class HeadTailCommand(FileCommand):
    name = "head"  # Shared by both
    aliases = ["tail"]
    usage = "head|tail [-n N] [path]"
    description = "Display first or last lines of a file."

    def execute(
        self, parts: List[str], input_data=None, capture_output=False, raw_line=None
    ):
        cmd = parts[0]
        n = 10
        if len(parts) > 1 and parts[1] == "-n":
            if len(parts) < 3:
                print("Usage: head|tail [-n N] [path]")
                return False
            try:
                n = int(parts[2])
            except ValueError:
                print("Usage: head|tail [-n N] [path]")
                return False
            if len(parts) > 3:
                path = self._resolve_path(parts[3])
            else:
                path = None
        elif len(parts) > 1:
            path = self._resolve_path(parts[1])
            if len(parts) > 2:
                try:
                    n = int(parts[2])
                except ValueError:
                    print("Usage: head|tail <path> [n]")
                    return False
        else:
            path = None

        if path is None:
            if input_data is None:
                print("Usage: head|tail <path> [n]")
                return False
            lines = input_data.splitlines()
        else:
            try:
                lines = self.kernel.fs.read_lines(path)
            except PermissionError as exc:
                print(str(exc))
                return False
            if lines is None:
                print(f"{parts[1]}: not found")
                return False
        sel = lines[:n] if cmd == "head" else lines[-n:]
        output = "\n".join(sel)
        if capture_output:
            return output
        if output:
            print(output)
        return True


class StatCommand(FileCommand):
    name = "stat"
    usage = "stat <path>"
    description = "Display metadata for a path."

    def execute(
        self, parts: List[str], input_data=None, capture_output=False, raw_line=None
    ):
        if len(parts) < 2:
            print("Usage: stat <path>")
            return False
        path = self._resolve_path(parts[1], allow_dir=True)
        info = self.kernel.fs.stat(path)
        if info is None:
            print(f"{parts[1]}: not found")
            return False

        out_lines = []
        for k, v in info.items():
            if k == "mode" and isinstance(v, int):
                out_lines.append(f"{k}: {oct(v)}")
            else:
                out_lines.append(f"{k}: {v}")

        out = "\n".join(out_lines)
        if capture_output:
            return out
        print(out)
        return True


class SourceCommand(FileCommand):
    name = "source"
    usage = "source <path>"
    description = "Execute commands from a file."

    def execute(
        self, parts: List[str], input_data=None, capture_output=False, raw_line=None
    ):
        if len(parts) < 2:
            print("Usage: source <path>")
            return False
        path = self._resolve_path(parts[1])
        content = self.kernel.fs.read(path)
        if content is None:
            print(f"{parts[1]}: not found")
            return False

        for line in content.splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            self.kernel.shell.execute(line)
        return True


class FormatCommand(FileCommand):
    name = "format"
    usage = "format"
    description = "Reset the virtual filesystem to initial state."

    def execute(
        self, parts: List[str], input_data=None, capture_output=False, raw_line=None
    ):
        if len(parts) != 1:
            print("Usage: format")
            return False
        try:
            self.kernel.fs.format()
            # Deep Edge Case: Unregister dynamic commands on format
            if hasattr(self.kernel.shell, "registry"):
                self.kernel.shell.registry.clear_dynamic_commands()
            print("Formatted filesystem")
            return True
        except PermissionError as exc:
            print(str(exc))
            return False
