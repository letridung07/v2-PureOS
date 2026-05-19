from .state import FSState
from .path import PathResolver


class FSPermissions:
    def __init__(self, state: FSState):
        self.state = state

    def has_permission(
        self, path: str, permission: int, allow_dir: bool = False
    ) -> bool:
        normalized = PathResolver.normalize_path(path, allow_dir=allow_dir)
        if normalized in self.state.files:
            mode = self.state.modes.get(normalized, 0o644)
            return bool(mode & permission)
        dir_path = normalized if normalized.endswith("/") else normalized + "/"
        if dir_path in self.state.dirs:
            mode = self.state.modes.get(dir_path, 0o755)
            return bool(mode & permission)
        return False

    def ensure_parent_writable(self, path: str):
        parent = PathResolver.parent_dir(path)
        if parent.rstrip("/") in self.state.files:
            raise PermissionError(f"Permission denied: {path}")
        while parent not in self.state.dirs and parent != "/":
            parent = PathResolver.parent_dir(parent)
            if parent.rstrip("/") in self.state.files:
                raise PermissionError(f"Permission denied: {path}")
        if not self.has_permission(
            parent, 0o200, allow_dir=True
        ) or not self.has_permission(parent, 0o100, allow_dir=True):
            raise PermissionError(f"Permission denied: {path}")

    def ensure_writable_file(self, path: str):
        if path in self.state.files and not self.has_permission(path, 0o200):
            raise PermissionError(f"Permission denied: {path}")

    def ensure_readable_file(self, path: str):
        if path in self.state.files and not self.has_permission(path, 0o400):
            raise PermissionError(f"Permission denied: {path}")

    def ensure_readable_dir(self, path: str):
        if not self.has_permission(
            path, 0o400, allow_dir=True
        ) or not self.has_permission(path, 0o100, allow_dir=True):
            raise PermissionError(f"Permission denied: {path}")

    def format_mode(self, mode: int, is_dir: bool) -> str:
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
