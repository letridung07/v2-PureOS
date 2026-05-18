"""Simple virtual filesystem with optional on-disk backing."""

import json
import os
from typing import Dict, Optional, List


class VirtualFS:
    def __init__(self, backing_path: Optional[str] = None):
        self.backing_path = backing_path
        self.files: Dict[str, str] = {}
        if backing_path:
            try:
                self._load()
            except Exception:
                # start fresh if loading fails
                self.files = {}

    def format(self):
        """Reset filesystem to initial state."""
        self.files.clear()
        self.files["/etc/motd"] = "Welcome to v2-PureOS"
        self._save_if_needed()

    def write(self, path: str, content: str):
        self.files[path] = content
        self._save_if_needed()

    def append(self, path: str, content: str):
        self.files[path] = self.files.get(path, "") + content
        self._save_if_needed()

    def read(self, path: str) -> Optional[str]:
        return self.files.get(path)

    def read_lines(self, path: str) -> List[str]:
        return self.files.get(path, "").splitlines()

    def list(self, prefix: str = "/") -> List[str]:
        return sorted(k for k in self.files.keys() if k.startswith(prefix))

    def exists(self, path: str) -> bool:
        return path in self.files

    def delete(self, path: str):
        if path in self.files:
            del self.files[path]
            self._save_if_needed()

    def rename(self, src: str, dst: str):
        if src in self.files:
            self.files[dst] = self.files.pop(src)
            self._save_if_needed()

    def copy(self, src: str, dst: str):
        if src in self.files:
            self.files[dst] = self.files[src]
            self._save_if_needed()

    def _save_if_needed(self):
        if self.backing_path:
            self.save()

    def save(self):
        dirpath = os.path.dirname(self.backing_path)
        if dirpath and not os.path.exists(dirpath):
            os.makedirs(dirpath, exist_ok=True)
        with open(self.backing_path, "w", encoding="utf-8") as f:
            json.dump(self.files, f, indent=2)

    def _load(self):
        if os.path.exists(self.backing_path):
            with open(self.backing_path, "r", encoding="utf-8") as f:
                self.files = json.load(f)
        else:
            self.files = {}
