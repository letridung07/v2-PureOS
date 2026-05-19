from typing import List
from .base import FileCommand


class GrepCommand(FileCommand):
    name = "grep"
    usage = "grep [options] <pattern> [path]"
    description = "Search file content for lines containing a pattern."

    def execute(
        self, parts: List[str], input_data=None, capture_output=False, raw_line=None
    ):
        ignore_case = False
        invert_match = False
        line_numbers = False

        args = []
        for arg in parts[1:]:
            if arg.startswith("--"):
                if arg == "--ignore-case":
                    ignore_case = True
                elif arg == "--invert-match":
                    invert_match = True
                elif arg == "--line-number":
                    line_numbers = True
                else:
                    print(f"grep: invalid option {arg}")
                    return False
            elif arg.startswith("-") and len(arg) > 1:
                for char in arg[1:]:
                    if char == "i":
                        ignore_case = True
                    elif char == "v":
                        invert_match = True
                    elif char == "n":
                        line_numbers = True
                    else:
                        print(f"grep: invalid option -- {char}")
                        return False
            else:
                args.append(arg)

        if len(args) < 1:
            print("Usage: grep [options] <pattern> [path]")
            return False

        pattern = args[0]
        path = args[1] if len(args) > 1 else None

        if path is not None:
            resolved_path = self._resolve_path(path)
            try:
                content = self.kernel.fs.read(resolved_path)
            except PermissionError as exc:
                print(str(exc))
                return False
            if content is None:
                print(f"grep: {path}: No such file or directory")
                return False
        else:
            content = input_data or ""

        matches = []
        for line_idx, line in enumerate(content.splitlines(), 1):
            match_pattern = pattern
            match_line = line
            if ignore_case:
                match_pattern = pattern.lower()
                match_line = line.lower()

            has_match = match_pattern in match_line
            if invert_match:
                has_match = not has_match

            if has_match:
                if line_numbers:
                    matches.append(f"{line_idx}:{line}")
                else:
                    matches.append(line)

        output = "\n".join(matches)
        if capture_output:
            return output
        if output:
            print(output)
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
