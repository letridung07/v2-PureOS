from typing import List

from .base import Command


class FileCommand(Command):
    def _resolve_path(
        self,
        path: str,
        is_dir: bool = False,
        allow_dir: bool = False,
    ) -> str:
        return self.kernel.shell.resolve_path(path, is_dir=is_dir, allow_dir=allow_dir)


class GrepCommand(FileCommand):
    name = "grep"
    usage = "grep <pattern> [path]"
    description = "Search file content for lines containing a pattern."

    def execute(
        self, parts: List[str], input_data=None, capture_output=False, raw_line=None
    ):
        if len(parts) < 2:
            print("Usage: grep <pattern> [path]")
            return False
        pattern = parts[1]
        if len(parts) > 2:
            path = self._resolve_path(parts[2])
            try:
                content = self.kernel.fs.read(path)
            except PermissionError as exc:
                print(str(exc))
                return False
            if content is None:
                print(f"{parts[2]}: not found")
                return False
        else:
            content = input_data or ""
        matches = [line for line in content.splitlines() if pattern in line]
        output = "\n".join(matches)
        if capture_output:
            return output
        if output:
            print(output)
        return True


class CatCommand(FileCommand):
    name = "cat"
    usage = "cat <path>"
    description = "Show file contents or pipe input through the shell."

    def execute(
        self, parts: List[str], input_data=None, capture_output=False, raw_line=None
    ):
        if len(parts) < 2:
            if input_data is None:
                print("Usage: cat <path>")
                return False
            content = input_data
        else:
            path = self._resolve_path(parts[1])
            try:
                content = self.kernel.fs.read(path)
            except PermissionError as exc:
                print(str(exc))
                return False
            if content is None:
                print(f"{parts[1]}: not found")
                return False
        if capture_output:
            return content
        print(content)
        return True


class WriteCommand(FileCommand):
    name = "write"
    usage = "write <path> <content>"
    description = "Write text to a file, creating it if necessary."

    def execute(
        self, parts: List[str], input_data=None, capture_output=False, raw_line=None
    ):
        if len(parts) < 3:
            print("Usage: write <path> <content>")
            return False
        path = self._resolve_path(parts[1])
        content = " ".join(parts[2:])
        try:
            self.kernel.fs.write(path, content)
            print(f"Wrote {len(content)} bytes to {parts[1]}")
            return True
        except (ValueError, PermissionError) as exc:
            print(str(exc))
            return False


class AppendCommand(FileCommand):
    name = "append"
    usage = "append <path> <content>"
    description = "Append text to the end of a file."

    def execute(
        self, parts: List[str], input_data=None, capture_output=False, raw_line=None
    ):
        if len(parts) < 3:
            print("Usage: append <path> <content>")
            return False
        path = self._resolve_path(parts[1])
        content = " ".join(parts[2:])
        try:
            self.kernel.fs.append(path, content)
            print(f"Appended {len(content)} bytes to {parts[1]}")
            return True
        except (ValueError, PermissionError) as exc:
            print(str(exc))
            return False


class EchoCommand(FileCommand):
    name = "echo"
    usage = "echo [text] [> path]"
    description = "Print text or redirect it to a file."

    def execute(
        self, parts: List[str], input_data=None, capture_output=False, raw_line=None
    ):
        if len(parts) < 2:
            if input_data is not None:
                if capture_output:
                    return input_data
                print(input_data)
                return True
            print()
            return True

        tokens = parts[1:]
        operator = None
        target = None
        content_tokens = []
        for index, token in enumerate(tokens):
            if token == ">>" or token == ">":
                operator = token
                target = tokens[index + 1] if index + 1 < len(tokens) else None
                content_tokens = tokens[:index]
                break
            if token.startswith(">>") and " " not in token:
                operator = ">>"
                target = token[2:]
                content_tokens = tokens[:index]
                break
            if token.startswith(">") and " " not in token:
                operator = ">"
                target = token[1:]
                content_tokens = tokens[:index]
                break
            if token.endswith(">>") and " " not in token:
                operator = ">>"
                target = tokens[index + 1] if index + 1 < len(tokens) else None
                content_tokens = tokens[:index] + [token[:-2]]
                break
            if token.endswith(">") and " " not in token:
                operator = ">"
                target = tokens[index + 1] if index + 1 < len(tokens) else None
                content_tokens = tokens[:index] + [token[:-1]]
                break
            if ">>" in token and " " not in token:
                idx = token.find(">>")
                operator = ">>"
                content_tokens = tokens[:index] + ([token[:idx]] if idx else [])
                target = token[idx + 2 :]
                break
            if ">" in token and " " not in token:
                idx = token.find(">")
                operator = ">"
                content_tokens = tokens[:index] + ([token[:idx]] if idx else [])
                target = token[idx + 1 :]
                break
        if operator:
            if target is None or target == "":
                print("Usage: echo <text> > <path>")
                return False
            content = " ".join(content_tokens)
            try:
                if operator == ">>":
                    self.kernel.fs.append(self._resolve_path(target), content)
                else:
                    self.kernel.fs.write(self._resolve_path(target), content)
                print(f"Wrote {len(content)} bytes to {target}")
                return True
            except (ValueError, PermissionError) as exc:
                print(str(exc))
                return False

        line = " ".join(tokens)
        if capture_output:
            return line
        print(line)
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


