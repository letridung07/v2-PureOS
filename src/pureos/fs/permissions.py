from .state import FSState
from .path import PathResolver


class FSPermissions:
    def __init__(self, state: FSState, kernel=None):
        self.state = state
        self.kernel = kernel

    def has_permission(
        self, path: str, permission: int, allow_dir: bool = False
    ) -> bool:
        normalized = PathResolver.normalize_path(path, allow_dir=allow_dir)

        # Find owner and group of the file
        owner_uid = self.state.owners.get(normalized, 0)
        group_gid = self.state.groups.get(normalized, 0)

        # Get file mode
        if normalized in self.state.files:
            mode = self.state.modes.get(normalized, 0o644)
        else:
            dir_path = normalized if normalized.endswith("/") else normalized + "/"
            if dir_path in self.state.dirs:
                mode = self.state.modes.get(dir_path, 0o755)
                owner_uid = self.state.owners.get(dir_path, 0)
                group_gid = self.state.groups.get(dir_path, 0)
            else:
                return False

        # If running standalone VirtualFS (no kernel/userDB), fallback to raw mode check
        if (
            not self.kernel
            or not hasattr(self.kernel, "users")
            or not self.kernel.users
        ):
            return bool(mode & permission)

        # Get active user context
        current_uid = self.kernel.users.effective_uid
        current_gids = self.kernel.users.effective_gids

        # Root bypasses all permission checks
        if current_uid == 0:
            return True

        # Mode contains 9 permission bits: rwxrwxrwx
        # permission argument represents requested owner bits (e.g. 0o400, 0o200, 0o100)
        if current_uid == owner_uid:
            return bool(mode & permission)
        elif group_gid in current_gids:
            return bool(mode & (permission >> 3))
        else:
            return bool(mode & (permission >> 6))

    def _audit_failure(self, message: str):
        if self.kernel:
            import logging

            user = self.kernel.users.current_user
            username = user.username if user else "unknown"
            logging.getLogger("pureos.audit").warning(
                f"Permission denied for user {username}: {message}"
            )

    def ensure_parent_writable(self, path: str):
        parent = PathResolver.parent_dir(path)
        if parent.rstrip("/") in self.state.files:
            self._audit_failure(f"parent is a file: {path}")
            raise PermissionError(f"Permission denied: {path}")
        while parent not in self.state.dirs and parent != "/":
            parent = PathResolver.parent_dir(parent)
            if parent.rstrip("/") in self.state.files:
                self._audit_failure(f"parent is a file: {path}")
                raise PermissionError(f"Permission denied: {path}")
        if not self.has_permission(
            parent, 0o200, allow_dir=True
        ) or not self.has_permission(parent, 0o100, allow_dir=True):
            self._audit_failure(f"write/execute denied on parent {parent} for {path}")
            raise PermissionError(f"Permission denied: {path}")

    def ensure_writable_file(self, path: str):
        if path in self.state.files and not self.has_permission(path, 0o200):
            self._audit_failure(f"write denied on file {path}")
            raise PermissionError(f"Permission denied: {path}")

    def ensure_readable_file(self, path: str):
        if path in self.state.files and not self.has_permission(path, 0o400):
            self._audit_failure(f"read denied on file {path}")
            raise PermissionError(f"Permission denied: {path}")

    def ensure_readable_dir(self, path: str):
        if not self.has_permission(
            path, 0o400, allow_dir=True
        ) or not self.has_permission(path, 0o100, allow_dir=True):
            self._audit_failure(f"read/execute denied on directory {path}")
            raise PermissionError(f"Permission denied: {path}")

    def ensure_deletion_allowed(self, path: str):
        """Check if deleting/renaming is allowed, respecting the sticky bit (0o1000)."""
        normalized = PathResolver.normalize_path(path, allow_dir=True)
        parent = PathResolver.parent_dir(normalized)

        # Ensure parent is writable (base POSIX requirement)
        self.ensure_parent_writable(normalized)

        # If no kernel/userDB, we can't check identities
        if (
            not self.kernel
            or not hasattr(self.kernel, "users")
            or not self.kernel.users
        ):
            return

        current_uid = self.kernel.users.effective_uid
        if current_uid == 0:
            return  # Root bypasses sticky bit

        # Check sticky bit on parent
        parent_mode = self.state.modes.get(parent, 0o755)
        if parent_mode & 0o1000:
            # Sticky bit set: user must be file owner, directory owner, or root
            file_owner = self.state.owners.get(normalized, 0)
            parent_owner = self.state.owners.get(parent, 0)
            if current_uid != file_owner and current_uid != parent_owner:
                self._audit_failure(f"sticky bit restriction: {path}")
                raise PermissionError(f"Permission denied: {path}")

    def ensure_executable_file(self, path: str):
        """Verify execute permissions (0o100) for a file."""
        if not self.has_permission(path, 0o100):
            self._audit_failure(f"execute denied on file {path}")
            raise PermissionError(f"Permission denied: {path}")

    def format_mode(self, mode: int, is_dir: bool, is_link: bool = False) -> str:
        if is_link:
            type_char = "l"
        elif is_dir:
            type_char = "d"
        else:
            type_char = "-"
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
        # Sticky bit: replace last 'x'/'–' with 't'/'T'
        if is_dir:
            last = perms[8]
            if mode & 0o1000:  # sticky bit in mode
                perms[8] = "t" if last == "x" else "T"
        return type_char + "".join(perms)

    def ensure_chmod_allowed(self, path: str):
        """Only the owner or root may change a file's mode."""
        if (
            not self.kernel
            or not hasattr(self.kernel, "users")
            or not self.kernel.users
        ):
            return
        current_uid = self.kernel.users.effective_uid
        if current_uid == 0:
            return  # root always allowed
        owner_uid = self.state.owners.get(path, 0)
        if current_uid != owner_uid:
            raise PermissionError(f"Permission denied: {path}")
