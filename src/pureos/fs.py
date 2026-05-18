"""Simple virtual filesystem with optional on-disk backing."""

import json
import os
from typing import Dict, Optional, List, Set


class VirtualFS:
    def __init__(self, backing_path: Optional[str] = None):
        self.backing_path = backing_path
        self.files: Dict[str, str] = {}
        self.dirs: Set[str] = {"/"}
        if backing_path:
            try:
                self._load()
            except Exception:
                self.files = {}
                self.dirs = {"/"}

    def has_content(self) -> bool:
        return bool(self.files or len(self.dirs) > 1)

    def format(self):
        """Reset filesystem to initial state."""
        self.files.clear()
        self.dirs = {"/", "/etc/"}
        self.files["/etc/motd"] = "Welcome to v2-PureOS"
        self._save_if_needed()

    def mkdir(self, path: str, parents: bool = True):
        path = self._normalize_path(path, is_dir=True)
        if path in self.files:
            raise ValueError(f"Cannot create directory, a file exists at {path}")
        if parents:
            self._ensure_dir_parents(path)
        self.dirs.add(path)
        self._save_if_needed()

    def write(self, path: str, content: str):
        normalized = self._normalize_path(path)
        if (
            normalized.endswith("/")
            or normalized in self.dirs
            or normalized + "/" in self.dirs
        ):
            raise ValueError("Cannot write to a directory path")
        self._ensure_dir_parents(normalized)
        self.files[normalized] = content
        self._save_if_needed()

    def append(self, path: str, content: str):
        normalized = self._normalize_path(path)
        if (
            normalized.endswith("/")
            or normalized in self.dirs
            or normalized + "/" in self.dirs
        ):
            raise ValueError("Cannot append to a directory path")
        self._ensure_dir_parents(normalized)
        self.files[normalized] = self.files.get(normalized, "") + content
        self._save_if_needed()

    def read(self, path: str) -> Optional[str]:
        normalized = self._normalize_path(path, allow_dir=True)
        if normalized.endswith("/") or normalized + "/" in self.dirs:
            return None
        return self.files.get(normalized)

    def read_lines(self, path: str) -> Optional[List[str]]:
        content = self.read(path)
        if content is None:
            return None
        return content.splitlines()

    def list(self, prefix: str = "/") -> List[str]:
        normalized = self._normalize_path(prefix, allow_dir=True)
        if normalized != "/" and not normalized.endswith("/"):
            if normalized in self.files:
                return [normalized]
            normalized = normalized + "/"
        result = []
        for d in self.dirs:
            if d.startswith(normalized) and d != normalized:
                result.append(d)
        for f in self.files:
            if f.startswith(normalized):
                result.append(f)
        return sorted(result)

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

    def delete(self, path: str):
        normalized = self._normalize_path(path, allow_dir=True)
        if normalized in self.files:
            del self.files[normalized]
            self._save_if_needed()
            return
        if normalized not in self.dirs and normalized + "/" not in self.dirs:
            return
        if normalized not in self.dirs:
            normalized += "/"
        for file_path in list(self.files):
            if file_path.startswith(normalized):
                del self.files[file_path]
        for dir_path in list(self.dirs):
            if dir_path.startswith(normalized):
                self.dirs.discard(dir_path)
        self.dirs.discard(normalized)
        self._save_if_needed()

    def rename(self, src: str, dst: str):
        src = self._normalize_path(src, allow_dir=True)
        if src in self.files:
            self._rename_file(src, dst)
        elif src in self.dirs or src + "/" in self.dirs:
            self._rename_dir(src, dst)

    def copy(self, src: str, dst: str):
        src = self._normalize_path(src, allow_dir=True)
        if src in self.files:
            self._copy_file(src, dst)
        elif src in self.dirs or src + "/" in self.dirs:
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
                self.dirs.discard(directory)
        for file_path in list(self.files):
            if file_path.startswith(src_dir):
                relative = file_path[len(src_dir) :]
                self.files[dst_dir + relative] = self.files.pop(file_path)
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
        for file_path, content in list(self.files.items()):
            if file_path.startswith(src_dir):
                relative = file_path[len(src_dir) :]
                self.files[dst_dir + relative] = content
        self._save_if_needed()

    def _ensure_dir_parents(self, path: str):
        normalized = self._normalize_path(path, allow_dir=True)
        if not normalized.endswith("/"):
            normalized = self._parent_dir(normalized)
        while normalized not in self.dirs:
            self.dirs.add(normalized)
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
            json.dump({"files": self.files, "dirs": sorted(self.dirs)}, f, indent=2)

    def _load(self):
        if os.path.exists(self.backing_path):
            with open(self.backing_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            self.files = {}
            self.dirs = {"/"}
            if isinstance(data, dict) and all(
                isinstance(v, str) for v in data.values()
            ):
                for path, content in data.items():
                    normalized = self._normalize_path(path, is_dir=path.endswith("/"))
                    if normalized.endswith("/"):
                        self.dirs.add(normalized)
                    else:
                        self.files[normalized] = content
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
                for path in self.files:
                    self._ensure_dir_parents(path)
        else:
            self.files = {}
            self.dirs = {"/"}
