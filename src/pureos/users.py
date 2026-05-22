"""POSIX-like user and group management for v2-PureOS."""

from __future__ import annotations

import hashlib
import logging
from typing import Dict, List, Optional


class User:
    def __init__(
        self,
        username: str,
        uid: int,
        gid: int,
        gids: Optional[List[int]] = None,
        password_hash: str = "",
        locked: bool = False,
        disk_quota: int = 0,  # 0 means unlimited
        mem_quota: int = 0,  # 0 means unlimited
    ):
        self.username = username
        self.uid = uid
        self.gid = gid
        self.gids = gids if gids is not None else [gid]
        self.password_hash = password_hash
        self.locked = locked  # account lock (passwd -l)
        self.disk_quota = disk_quota
        self.mem_quota = mem_quota

    def set_password(self, password: str):
        if not password:
            self.password_hash = ""
        else:
            self.password_hash = hashlib.sha256(password.encode("utf-8")).hexdigest()

    def check_password(self, password: str) -> bool:
        if self.locked:
            return False
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
        self._effective_uid: Optional[int] = None
        self._effective_gid: Optional[int] = None

    @property
    def effective_uid(self) -> int:
        if self._effective_uid is not None:
            return self._effective_uid
        return self.current_user.uid if self.current_user else 0

    @property
    def effective_gid(self) -> int:
        if self._effective_gid is not None:
            return self._effective_gid
        return self.current_user.gid if self.current_user else 0

    @property
    def effective_gids(self) -> List[int]:
        if self._effective_gid is not None:
            # If SGID is active, the primary group is replaced in the set
            gids = self.current_user.gids.copy() if self.current_user else [0]
            if self._effective_gid not in gids:
                gids.append(self._effective_gid)
            return gids
        return self.current_user.gids if self.current_user else [0]

    def set_effective_ids(self, uid: Optional[int] = None, gid: Optional[int] = None):
        self._effective_uid = uid
        self._effective_gid = gid

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
        quota_content = ""
        if self.kernel.fs.exists("/etc/quota"):
            quota_content = self.kernel.fs.read("/etc/quota") or ""

        # Parse quotas
        quotas = {}
        for line in quota_content.splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            parts = line.split(":")
            if len(parts) >= 3:
                username = parts[0]
                try:
                    disk_quota = int(parts[1])
                    mem_quota = int(parts[2])
                    quotas[username] = (disk_quota, mem_quota)
                except ValueError:
                    continue

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
                    disk_quota=quotas.get(username, (0, 0))[0],
                    mem_quota=quotas.get(username, (0, 0))[1],
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
            quota_lines = []
            for user in self.users.values():
                # username:password_hash:uid:gid:gecos:home:shell
                line = (
                    f"{user.username}:{user.password_hash}:{user.uid}:{user.gid}:"
                    f"{user.username}:/home/{user.username}:/bin/sh"
                )
                passwd_lines.append(line)
                # username:disk_quota:mem_quota
                quota_lines.append(
                    f"{user.username}:{user.disk_quota}:{user.mem_quota}"
                )

            group_lines = []
            for groupname, gid in self.groups.items():
                members = self.group_members.get(groupname, [])
                # groupname:password:gid:member_list
                line = f"{groupname}:x:{gid}:{','.join(members)}"
                group_lines.append(line)

            self.kernel.fs.write("/etc/passwd", "\n".join(passwd_lines) + "\n")
            self.kernel.fs.write("/etc/group", "\n".join(group_lines) + "\n")
            self.kernel.fs.write("/etc/quota", "\n".join(quota_lines) + "\n")
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
            logging.getLogger("pureos.audit").warning(
                f"Failed login attempt for unknown user: {username}"
            )
            return False

        success = self.users[username].check_password(password)
        if not success:
            logging.getLogger("pureos.audit").warning(
                f"Failed login attempt for user: {username}"
            )
        else:
            logging.getLogger("pureos.audit").info(
                f"Successful authentication for user: {username}"
            )
        return success

    def su(self, username: str, password: Optional[str] = None) -> bool:
        if username not in self.users:
            logging.getLogger("pureos.audit").warning(
                f"su attempt for unknown user: {username}"
            )
            return False

        target_user = self.users[username]

        # Locked accounts cannot be switched to
        if target_user.locked:
            logging.getLogger("pureos.audit").warning(
                f"su attempt to locked account: {username}"
            )
            return False

        # Root user bypasses password checks; empty password hash also bypasses
        if (
            (self.current_user and self.current_user.uid == 0)
            or not target_user.password_hash
            or (password is not None and target_user.check_password(password))
        ):
            old_username = (
                self.current_user.username if self.current_user else "unknown"
            )
            logging.getLogger("pureos.audit").info(
                f"User {old_username} switched to {username}"
            )
            self.current_user = target_user
            self.save_login_session(username)
            return True

        logging.getLogger("pureos.audit").warning(
            f"Failed su attempt to {username} by "
            f"{self.current_user.username if self.current_user else 'unknown'}"
        )
        return False

    def passwd_lock(self, username: str):
        """Lock a user account (passwd -l)."""
        if username not in self.users:
            raise ValueError(f"User {username} does not exist")
        if username == "root":
            raise ValueError("Cannot lock root account")
        self.users[username].locked = True
        self.save_to_fs()

    def passwd_unlock(self, username: str):
        """Unlock a user account (passwd -u)."""
        if username not in self.users:
            raise ValueError(f"User {username} does not exist")
        self.users[username].locked = False
        self.save_to_fs()

    def is_sudoer(self, username: str) -> bool:
        """Check if a user is allowed to run sudo.

        Checks:
        1. /etc/sudoers for explicit user grants.
        2. Membership in the 'sudo' group.
        """
        user = self.users.get(username)
        if not user:
            return False
        # Root is always allowed
        if user.uid == 0:
            return True
        # Check /etc/sudoers
        if self.kernel.fs.exists("/etc/sudoers"):
            try:
                content = self.kernel.fs.read("/etc/sudoers") or ""
                for line in content.splitlines():
                    line = line.split("#")[0].strip()
                    if not line:
                        continue
                    parts = line.split()
                    if parts and parts[0] == username:
                        return True  # User is explicitly listed
                    if parts and parts[0].startswith("%"):
                        group_name = parts[0][1:]
                        if group_name in self.groups:
                            gid = self.groups[group_name]
                            if gid in user.gids:
                                return True
            except Exception:
                pass
        # Fall back to sudo group membership
        sudo_gid = self.groups.get("sudo", 27)
        return sudo_gid in user.gids

    def save_login_session(self, username: str):
        """Append a login entry to /var/log/lastlog."""
        import time

        try:
            timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
            entry = f"{username}\t{timestamp}\tpts/0\n"
            old_user = self.current_user
            root_user = self.users.get("root")
            if root_user:
                self.current_user = root_user
            try:
                if self.kernel.fs.exists("/var/log/lastlog"):
                    self.kernel.fs.append("/var/log/lastlog", entry)
                else:
                    self.kernel.fs.mkdir("/var/log", parents=True)
                    self.kernel.fs.write("/var/log/lastlog", entry)
            finally:
                self.current_user = old_user
        except Exception:
            pass
