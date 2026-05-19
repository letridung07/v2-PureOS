from typing import List
from .base import FileCommand


class StatCommand(FileCommand):
    name = "stat"
    usage = "stat <path>"
    description = "Show metadata for a file or directory."

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
        print(f"path: {info['path']}")
        print(f"type: {info['type']}")
        print(f"mode: {oct(info['mode'])}")
        print(f"mode_str: {info['mode_str']}")
        print(f"size: {info['size']}")
        return True


class SourceCommand(FileCommand):
    name = "source"
    usage = "source <path>"
    description = "Execute commands from a file line by line."

    def execute(
        self, parts: List[str], input_data=None, capture_output=False, raw_line=None
    ):
        if len(parts) < 2:
            print("Usage: source <path>")
            return False
        path = self._resolve_path(parts[1])
        try:
            content = self.kernel.fs.read(path)
        except PermissionError as exc:
            print(str(exc))
            return False
        if content is None:
            print(f"{parts[1]}: not found")
            return False
        for line in content.splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            result = self.kernel.shell.execute(line, add_to_history=False)
            if result == "exit":
                return "exit"
        return True


class HeadTailCommand(FileCommand):
    name = "head"
    aliases = ["tail"]
    usage = "head|tail [-n N] [path]"
    description = "Show the beginning or end of a file or input stream."

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
            print("Formatted filesystem")
            return True
        except PermissionError as exc:
            print(str(exc))
            return False
