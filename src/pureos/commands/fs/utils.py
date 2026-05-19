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


class WcCommand(FileCommand):
    name = "wc"
    usage = "wc [-l] [-w] [-c] [path]"
    description = "Print newline, word, and byte counts for a file or input."

    def execute(
        self, parts: List[str], input_data=None, capture_output=False, raw_line=None
    ):
        show_lines = False
        show_words = False
        show_bytes = False
        path = None
        for arg in parts[1:]:
            if arg == "-l":
                show_lines = True
            elif arg == "-w":
                show_words = True
            elif arg == "-c":
                show_bytes = True
            elif arg.startswith("-"):
                print(f"wc: invalid option -- {arg}")
                return False
            elif path is None:
                path = self._resolve_path(arg)

        if not (show_lines or show_words or show_bytes):
            show_lines = show_words = show_bytes = True

        if path is not None:
            try:
                content = self.kernel.fs.read(path)
            except PermissionError as exc:
                print(str(exc))
                return False
            if content is None:
                print(f"wc: {parts[-1]}: No such file or directory")
                return False
        else:
            content = input_data or ""

        lines_count = len(content.splitlines()) if content else 0
        words_count = len(content.split())
        bytes_count = len(content.encode("utf-8"))

        out_parts = []
        if show_lines:
            out_parts.append(f"{lines_count:>7}")
        if show_words:
            out_parts.append(f"{words_count:>7}")
        if show_bytes:
            out_parts.append(f"{bytes_count:>7}")
        if path is not None:
            out_parts.append(f" {parts[-1]}")

        out = "".join(out_parts)
        if capture_output:
            return out
        print(out)
        return True


class SortCommand(FileCommand):
    name = "sort"
    usage = "sort [-r] [-n] [path]"
    description = "Sort lines of text files or input."

    def execute(
        self, parts: List[str], input_data=None, capture_output=False, raw_line=None
    ):
        reverse = False
        numeric = False
        path = None
        for arg in parts[1:]:
            if arg == "-r":
                reverse = True
            elif arg == "-n":
                numeric = True
            elif arg.startswith("-"):
                print(f"sort: invalid option -- {arg}")
                return False
            elif path is None:
                path = self._resolve_path(arg)

        if path is not None:
            try:
                content = self.kernel.fs.read(path)
            except PermissionError as exc:
                print(str(exc))
                return False
            if content is None:
                print(f"sort: {parts[-1]}: No such file or directory")
                return False
        else:
            content = input_data or ""

        lines = content.splitlines()

        if numeric:

            def sort_key(line):
                import re

                match = re.match(r"^\s*(-?\d+)", line)
                if match:
                    return (0, int(match.group(1)), line)
                return (1, 0, line)

        else:

            def sort_key(x):
                return x

        lines.sort(key=sort_key, reverse=reverse)
        out = "\n".join(lines)
        if capture_output:
            return out
        if out:
            print(out)
        return True


class UniqCommand(FileCommand):
    name = "uniq"
    usage = "uniq [-c] [-d] [-u] [path]"
    description = "Report or omit repeated lines."

    def execute(
        self, parts: List[str], input_data=None, capture_output=False, raw_line=None
    ):
        count = False
        duplicates_only = False
        unique_only = False
        path = None
        for arg in parts[1:]:
            if arg == "-c":
                count = True
            elif arg == "-d":
                duplicates_only = True
            elif arg == "-u":
                unique_only = True
            elif arg.startswith("-"):
                print(f"uniq: invalid option -- {arg}")
                return False
            elif path is None:
                path = self._resolve_path(arg)

        if path is not None:
            try:
                content = self.kernel.fs.read(path)
            except PermissionError as exc:
                print(str(exc))
                return False
            if content is None:
                print(f"uniq: {parts[-1]}: No such file or directory")
                return False
        else:
            content = input_data or ""

        lines = content.splitlines()
        if not lines:
            return True

        grouped = []
        current_line = lines[0]
        current_count = 1
        for line in lines[1:]:
            if line == current_line:
                current_count += 1
            else:
                grouped.append((current_line, current_count))
                current_line = line
                current_count = 1
        grouped.append((current_line, current_count))

        out_lines = []
        for line, c in grouped:
            if duplicates_only and c == 1:
                continue
            if unique_only and c > 1:
                continue

            if count:
                out_lines.append(f"{c:>7} {line}")
            else:
                out_lines.append(line)

        out = "\n".join(out_lines)
        if capture_output:
            return out
        if out:
            print(out)
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
