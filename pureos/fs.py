"""Simple in-memory virtual filesystem."""

from typing import Dict

class VirtualFS:
    def __init__(self):
        self.files: Dict[str, str] = {}

    def format(self):
        self.files.clear()
        self.files["/etc/motd"] = "Welcome to v2-PureOS"

    def write(self, path: str, content: str):
        self.files[path] = content

    def read(self, path: str):
        return self.files.get(path)

    def list(self, prefix: str = "/"):
        return sorted(k for k in self.files.keys() if k.startswith(prefix))
