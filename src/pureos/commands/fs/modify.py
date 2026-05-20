from typing import List
from .base import FileCommand


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
        except PermissionError as exc:
            print(str(exc))
            return False


class LnCommand(FileCommand):
    name = "ln"
    usage = "ln [-s] <target> <link>"
    description = "Create a hard link or symbolic link (-s) to a file."

    def execute(
        self, parts: List[str], input_data=None, capture_output=False, raw_line=None
    ):
        symbolic = "-s" in parts
        args = [p for p in parts[1:] if p != "-s"]
        if len(args) < 2:
            print("Usage: ln [-s] <target> <link>")
            return False
        target = args[0]
        link_path = self._resolve_path(args[1])

        if symbolic:
            try:
                self.kernel.fs.symlink(target, link_path)
                print(f"Symlink created: {args[1]} -> {target}")
                return True
            except (FileExistsError, PermissionError) as exc:
                print(str(exc))
                return False
        else:
            # Hard link: copy inode (same content pointer)
            target_resolved = self._resolve_path(target)
            if not self.kernel.fs.is_file(target_resolved):
                print(f"ln: {target}: not a file or not found")
                return False
            if self.kernel.fs.exists(link_path):
                print(f"ln: failed to create hard link '{args[1]}': File exists")
                return False
            try:
                target_inode = self.kernel.fs.state.inodes.get(target_resolved, 0)
                self.kernel.fs.write(link_path, self.kernel.fs.read(target_resolved))
                # Share the same inode number to simulate hard link
                self.kernel.fs.state.inodes[link_path] = target_inode
                print(f"Hard link created: {args[1]} -> {target}")
                return True
            except (PermissionError, ValueError) as exc:
                print(str(exc))
                return False


class ReadlinkCommand(FileCommand):
    name = "readlink"
    usage = "readlink <path>"
    description = "Print the target of a symbolic link."

    def execute(
        self, parts: List[str], input_data=None, capture_output=False, raw_line=None
    ):
        if len(parts) < 2:
            print("Usage: readlink <path>")
            return False
        path = self._resolve_path(parts[1])
        target = self.kernel.fs.readlink(path)
        if target is None:
            print(f"readlink: {parts[1]}: not a symbolic link")
            return False
        if capture_output:
            return target
        print(target)
        return True


class DuCommand(FileCommand):
    name = "du"
    usage = "du [-h] [path]"
    description = "Show disk usage for a file or directory tree."

    def execute(
        self, parts: List[str], input_data=None, capture_output=False, raw_line=None
    ):
        human = "-h" in parts
        args = [p for p in parts[1:] if not p.startswith("-")]
        path = self._resolve_path(args[0]) if args else self.kernel.shell.cwd

        if not self.kernel.fs.exists(path):
            print(f"du: {parts[1] if len(parts) > 1 else path}: not found")
            return False

        # Walk tree and compute per-entry usage
        lines = []
        total = 0
        if self.kernel.fs.is_dir(path):
            from pureos.fs.path import PathResolver

            dir_path = PathResolver.normalize_path(path, is_dir=True)
            # Collect all sub-directories and their usage
            for f_path, content in sorted(self.kernel.fs.files.items()):
                if f_path.startswith(dir_path):
                    size = len(content)
                    total += size
            lines.append(
                self._format_size(total, human) + "\t" + (args[0] if args else path)
            )
        else:
            total = self.kernel.fs.du(path)
            lines.append(
                self._format_size(total, human) + "\t" + (args[0] if args else path)
            )

        out = "\n".join(lines)
        if capture_output:
            return out
        print(out)
        return True

    def _format_size(self, size: int, human: bool) -> str:
        if not human:
            return str(size)
        for unit in ["B", "K", "M", "G", "T"]:
            if size < 1024:
                return f"{size:.0f}{unit}"
            size /= 1024
        return f"{size:.0f}P"
