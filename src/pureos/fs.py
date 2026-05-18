"""Simple virtual filesystem with optional on-disk backing.
"""

import json
import os
from typing import Dict, Optional


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

    def read(self, path: str):
        return self.files.get(path)

    def list(self, prefix: str = "/"):
        return sorted(k for k in self.files.keys() if k.startswith(prefix))

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