class LsCommand(FileCommand):
    name = "ls"
    usage = "ls [-l] [path]"
    description = "List files and directories in the virtual filesystem."

    def execute(
        self, parts: List[str], input_data=None, capture_output=False, raw_line=None
    ):
        long_listing = False
        path_arg = None
        for arg in parts[1:]:
            if arg == "-l":
                long_listing = True
            elif path_arg is None:
                path_arg = arg
        if path_arg:
            prefix = self._resolve_path(path_arg, allow_dir=True)
        else:
            prefix = self.kernel.shell.cwd
        if not self.kernel.fs.exists(prefix):
            print(f"{path_arg}: not found")
            return False
        try:
            entries = self.kernel.fs.list(prefix)
        except PermissionError as exc:
            print(str(exc))
            return False
        if long_listing:
            if self.kernel.fs.is_file(prefix):
                entries = [prefix]
            for p in entries:
                info = self.kernel.fs.stat(p)
                if info is None:
                    continue
                print(f"{info['mode_str']} {info['size']:>5} {info['path']}")
        else:
            for p in entries:
                print(p)
        return True


class PwdCommand(FileCommand):
    name = "pwd"
    usage = "pwd"
    description = "Print the current working directory."

    def execute(
        self, parts: List[str], input_data=None, capture_output=False, raw_line=None
    ):
        print(self.kernel.shell.cwd)
        return True


class CdCommand(FileCommand):
    name = "cd"
    usage = "cd <path>"
    description = "Change the current working directory."

    def execute(
        self, parts: List[str], input_data=None, capture_output=False, raw_line=None
    ):
        if len(parts) < 2:
            print("Usage: cd <path>")
            return False
        path = self._resolve_path(parts[1], is_dir=True)
        if not self.kernel.fs.exists(path) or not self.kernel.fs.is_dir(path):
            print(f"{parts[1]}: not found")
            return False
        self.kernel.shell.cwd = path
        return True


class FindCommand(FileCommand):
    name = "find"
    usage = "find [path]"
    description = "Recursively list files and directories from a path."

    def execute(
        self, parts: List[str], input_data=None, capture_output=False, raw_line=None
    ):
        if len(parts) > 1:
            path = self._resolve_path(parts[1], allow_dir=True)
        else:
            path = self.kernel.shell.cwd
        if not self.kernel.fs.exists(path):
            print(f"{parts[1] if len(parts) > 1 else path}: not found")
            return False
        if self.kernel.fs.is_dir(path):
            try:
                print(path)
                for p in self.kernel.fs.find(path):
                    print(p)
            except PermissionError as exc:
                print(str(exc))
                return False
        else:
            print(path)
        return True


class MkdirCommand(FileCommand):
    name = "mkdir"
    usage = "mkdir <path>"
    description = "Create a directory in the virtual filesystem."

    def execute(
        self, parts: List[str], input_data=None, capture_output=False, raw_line=None
    ):
        if len(parts) < 2:
            print("Usage: mkdir <path>")
            return False
        dirpath = self._resolve_path(parts[1], is_dir=True)
        try:
            self.kernel.fs.mkdir(dirpath)
            print(f"Created directory {parts[1]}")
            return True
        except (ValueError, PermissionError) as exc:
            print(str(exc))
            return False


class TouchCommand(FileCommand):
    name = "touch"
    usage = "touch <path>"
    description = "Create or update a file timestamp in the virtual filesystem."

    def execute(
        self, parts: List[str], input_data=None, capture_output=False, raw_line=None
    ):
        if len(parts) < 2:
            print("Usage: touch <path>")
            return False
        path = self._resolve_path(parts[1])
        if not self.kernel.fs.exists(path):
            try:
                self.kernel.fs.write(path, "")
                print(f"Created file {parts[1]}")
                return True
            except (ValueError, PermissionError) as exc:
                print(str(exc))
                return False
        print(f"Touched {parts[1]}")
        return True


