from typing import Dict, Set, Optional


class FSState:
    def __init__(self, backing_path: Optional[str] = None):
        self.backing_path = backing_path
        self.files: Dict[str, str] = {}
        self.dirs: Set[str] = {"/"}
        self.modes: Dict[str, int] = {"/": 0o755}
        self.owners: Dict[str, int] = {"/": 0}
        self.groups: Dict[str, int] = {"/": 0}
        # path -> target path (for symlinks)
        self.symlinks: Dict[str, str] = {}
        # path -> inode number
        self.inodes: Dict[str, int] = {"/": 1}
        self._inode_counter: int = 2
        # paths with sticky bit set
        self.sticky_bits: Set[str] = {"/tmp/"}

    def next_inode(self) -> int:
        ino = self._inode_counter
        self._inode_counter += 1
        return ino

    def has_content(self) -> bool:
        return bool(self.files or len(self.dirs) > 1)
