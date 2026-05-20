from typing import List
from .base import FileCommand


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
            prefix = self.resolve_path(path_arg, allow_dir=True)
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

        output = []
        if long_listing:
            if self.kernel.fs.is_file(prefix):
                entries = [prefix]
            for p in entries:
                info = self.kernel.fs.stat(p)
                if info is None:
                    continue
                output.append(f"{info['mode_str']} {info['size']:>5} {info['path']}")
        else:
            output = entries

        return self.emit("\n".join(output), capture_output)


class PwdCommand(FileCommand):
    name = "pwd"
    usage = "pwd"
    description = "Print the current working directory."

    def execute(
        self, parts: List[str], input_data=None, capture_output=False, raw_line=None
    ):
        return self.emit(self.kernel.shell.cwd, capture_output)


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
        path = self.resolve_path(parts[1], is_dir=True)
        if not self.kernel.fs.exists(path) or not self.kernel.fs.is_dir(path):
            print(f"{parts[1]}: not found")
            return False
        self.kernel.shell.cwd = path
        return True


class CatCommand(FileCommand):
    name = "cat"
    usage = "cat <path>"
    description = "Show file contents or pipe input through the shell."

    def execute(
        self, parts: List[str], input_data=None, capture_output=False, raw_line=None
    ):
        content = self.read_input(parts, input_data)
        if content is None:
            return False
        return self.emit(content, capture_output)


class EchoCommand(FileCommand):
    name = "echo"
    usage = "echo [-n] [-e] [text] [> path]"
    description = "Print text or redirect it to a file."

    def execute(
        self, parts: List[str], input_data=None, capture_output=False, raw_line=None
    ):
        no_newline = False
        expand_escapes = False
        remaining = []
        for p in parts[1:]:
            if p == "-n":
                no_newline = True
            elif p == "-e":
                expand_escapes = True
            else:
                remaining.append(p)

        if not remaining:
            if input_data is not None:
                content = input_data
            else:
                content = ""
        else:
            content = " ".join(remaining)

        if expand_escapes:
            # Basic escape expansion for \n, \t, \\
            content = (
                content.replace("\\n", "\n").replace("\\t", "\t").replace("\\\\", "\\")
            )

        if not no_newline:
            content += "\n"

        if capture_output:
            return content

        print(content, end="")
        return True
