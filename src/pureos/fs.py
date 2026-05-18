"""Simple virtual filesystem with optional on-disk backing."""

import json
import os
from typing import Dict, Optional, List, Set


class VirtualFS:
    def __init__(self, backing_path: Optional[str] = None):
        self.backing_path = backing_path
        self.files: Dict[str, str] = {}
        self.dirs: Set[str] = {"/"}
        self.modes: Dict[str, int] = {"/": 0o755}
        if backing_path:
            try:
                self._load()
            except Exception:
                self.files = {}
                self.dirs = {"/"}
                self.modes = {"/": 0o755}

    def has_content(self) -> bool:
        return bool(self.files or len(self.dirs) > 1)

    def _has_permission(
        self, path: str, permission: int, allow_dir: bool = False
    ) -> bool:
        normalized = self._normalize_path(path, allow_dir=allow_dir)
        if normalized in self.files:
            mode = self.modes.get(normalized, 0o644)
            return bool(mode & permission)
        dir_path = normalized if normalized.endswith("/") else normalized + "/"
        if dir_path in self.dirs:
            mode = self.modes.get(dir_path, 0o755)
            return bool(mode & permission)
        return False

    def _ensure_parent_writable(self, path: str):
        parent = self._parent_dir(path)
        if parent.rstrip("/") in self.files:
            raise PermissionError(f"Permission denied: {path}")
        while parent not in self.dirs and parent != "/":
            parent = self._parent_dir(parent)
            if parent.rstrip("/") in self.files:
                raise PermissionError(f"Permission denied: {path}")
        if not self._has_permission(
            parent, 0o200, allow_dir=True
        ) or not self._has_permission(parent, 0o100, allow_dir=True):
            raise PermissionError(f"Permission denied: {path}")

    def _ensure_writable_file(self, path: str):
        if path in self.files and not self._has_permission(path, 0o200):
            raise PermissionError(f"Permission denied: {path}")

    def _ensure_readable_file(self, path: str):
        if path in self.files and not self._has_permission(path, 0o400):
            raise PermissionError(f"Permission denied: {path}")

    def _ensure_readable_dir(self, path: str):
        if not self._has_permission(
            path, 0o400, allow_dir=True
        ) or not self._has_permission(path, 0o100, allow_dir=True):
            raise PermissionError(f"Permission denied: {path}")

    def format(self):
        """Reset filesystem to initial state."""
        self.files.clear()
        self.dirs = {"/", "/etc/"}
        self.modes = {"/": 0o755, "/etc/": 0o755, "/etc/motd": 0o644}
        self.files["/etc/motd"] = "Welcome to v2-PureOS"
        self._save_if_needed()

    def mkdir(self, path: str, parents: bool = True):
        path = self._normalize_path(path, is_dir=True)
        if path in self.files:
            raise ValueError(f"Cannot create directory, a file exists at {path}")
        self._ensure_parent_writable(path)
        if parents:
            self._ensure_dir_parents(path)
        self.dirs.add(path)
        self.modes.setdefault(path, 0o755)
        self._save_if_needed()

    def write(self, path: str, content: str):
        normalized = self._normalize_path(path)
        if (
            normalized.endswith("/")
            or normalized in self.dirs
            or normalized + "/" in self.dirs
        ):
            raise ValueError("Cannot write to a directory path")
        if normalized in self.files:
            self._ensure_writable_file(normalized)
        else:
            self._ensure_parent_writable(normalized)
        self._ensure_dir_parents(normalized)
        self.files[normalized] = content
        self.modes.setdefault(normalized, 0o644)
        self._save_if_needed()

    def append(self, path: str, content: str):
        normalized = self._normalize_path(path)
        if (
            normalized.endswith("/")
            or normalized in self.dirs
            or normalized + "/" in self.dirs
        ):
            raise ValueError("Cannot append to a directory path")
        if normalized in self.files:
            self._ensure_writable_file(normalized)
        else:
            self._ensure_parent_writable(normalized)
        self._ensure_dir_parents(normalized)
        self.files[normalized] = self.files.get(normalized, "") + content
        self.modes.setdefault(normalized, 0o644)
        self._save_if_needed()

    def read(self, path: str) -> Optional[str]:
        normalized = self._normalize_path(path, allow_dir=True)
        if normalized.endswith("/") or normalized + "/" in self.dirs:
            return None
        self._ensure_readable_file(normalized)
        return self.files.get(normalized)

    def read_lines(self, path: str) -> Optional[List[str]]:
        content = self.read(path)
        if content is None:
            return None
        return content.splitlines()

    def list(self, prefix: str = "/", recursive: bool = False) -> List[str]:
        if recursive:
            return self.find(prefix)
        normalized = self._normalize_path(prefix, allow_dir=True)
        if normalized in self.files:
            return [normalized]
        if normalized != "/" and not normalized.endswith("/"):
            normalized = normalized + "/"
        self._ensure_readable_dir(normalized)
        result = []
        for d in self.dirs:
            if d == normalized:
                continue
            if d.startswith(normalized):
                remainder = d[len(normalized) :]
                if remainder and "/" not in remainder.rstrip("/"):
                    result.append(d)
        for f in self.files:
            if f.startswith(normalized):
                remainder = f[len(normalized) :]
                if remainder and "/" not in remainder:
                    result.append(f)
        return sorted(result)

    def find(self, prefix: str = "/") -> List[str]:
        normalized = self._normalize_path(prefix, allow_dir=True)
        if normalized in self.files:
            return [normalized]
        if normalized != "/" and not normalized.endswith("/"):
            normalized = normalized + "/"
        self._ensure_readable_dir(normalized)
        result = []
        for d in sorted(self.dirs):
            if d.startswith(normalized) and d != normalized:
                result.append(d)
        for f in sorted(self.files):
            if f.startswith(normalized):
                result.append(f)
        return result

    def exists(self, path: str) -> bool:
        normalized = self._normalize_path(path, allow_dir=True)
        return (
            normalized in self.files
            or normalized in self.dirs
            or normalized + "/" in self.dirs
        )

    def is_dir(self, path: str) -> bool:
        normalized = self._normalize_path(path, allow_dir=True)
        return normalized in self.dirs or normalized + "/" in self.dirs

    def is_file(self, path: str) -> bool:
        normalized = self._normalize_path(path, allow_dir=True)
        return normalized in self.files

    def stat(self, path: str) -> Optional[Dict[str, object]]:
        normalized = self._normalize_path(path, allow_dir=True)
        if normalized in self.files:
            mode = self.modes.get(normalized, 0o644)
            return {
                "path": normalized,
                "type": "file",
                "mode": mode,
                "mode_str": self._format_mode(mode, False),
                "size": len(self.files[normalized]),
            }
        dir_path = normalized if normalized.endswith("/") else normalized + "/"
        if dir_path in self.dirs:
            mode = self.modes.get(dir_path, 0o755)
            return {
                "path": dir_path,
                "type": "dir",
                "mode": mode,
                "mode_str": self._format_mode(mode, True),
                "size": 0,
            }
        return None

    def chmod(self, path: str, mode: int):
        normalized = self._normalize_path(path, allow_dir=True)
        if normalized in self.files:
            self.modes[normalized] = mode
            self._save_if_needed()
            return
        dir_path = normalized if normalized.endswith("/") else normalized + "/"
        if dir_path in self.dirs:
            self.modes[dir_path] = mode
            self._save_if_needed()
            return
        raise FileNotFoundError(path)

    def delete(self, path: str):
        normalized = self._normalize_path(path, allow_dir=True)
        self._ensure_parent_writable(normalized)
        if normalized in self.files:
            del self.files[normalized]
            self.modes.pop(normalized, None)
            self._save_if_needed()
            return
        if normalized not in self.dirs and normalized + "/" not in self.dirs:
            return
        if normalized not in self.dirs:
            normalized += "/"
        for file_path in list(self.files):
            if file_path.startswith(normalized):
                del self.files[file_path]
                self.modes.pop(file_path, None)
        for dir_path in list(self.dirs):
            if dir_path.startswith(normalized):
                self.dirs.discard(dir_path)
                self.modes.pop(dir_path, None)
        self.dirs.discard(normalized)
        self.modes.pop(normalized, None)
        self._save_if_needed()

    def rename(self, src: str, dst: str):
        src = self._normalize_path(src, allow_dir=True)
        if src in self.files:
            self._ensure_readable_file(src)
            self._ensure_parent_writable(dst)
            self._rename_file(src, dst)
        elif src in self.dirs or src + "/" in self.dirs:
            self._ensure_parent_writable(dst)
            self._rename_dir(src, dst)

    def copy(self, src: str, dst: str):
        src = self._normalize_path(src, allow_dir=True)
        if src in self.files:
            self._ensure_readable_file(src)
            self._ensure_parent_writable(dst)
            self._copy_file(src, dst)
        elif src in self.dirs or src + "/" in self.dirs:
            self._ensure_parent_writable(dst)
            self._copy_dir(src, dst)

    def _rename_file(self, src: str, dst: str):
        normalized_dst = self._normalize_path(dst, allow_dir=True)
        if (
            normalized_dst.endswith("/")
            or normalized_dst in self.dirs
            or normalized_dst + "/" in self.dirs
        ):
            dir_path = self._normalize_path(normalized_dst, is_dir=True)
            if dir_path not in self.dirs:
                self.mkdir(dir_path, parents=True)
            normalized_dst = dir_path + os.path.basename(src.rstrip("/"))
        self._ensure_dir_parents(normalized_dst)
        self.files[normalized_dst] = self.files.pop(src)
        self.modes[normalized_dst] = self.modes.pop(src, 0o644)
        self._save_if_needed()

    def _copy_file(self, src: str, dst: str):
        normalized_dst = self._normalize_path(dst, allow_dir=True)
        if (
            normalized_dst.endswith("/")
            or normalized_dst in self.dirs
            or normalized_dst + "/" in self.dirs
        ):
            dir_path = self._normalize_path(normalized_dst, is_dir=True)
            if dir_path not in self.dirs:
                self.mkdir(dir_path, parents=True)
            normalized_dst = dir_path + os.path.basename(src.rstrip("/"))
        self._ensure_dir_parents(normalized_dst)
        self.files[normalized_dst] = self.files[src]
        self.modes[normalized_dst] = self.modes.get(src, 0o644)
        self._save_if_needed()

    def _rename_dir(self, src: str, dst: str):
        src_dir = self._normalize_path(src, is_dir=True)
        dst_dir = self._normalize_path(dst, is_dir=True)
        if dst_dir == src_dir:
            return
        self.mkdir(dst_dir, parents=True)
        for directory in sorted(self.dirs):
            if directory.startswith(src_dir):
                relative = directory[len(src_dir) :]
                self.dirs.add(dst_dir + relative)
                self.modes[dst_dir + relative] = self.modes.pop(directory, 0o755)
                self.dirs.discard(directory)
        for file_path in list(self.files):
            if file_path.startswith(src_dir):
                relative = file_path[len(src_dir) :]
                self.files[dst_dir + relative] = self.files.pop(file_path)
                self.modes[dst_dir + relative] = self.modes.pop(file_path, 0o644)
        self.delete(src_dir)
        self._save_if_needed()

    def _copy_dir(self, src: str, dst: str):
        src_dir = self._normalize_path(src, is_dir=True)
        dst_dir = self._normalize_path(dst, is_dir=True)
        if dst_dir == src_dir:
            return
        self.mkdir(dst_dir, parents=True)
        for directory in sorted(self.dirs):
            if directory.startswith(src_dir):
                relative = directory[len(src_dir) :]
                self.dirs.add(dst_dir + relative)
                self.modes[dst_dir + relative] = self.modes.get(directory, 0o755)
        for file_path, content in list(self.files.items()):
            if file_path.startswith(src_dir):
                relative = file_path[len(src_dir) :]
                self.files[dst_dir + relative] = content
                self.modes[dst_dir + relative] = self.modes.get(file_path, 0o644)
        self._save_if_needed()

    def _ensure_dir_parents(self, path: str):
        normalized = self._normalize_path(path, allow_dir=True)
        if not normalized.endswith("/"):
            normalized = self._parent_dir(normalized)
        if normalized.rstrip("/") in self.files:
            raise ValueError(
                f"Cannot create directory under file path {normalized.rstrip('/')}"
            )
        while normalized not in self.dirs:
            if normalized.rstrip("/") in self.files:
                raise ValueError(
                    f"Cannot create directory under file path {normalized.rstrip('/')}"
                )
            self.dirs.add(normalized)
            self.modes.setdefault(normalized, 0o755)
            if normalized == "/":
                break
            normalized = self._parent_dir(normalized)

    def _parent_dir(self, path: str) -> str:
        normalized = self._normalize_path(path, allow_dir=True)
        if normalized == "/":
            return "/"
        stripped = normalized.rstrip("/")
        parent = stripped.rsplit("/", 1)[0]
        if not parent:
            return "/"
        return parent + "/"

    def _format_mode(self, mode: int, is_dir: bool) -> str:
        type_char = "d" if is_dir else "-"
        perms = []
        for bit, char in [
            (0o400, "r"),
            (0o200, "w"),
            (0o100, "x"),
            (0o040, "r"),
            (0o020, "w"),
            (0o010, "x"),
            (0o004, "r"),
            (0o002, "w"),
            (0o001, "x"),
        ]:
            perms.append(char if mode & bit else "-")
        return type_char + "".join(perms)

    def _normalize_path(
        self, path: str, is_dir: bool = False, allow_dir: bool = False
    ) -> str:
        if path is None:
            path = ""
        path = path.replace("\\", "/")
        if path != "/" and path.endswith("/"):
            is_dir = True
        if not path.startswith("/"):
            path = "/" + path
        parts = []
        for segment in path.split("/"):
            if segment in ("", "."):
                continue
            if segment == "..":
                if parts:
                    parts.pop()
                continue
            parts.append(segment)
        normalized = "/" + "/".join(parts)
        if normalized != "/" and (is_dir or allow_dir and path.endswith("/")):
            normalized += "/"
        return normalized

    def _save_if_needed(self):
        if self.backing_path:
            self.save()

    def save(self):
        dirpath = os.path.dirname(self.backing_path)
        if dirpath and not os.path.exists(dirpath):
            os.makedirs(dirpath, exist_ok=True)
        with open(self.backing_path, "w", encoding="utf-8") as f:
            json.dump(
                {
                    "files": self.files,
                    "dirs": sorted(self.dirs),
                    "modes": {path: mode for path, mode in self.modes.items()},
                },
                f,
                indent=2,
            )

    def _load(self):
        if os.path.exists(self.backing_path):
            with open(self.backing_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            self.files = {}
            self.dirs = {"/"}
            self.modes = {"/": 0o755}
            if isinstance(data, dict) and all(
                isinstance(v, str) for v in data.values()
            ):
                for path, content in data.items():
                    normalized = self._normalize_path(path, is_dir=path.endswith("/"))
                    if normalized.endswith("/"):
                        self.dirs.add(normalized)
                        self.modes.setdefault(normalized, 0o755)
                    else:
                        self.files[normalized] = content
                        self.modes.setdefault(normalized, 0o644)
                    self._ensure_dir_parents(normalized)
            else:
                self.files = {
                    self._normalize_path(path): content
                    for path, content in data.get("files", {}).items()
                }
                self.dirs = {
                    self._normalize_path(path, is_dir=True)
                    for path in data.get("dirs", [])
                }
                self.dirs.add("/")
                self.modes = {
                    self._normalize_path(path, allow_dir=True): mode
                    for path, mode in data.get("modes", {}).items()
                }
                self.modes.setdefault("/", 0o755)
                for path in self.files:
                    self._ensure_dir_parents(path)
                    self.modes.setdefault(path, 0o644)
                for path in self.dirs:
                    self.modes.setdefault(path, 0o755)
        else:
            self.files = {}
            self.dirs = {"/"}
            self.modes = {"/": 0o755}
