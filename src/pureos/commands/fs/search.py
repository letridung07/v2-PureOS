from typing import List
from .base import FileCommand


class FindCommand(FileCommand):
    name = "find"
    usage = "find [path]"
    description = "Recursively list files and directories from a path."

    def execute(
        self, parts: List[str], input_data=None, capture_output=False, raw_line=None
    ):
        if len(parts) > 1:
            path = self.resolve_path(parts[1], allow_dir=True)
        else:
            path = self.kernel.shell.cwd
        if not self.kernel.fs.exists(path):
            print(f"{parts[1] if len(parts) > 1 else path}: not found")
            return False
        output = [path]
        if self.kernel.fs.is_dir(path):
            try:
                for p in self.kernel.fs.find(path):
                    output.append(p)
            except PermissionError as exc:
                print(str(exc))
                return False

        return self.emit("\n".join(output), capture_output)
