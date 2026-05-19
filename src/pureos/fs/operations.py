from typing import List, Optional, Dict
import os
from .state import FSState
from .path import PathResolver
from .permissions import FSPermissions
from .persistence import FSPersistence


class FSOperations:
    def __init__(
        self, state: FSState, permissions: FSPermissions, persistence: FSPersistence
    ):
        self.state = state
        self.permissions = permissions
        self.persistence = persistence

    def format(self):
        """Reset filesystem to initial state."""
        self.state.files.clear()
        self.state.dirs = {"/", "/etc/"}
        self.state.modes = {
            "/": 0o755,
            "/etc/": 0o755,
            "/etc/motd": 0o644,
            "/etc/pureosrc": 0o644,
        }
        self.state.files["/etc/motd"] = "Welcome to v2-PureOS"
        self.state.files["/etc/pureosrc"] = (
            "alias ll ls -l\n" "alias la ls\n" "alias grep grep -i\n"
        )
        self.persistence.save_if_needed()

    def mkdir(self, path: str, parents: bool = True):
        path = PathResolver.normalize_path(path, is_dir=True)
        if path in self.state.files:
            raise ValueError(f"Cannot create directory, a file exists at {path}")
        self.permissions.ensure_parent_writable(path)
        if parents:
            PathResolver.ensure_dir_parents(self.state, path)
        self.state.dirs.add(path)
        self.state.modes.setdefault(path, 0o755)
        self.persistence.save_if_needed()

    def write(self, path: str, content: str):
        normalized = PathResolver.normalize_path(path)
        if (
            normalized.endswith("/")
            or normalized in self.state.dirs
            or normalized + "/" in self.state.dirs
        ):
            raise ValueError("Cannot write to a directory path")
        if normalized in self.state.files:
            self.permissions.ensure_writable_file(normalized)
        else:
            self.permissions.ensure_parent_writable(normalized)
        PathResolver.ensure_dir_parents(self.state, normalized)
        self.state.files[normalized] = content
        self.state.modes.setdefault(normalized, 0o644)
        self.persistence.save_if_needed()

    def append(self, path: str, content: str):
        normalized = PathResolver.normalize_path(path)
        if (
            normalized.endswith("/")
            or normalized in self.state.dirs
            or normalized + "/" in self.state.dirs
        ):
            raise ValueError("Cannot append to a directory path")
        if normalized in self.state.files:
            self.permissions.ensure_writable_file(normalized)
        else:
            self.permissions.ensure_parent_writable(normalized)
        PathResolver.ensure_dir_parents(self.state, normalized)
        self.state.files[normalized] = self.state.files.get(normalized, "") + content
        self.state.modes.setdefault(normalized, 0o644)
        self.persistence.save_if_needed()

    def read(self, path: str) -> Optional[str]:
        normalized = PathResolver.normalize_path(path, allow_dir=True)
        if normalized.endswith("/") or normalized + "/" in self.state.dirs:
            return None
        self.permissions.ensure_readable_file(normalized)
        return self.state.files.get(normalized)

    def read_lines(self, path: str) -> Optional[List[str]]:
        content = self.read(path)
        if content is None:
            return None
        return content.splitlines()

    def list(self, prefix: str = "/", recursive: bool = False) -> List[str]:
        if recursive:
            return self.find(prefix)
        normalized = PathResolver.normalize_path(prefix, allow_dir=True)
        if normalized in self.state.files:
            return [normalized]
        if normalized != "/" and not normalized.endswith("/"):
            normalized = normalized + "/"
        self.permissions.ensure_readable_dir(normalized)
        result = []
        for d in self.state.dirs:
            if d == normalized:
                continue
            if d.startswith(normalized):
                remainder = d[len(normalized) :]
                if remainder and "/" not in remainder.rstrip("/"):
                    result.append(d)
        for f in self.state.files:
            if f.startswith(normalized):
                remainder = f[len(normalized) :]
                if remainder and "/" not in remainder:
                    result.append(f)
        return sorted(result)

    def find(self, prefix: str = "/") -> List[str]:
        normalized = PathResolver.normalize_path(prefix, allow_dir=True)
        if normalized in self.state.files:
            return [normalized]
        if normalized != "/" and not normalized.endswith("/"):
            normalized = normalized + "/"
        self.permissions.ensure_readable_dir(normalized)
        result = []
        for d in sorted(self.state.dirs):
            if d.startswith(normalized) and d != normalized:
                result.append(d)
        for f in sorted(self.state.files):
            if f.startswith(normalized):
                result.append(f)
        return result

    def exists(self, path: str) -> bool:
        normalized = PathResolver.normalize_path(path, allow_dir=True)
        return (
            normalized in self.state.files
            or normalized in self.state.dirs
            or normalized + "/" in self.state.dirs
        )

    def is_dir(self, path: str) -> bool:
        normalized = PathResolver.normalize_path(path, allow_dir=True)
        return normalized in self.state.dirs or normalized + "/" in self.state.dirs

    def is_file(self, path: str) -> bool:
        normalized = PathResolver.normalize_path(path, allow_dir=True)
        return normalized in self.state.files

    def stat(self, path: str) -> Optional[Dict[str, object]]:
        normalized = PathResolver.normalize_path(path, allow_dir=True)
        if normalized in self.state.files:
            mode = self.state.modes.get(normalized, 0o644)
            return {
                "path": normalized,
                "type": "file",
                "mode": mode,
                "mode_str": self.permissions.format_mode(mode, False),
                "size": len(self.state.files[normalized]),
            }
        dir_path = normalized if normalized.endswith("/") else normalized + "/"
        if dir_path in self.state.dirs:
            mode = self.state.modes.get(dir_path, 0o755)
            return {
                "path": dir_path,
                "type": "dir",
                "mode": mode,
                "mode_str": self.permissions.format_mode(mode, True),
                "size": 0,
            }
        return None

    def chmod(self, path: str, mode: int):
        normalized = PathResolver.normalize_path(path, allow_dir=True)
        if normalized in self.state.files:
            self.state.modes[normalized] = mode
            self.persistence.save_if_needed()
            return
        dir_path = normalized if normalized.endswith("/") else normalized + "/"
        if dir_path in self.state.dirs:
            self.state.modes[dir_path] = mode
            self.persistence.save_if_needed()
            return
        raise FileNotFoundError(path)

    def delete(self, path: str):
        normalized = PathResolver.normalize_path(path, allow_dir=True)
        self.permissions.ensure_parent_writable(normalized)
        if normalized in self.state.files:
            del self.state.files[normalized]
            self.state.modes.pop(normalized, None)
            self.persistence.save_if_needed()
            return
        if (
            normalized not in self.state.dirs
            and normalized + "/" not in self.state.dirs
        ):
            return
        if normalized not in self.state.dirs:
            normalized += "/"
        for file_path in list(self.state.files):
            if file_path.startswith(normalized):
                del self.state.files[file_path]
                self.state.modes.pop(file_path, None)
        for dir_path in list(self.state.dirs):
            if dir_path.startswith(normalized):
                self.state.dirs.discard(dir_path)
                self.state.modes.pop(dir_path, None)
        self.state.dirs.discard(normalized)
        self.state.modes.pop(normalized, None)
        self.persistence.save_if_needed()

    def rename(self, src: str, dst: str):
        src = PathResolver.normalize_path(src, allow_dir=True)
        if src in self.state.files:
            self.permissions.ensure_readable_file(src)
            self.permissions.ensure_parent_writable(dst)
            self._rename_file(src, dst)
        elif src in self.state.dirs or src + "/" in self.state.dirs:
            self.permissions.ensure_parent_writable(dst)
            self._rename_dir(src, dst)

    def copy(self, src: str, dst: str):
        src = PathResolver.normalize_path(src, allow_dir=True)
        if src in self.state.files:
            self.permissions.ensure_readable_file(src)
            self.permissions.ensure_parent_writable(dst)
            self._copy_file(src, dst)
        elif src in self.state.dirs or src + "/" in self.state.dirs:
            self.permissions.ensure_parent_writable(dst)
            self._copy_dir(src, dst)

    def _rename_file(self, src: str, dst: str):
        normalized_dst = PathResolver.normalize_path(dst, allow_dir=True)
        if (
            normalized_dst.endswith("/")
            or normalized_dst in self.state.dirs
            or normalized_dst + "/" in self.state.dirs
        ):
            dir_path = PathResolver.normalize_path(normalized_dst, is_dir=True)
            if dir_path not in self.state.dirs:
                self.mkdir(dir_path, parents=True)
            normalized_dst = dir_path + os.path.basename(src.rstrip("/"))
        PathResolver.ensure_dir_parents(self.state, normalized_dst)
        self.state.files[normalized_dst] = self.state.files.pop(src)
        self.state.modes[normalized_dst] = self.state.modes.pop(src, 0o644)
        self.persistence.save_if_needed()

    def _copy_file(self, src: str, dst: str):
        normalized_dst = PathResolver.normalize_path(dst, allow_dir=True)
        if (
            normalized_dst.endswith("/")
            or normalized_dst in self.state.dirs
            or normalized_dst + "/" in self.state.dirs
        ):
            dir_path = PathResolver.normalize_path(normalized_dst, is_dir=True)
            if dir_path not in self.state.dirs:
                self.mkdir(dir_path, parents=True)
            normalized_dst = dir_path + os.path.basename(src.rstrip("/"))
        PathResolver.ensure_dir_parents(self.state, normalized_dst)
        self.state.files[normalized_dst] = self.state.files[src]
        self.state.modes[normalized_dst] = self.state.modes.get(src, 0o644)
        self.persistence.save_if_needed()

    def _rename_dir(self, src: str, dst: str):
        src_dir = PathResolver.normalize_path(src, is_dir=True)
        dst_dir = PathResolver.normalize_path(dst, is_dir=True)
        if dst_dir == src_dir:
            return
        if dst_dir.startswith(src_dir):
            raise ValueError(
                f"Cannot rename directory into its own subdirectory: {dst_dir}"
            )
        self.mkdir(dst_dir, parents=True)
        for directory in sorted(self.state.dirs):
            if directory.startswith(src_dir):
                relative = directory[len(src_dir) :]
                self.state.dirs.add(dst_dir + relative)
                self.state.modes[dst_dir + relative] = self.state.modes.pop(
                    directory, 0o755
                )
                self.state.dirs.discard(directory)
        for file_path in list(self.state.files):
            if file_path.startswith(src_dir):
                relative = file_path[len(src_dir) :]
                self.state.files[dst_dir + relative] = self.state.files.pop(file_path)
                self.state.modes[dst_dir + relative] = self.state.modes.pop(
                    file_path, 0o644
                )
        self.delete(src_dir)
        self.persistence.save_if_needed()

    def _copy_dir(self, src: str, dst: str):
        src_dir = PathResolver.normalize_path(src, is_dir=True)
        dst_dir = PathResolver.normalize_path(dst, is_dir=True)
        if dst_dir == src_dir:
            return
        if dst_dir.startswith(src_dir):
            raise ValueError(
                f"Cannot copy directory into its own subdirectory: {dst_dir}"
            )
        self.mkdir(dst_dir, parents=True)
        for directory in sorted(self.state.dirs):
            if directory.startswith(src_dir):
                relative = directory[len(src_dir) :]
                self.state.dirs.add(dst_dir + relative)
                self.state.modes[dst_dir + relative] = self.state.modes.get(
                    directory, 0o755
                )
        for file_path, content in list(self.state.files.items()):
            if file_path.startswith(src_dir):
                relative = file_path[len(src_dir) :]
                self.state.files[dst_dir + relative] = content
                self.state.modes[dst_dir + relative] = self.state.modes.get(
                    file_path, 0o644
                )
        self.persistence.save_if_needed()
