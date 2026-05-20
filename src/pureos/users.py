"""POSIX-like user and group management for v2-PureOS."""

from __future__ import annotations

import hashlib
from typing import Dict, List, Optional


class User:
    def __init__(
        self,
        username: str,
        uid: int,
        gid: int,
        gids: Optional[List[int]] = None,
        password_hash: str = "",
    ):
        self.username = username
        self.uid = uid
        self.gid = gid
        self.gids = gids if gids is not None else [gid]
        self.password_hash = password_hash

    def set_password(self, password: str):
        if not password:
            self.password_hash = ""
        else:
            self.password_hash = hashlib.sha256(password.encode("utf-8")).hexdigest()

    def check_password(self, password: str) -> bool:
        if not self.password_hash:
            # Empty password means no password required
            return True
        hashed = hashlib.sha256(password.encode("utf-8")).hexdigest()
        return self.password_hash == hashed


class UserDB:
    def __init__(self, kernel):
        self.kernel = kernel
        self.users: Dict[str, User] = {}
        self.groups: Dict[str, int] = {}  # groupname -> gid
        self.group_members: Dict[str, List[str]] = {}  # groupname -> [usernames]
        self.current_user: Optional[User] = None

    def initialize(self):
        """Initialize the user database, creating defaults if not persisted."""
        if self.kernel.fs.exists("/etc/passwd"):
            try:
                self.load_from_fs()
            except Exception as exc:
                self.kernel.logger.error("Failed to load users from FS: %s", exc)
                self._create_defaults()
        else:
            self._create_defaults()

        # Set default active user to root
        self.current_user = self.users.get("root")

    def _create_defaults(self):
        self.users.clear()
        self.groups.clear()
        self.group_members.clear()

        # Create root user and group
        root_user = User("root", uid=0, gid=0, password_hash="")
        self.users["root"] = root_user
        self.groups["root"] = 0
        self.group_members["root"] = ["root"]

        # Create guest user and group
        guest_user = User(
            "guest", uid=1000, gid=1000, gids=[1000, 27], password_hash=""
        )
        self.users["guest"] = guest_user
        self.groups["guest"] = 1000
        self.group_members["guest"] = ["guest"]

        # Create sudo group
        self.groups["sudo"] = 27
        self.group_members["sudo"] = ["guest"]

        # Save these to the virtual filesystem
        self.save_to_fs()

    def load_from_fs(self):
        """Load users and groups from /etc/passwd and /etc/group."""
        if not self.kernel.fs.exists("/etc/passwd") or not self.kernel.fs.exists(
            "/etc/group"
        ):
            return

        passwd_content = self.kernel.fs.read("/etc/passwd") or ""
        group_content = self.kernel.fs.read("/etc/group") or ""

        # Parse groups first to populate user gids
        self.groups.clear()
        self.group_members.clear()
        for line in group_content.splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            parts = line.split(":")
            if len(parts) >= 3:
                groupname = parts[0]
                try:
                    gid = int(parts[2])
                except ValueError:
                    continue
                self.groups[groupname] = gid
                members = parts[3].split(",") if len(parts) > 3 and parts[3] else []
                self.group_members[groupname] = members

        # Parse users
        self.users.clear()
        for line in passwd_content.splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            parts = line.split(":")
            if len(parts) >= 4:
                username = parts[0]
                password_hash = parts[1]
                try:
                    uid = int(parts[2])
                    gid = int(parts[3])
                except ValueError:
                    continue

                # Resolve supplementary groups
                gids = [gid]
                for gname, ggid in self.groups.items():
                    members = self.group_members.get(gname, [])
                    if username in members and ggid not in gids:
                        gids.append(ggid)

                user = User(
                    username=username,
                    uid=uid,
                    gid=gid,
                    gids=gids,
                    password_hash=password_hash,
                )
                self.users[username] = user

    def save_to_fs(self):
        """Save users and groups to /etc/passwd and /etc/group."""
        # Temporarily elevate to root to allow writing etc files (like setuid root)
        old_user = self.current_user
        root_user = self.users.get("root")
        if root_user:
            self.current_user = root_user

        try:
            passwd_lines = []
            for user in self.users.values():
                # username:password_hash:uid:gid:gecos:home:shell
                line = (
                    f"{user.username}:{user.password_hash}:{user.uid}:{user.gid}:"
                    f"{user.username}:/home/{user.username}:/bin/sh"
                )
                passwd_lines.append(line)

            group_lines = []
            for groupname, gid in self.groups.items():
                members = self.group_members.get(groupname, [])
                # groupname:password:gid:member_list
                line = f"{groupname}:x:{gid}:{','.join(members)}"
                group_lines.append(line)

            self.kernel.fs.write("/etc/passwd", "\n".join(passwd_lines) + "\n")
            self.kernel.fs.write("/etc/group", "\n".join(group_lines) + "\n")
        finally:
            self.current_user = old_user

    def add_user(
        self,
        username: str,
        password: Optional[str] = None,
        uid: Optional[int] = None,
        gid: Optional[int] = None,
    ) -> User:
        if username in self.users:
            raise ValueError(f"User {username} already exists")

        # Determine UID
        if uid is None:
            existing_uids = {u.uid for u in self.users.values() if u.uid >= 1000}
            uid = 1000
            while uid in existing_uids:
                uid += 1

        # Determine GID
        if gid is None:
            existing_gids = {ggid for ggid in self.groups.values() if ggid >= 1000}
            gid = 1000
            while gid in existing_gids:
                gid += 1

        # Create user group if not exists
        if username not in self.groups:
            self.groups[username] = gid
            self.group_members[username] = [username]

        user = User(username=username, uid=uid, gid=gid, password_hash="")
        if password:
            user.set_password(password)

        self.users[username] = user
        self.save_to_fs()
        return user

    def delete_user(self, username: str):
        if username not in self.users:
            raise ValueError(f"User {username} does not exist")
        if username == "root":
            raise ValueError("Cannot delete root user")
        if self.current_user and self.current_user.username == username:
            raise ValueError("Cannot delete current user")

        del self.users[username]
        # Remove user from group memberships
        for groupname, members in list(self.group_members.items()):
            if username in members:
                members.remove(username)
                if groupname == username:
                    # Clean up user's primary group if empty or matches name
                    self.groups.pop(groupname, None)
                    self.group_members.pop(groupname, None)

        self.save_to_fs()

    def passwd(self, username: str, password: str):
        if username not in self.users:
            raise ValueError(f"User {username} does not exist")
        self.users[username].set_password(password)
        self.save_to_fs()

    def authenticate(self, username: str, password: str) -> bool:
        if username not in self.users:
            return False
        return self.users[username].check_password(password)

    def su(self, username: str, password: Optional[str] = None) -> bool:
        if username not in self.users:
            return False

        target_user = self.users[username]

        # Root user bypasses password checks; empty password hash also bypasses
        if (
            (self.current_user and self.current_user.uid == 0)
            or not target_user.password_hash
            or (password is not None and target_user.check_password(password))
        ):
            self.current_user = target_user
            return True

        return False