class RmCommand(FileCommand):
    name = "rm"
    usage = "rm <path>"
    description = "Remove a file or directory entry from the virtual filesystem."

    def execute(
        self, parts: List[str], input_data=None, capture_output=False, raw_line=None
    ):
        if len(parts) < 2:
            print("Usage: rm <path>")
            return False
        path = self._resolve_path(parts[1], allow_dir=True)
        if self.kernel.fs.exists(path):
            try:
                self.kernel.fs.delete(path)
                print(f"Removed {parts[1]}")
                return True
            except PermissionError as exc:
                print(str(exc))
                return False
        print(f"{parts[1]}: not found")
        return False


class RmdirCommand(FileCommand):
    name = "rmdir"
    usage = "rmdir <path>"
    description = "Remove an empty directory from the virtual filesystem."

    def execute(
        self, parts: List[str], input_data=None, capture_output=False, raw_line=None
    ):
        if len(parts) < 2:
            print("Usage: rmdir <path>")
            return False
        path = self._resolve_path(parts[1], is_dir=True)
        if path == "/":
            print("Cannot remove root directory")
            return False
        if not self.kernel.fs.exists(path) or not self.kernel.fs.is_dir(path):
            print(f"{parts[1]}: not found")
            return False
        if self.kernel.fs.list(path):
            print("Directory not empty")
            return False
        try:
            self.kernel.fs.delete(path)
            print(f"Removed directory {parts[1]}")
            return True
        except PermissionError as exc:
            print(str(exc))
            return False


class MvCommand(FileCommand):
    name = "mv"
    usage = "mv <src> <dst>"
    description = "Move or rename a file or directory."

    def execute(
        self, parts: List[str], input_data=None, capture_output=False, raw_line=None
    ):
        if len(parts) < 3:
            print("Usage: mv <src> <dst>")
            return False
        src = self._resolve_path(parts[1], allow_dir=True)
        dst = self._resolve_path(parts[2], allow_dir=True)
        if not self.kernel.fs.exists(src):
            print(f"{parts[1]}: not found")
            return False
        try:
            self.kernel.fs.rename(src, dst)
            print(f"Moved {parts[1]} -> {parts[2]}")
            return True
        except PermissionError as exc:
            print(str(exc))
            return False


class CpCommand(FileCommand):
    name = "cp"
    usage = "cp <src> <dst>"
    description = "Copy a file or directory."

    def execute(
        self, parts: List[str], input_data=None, capture_output=False, raw_line=None
    ):
        if len(parts) < 3:
            print("Usage: cp <src> <dst>")
            return False
        src = self._resolve_path(parts[1], allow_dir=True)
        dst = self._resolve_path(parts[2], allow_dir=True)
        if not self.kernel.fs.exists(src):
            print(f"{parts[1]}: not found")
            return False
        try:
            self.kernel.fs.copy(src, dst)
            print(f"Copied {parts[1]} -> {parts[2]}")
            return True
        except PermissionError as exc:
            print(str(exc))
            return False


class ChmodCommand(FileCommand):
    name = "chmod"
    usage = "chmod <mode> <path>"
    description = "Change file or directory permission bits."

    def execute(
        self, parts: List[str], input_data=None, capture_output=False, raw_line=None
    ):
        if len(parts) < 3:
            print("Usage: chmod <mode> <path>")
            return False
        try:
            mode = int(parts[1], 8)
        except ValueError:
            print("Usage: chmod <mode> <path>")
            return False
        path = self._resolve_path(parts[2], allow_dir=True)
        try:
            self.kernel.fs.chmod(path, mode)
            print(f"Mode set to {oct(mode)} for {parts[2]}")
            return True
        except FileNotFoundError:
            print(f"{parts[2]}: not found")
            return False


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
            result = self.kernel.shell.execute(line)
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


def register_fs_commands(registry):
    registry.register(GrepCommand(registry.kernel))
    registry.register(CatCommand(registry.kernel))
    registry.register(WriteCommand(registry.kernel))
    registry.register(AppendCommand(registry.kernel))
    registry.register(EchoCommand(registry.kernel))
    registry.register(FormatCommand(registry.kernel))
    registry.register(LsCommand(registry.kernel))
    registry.register(PwdCommand(registry.kernel))
    registry.register(CdCommand(registry.kernel))
    registry.register(FindCommand(registry.kernel))
    registry.register(MkdirCommand(registry.kernel))
    registry.register(TouchCommand(registry.kernel))
    registry.register(RmCommand(registry.kernel))
    registry.register(RmdirCommand(registry.kernel))
    registry.register(MvCommand(registry.kernel))
    registry.register(CpCommand(registry.kernel))
    registry.register(ChmodCommand(registry.kernel))
    registry.register(StatCommand(registry.kernel))
    registry.register(SourceCommand(registry.kernel))
    registry.register(HeadTailCommand(registry.kernel))
