from typing import Dict, Set, Optional


class FSState:
    def __init__(self, backing_path: Optional[str] = None):
        self.backing_path = backing_path
        self.files: Dict[str, str] = {}
        self.dirs: Set[str] = {"/"}
        self.modes: Dict[str, int] = {"/": 0o755}
        self.owners: Dict[str, int] = {"/": 0}
        self.groups: Dict[str, int] = {"/": 0}

    def has_content(self) -> bool:
        return bool(self.files or len(self.dirs) > 1)
