"""Shell commands for user and permission management."""

import sys
from typing import List

from .base import Command


class WhoamiCommand(Command):
    name = "whoami"
    description = "Print the current active user name"
    usage = "whoami"

    def execute(
        self,
        parts: List[str],
        input_data=None,
        capture_output=False,
        raw_line=None,
    ):
        if not self.kernel.users or not self.kernel.users.current_user:
            print("root")
            return True
        username = self.kernel.users.current_user.username
        if capture_output:
            return username
        print(username)
        return True


class SuCommand(Command):
    name = "su"
    description = "Switch active user context"
    usage = "su [username]"

    def execute(
        self,
        parts: List[str],
        input_data=None,
        capture_output=False,
        raw_line=None,
    ):
        username = parts[1] if len(parts) > 1 else "root"
        users = self.kernel.users
        if not users or username not in users.users:
            print(f"su: user '{username}' does not exist")
            return False

        target_user = users.users[username]
        current_user = users.current_user

        # Root user bypasses password; empty password hash also bypasses
        if (current_user and current_user.uid == 0) or not target_user.password_hash:
            success = users.su(username)
            if not success:
                print("su: Authentication failure")
                return False
            return True

        # Otherwise prompt for password
        try:
            if sys.stdin.isatty():
                import getpass

                password = getpass.getpass("Password: ")
            else:
                password = input("Password: ")
        except (EOFError, KeyboardInterrupt):
            print("\nsu: Authentication failure")
            return False

        success = users.su(username, password)
        if not success:
            print("su: Authentication failure")
            return False

        return True


class UserAddCommand(Command):
    name = "useradd"
    description = "Create a new user"
    usage = "useradd <username>"

    def execute(
        self,
        parts: List[str],
        input_data=None,
        capture_output=False,
        raw_line=None,
    ):
        if len(parts) < 2:
            print("Usage: useradd <username>")
            return False

        users = self.kernel.users
        if not users:
            print("useradd: User database not initialized")
            return False

        if users.current_user and users.current_user.uid != 0:
            print("useradd: Permission denied")
            return False

        username = parts[1]
        try:
            users.add_user(username)
        except ValueError as exc:
            print(f"useradd: {exc}")
            return False

        return True


class UserDelCommand(Command):
    name = "userdel"
    description = "Delete an existing user"
    usage = "userdel <username>"

    def execute(
        self,
        parts: List[str],
        input_data=None,
        capture_output=False,
        raw_line=None,
    ):
        if len(parts) < 2:
            print("Usage: userdel <username>")
            return False

        users = self.kernel.users
        if not users:
            print("userdel: User database not initialized")
            return False

        if users.current_user and users.current_user.uid != 0:
            print("userdel: Permission denied")
            return False

        username = parts[1]
        try:
            users.delete_user(username)
        except ValueError as exc:
            print(f"userdel: {exc}")
            return False

        return True


class PasswdCommand(Command):
    name = "passwd"
    description = "Change a user's password, or lock/unlock an account"
    usage = "passwd [-l|-u] [username]"

    def execute(
        self,
        parts: List[str],
        input_data=None,
        capture_output=False,
        raw_line=None,
    ):
        users = self.kernel.users
        if not users:
            print("passwd: User database not initialized")
            return False

        # Check for -l (lock) or -u (unlock) flags
        lock_flag = "-l" in parts
        unlock_flag = "-u" in parts
        filtered = [p for p in parts[1:] if p not in ("-l", "-u")]

        current_user = users.current_user
        username = (
            filtered[0]
            if filtered
            else (current_user.username if current_user else "root")
        )

        if lock_flag:
            if current_user and current_user.uid != 0:
                print("passwd: Permission denied")
                return False
            try:
                users.passwd_lock(username)
                print(f"passwd: account '{username}' locked")
                return True
            except ValueError as exc:
                print(f"passwd: {exc}")
                return False

        if unlock_flag:
            if current_user and current_user.uid != 0:
                print("passwd: Permission denied")
                return False
            try:
                users.passwd_unlock(username)
                print(f"passwd: account '{username}' unlocked")
                return True
            except ValueError as exc:
                print(f"passwd: {exc}")
                return False

        if current_user and current_user.uid != 0 and current_user.username != username:
            print("passwd: Permission denied")
            return False

        try:
            if sys.stdin.isatty():
                import getpass

                p1 = getpass.getpass("New password: ")
                p2 = getpass.getpass("Retype new password: ")
            else:
                p1 = input("New password: ")
                p2 = input("Retype new password: ")
        except (EOFError, KeyboardInterrupt):
            print("\npasswd: password unchanged")
            return False

        if p1 != p2:
            print("passwd: passwords do not match")
            return False

        try:
            users.passwd(username, p1)
            print("passwd: password updated successfully")
        except ValueError as exc:
            print(f"passwd: {exc}")
            return False

        return True


class GroupsCommand(Command):
    name = "groups"
    description = "Print group memberships for a user"
    usage = "groups [username]"

    def execute(
        self,
        parts: List[str],
        input_data=None,
        capture_output=False,
        raw_line=None,
    ):
        users = self.kernel.users
        if not users:
            print("groups: User database not initialized")
            return False

        current_user = users.current_user
        username = (
            parts[1]
            if len(parts) > 1
            else (current_user.username if current_user else "root")
        )

        user = users.users.get(username)
        if not user:
            print(f"groups: '{username}': no such user")
            return False

        group_names = []
        for gname, gid in users.groups.items():
            if gid in user.gids:
                group_names.append(gname)

        out = " ".join(group_names)
        if capture_output:
            return out
        print(out)
        return True


class ChownCommand(Command):
    name = "chown"
    description = "Change the owner of a file or directory"
    usage = "chown <owner> <path>"

    def execute(
        self,
        parts: List[str],
        input_data=None,
        capture_output=False,
        raw_line=None,
    ):
        if len(parts) < 3:
            print("Usage: chown <owner> <path>")
            return False

        owner = parts[1]
        path = parts[2]
        users = self.kernel.users

        if not users or (users.current_user and users.current_user.uid != 0):
            print("chown: Permission denied")
            return False

        owner_uid = None
        if owner.isdigit():
            owner_uid = int(owner)
        else:
            u = users.users.get(owner)
            if u:
                owner_uid = u.uid
            else:
                print(f"chown: invalid user: '{owner}'")
                return False

        resolved_path = self.resolve_path(path, allow_dir=True)
        if not self.kernel.fs.exists(resolved_path):
            # Check if directory exists ending in /
            resolved_path_dir = (
                resolved_path if resolved_path.endswith("/") else resolved_path + "/"
            )
            if not self.kernel.fs.exists(resolved_path_dir):
                print(f"chown: '{path}': No such file or directory")
                return False
            resolved_path = resolved_path_dir

        self.kernel.fs.state.owners[resolved_path] = owner_uid
        self.kernel.fs.persistence.save_if_needed()
        return True


class ChgrpCommand(Command):
    name = "chgrp"
    description = "Change the group of a file or directory"
    usage = "chgrp <group> <path>"

    def execute(
        self,
        parts: List[str],
        input_data=None,
        capture_output=False,
        raw_line=None,
    ):
        if len(parts) < 3:
            print("Usage: chgrp <group> <path>")
            return False

        group = parts[1]
        path = parts[2]
        users = self.kernel.users

        resolved_path = self.resolve_path(path, allow_dir=True)
        if not self.kernel.fs.exists(resolved_path):
            resolved_path_dir = (
                resolved_path if resolved_path.endswith("/") else resolved_path + "/"
            )
            if not self.kernel.fs.exists(resolved_path_dir):
                print(f"chgrp: '{path}': No such file or directory")
                return False
            resolved_path = resolved_path_dir

        current_user = users.current_user if users else None
        file_owner = self.kernel.fs.state.owners.get(resolved_path, 0)

        if current_user and current_user.uid != 0 and current_user.uid != file_owner:
            print("chgrp: Permission denied")
            return False

        group_gid = None
        if group.isdigit():
            group_gid = int(group)
        else:
            if not users or group not in users.groups:
                print(f"chgrp: invalid group: '{group}'")
                return False
            group_gid = users.groups[group]

        if current_user and current_user.uid != 0:
            if group_gid not in current_user.gids:
                print("chgrp: Permission denied")
                return False

        self.kernel.fs.state.groups[resolved_path] = group_gid
        self.kernel.fs.persistence.save_if_needed()
        return True


class SudoCommand(Command):
    name = "sudo"
    description = "Execute a command with root privileges"
    usage = "sudo <command> [args...]"

    def execute(
        self,
        parts: List[str],
        input_data=None,
        capture_output=False,
        raw_line=None,
    ):
        if len(parts) < 2:
            print("Usage: sudo <command> [args...]")
            return False

        users = self.kernel.users
        if not users:
            print("sudo: User database not initialized")
            return False

        current_user = users.current_user
        if not current_user:
            print("sudo: No active user context")
            return False

        # If not root, check permissions
        if current_user.uid != 0:
            if not users.is_sudoer(current_user.username):
                print(
                    f"sudo: {current_user.username} is not in the sudoers "
                    "file. This incident will be reported."
                )
                return False

            # Prompt for password if the user has a password set
            if current_user.password_hash:
                try:
                    if sys.stdin.isatty():
                        import getpass

                        password = getpass.getpass(
                            f"[sudo] password for {current_user.username}: "
                        )
                    else:
                        password = input(
                            f"[sudo] password for {current_user.username}: "
                        )
                except (EOFError, KeyboardInterrupt):
                    print("\nsudo: Authentication failure")
                    return False

                if not current_user.check_password(password):
                    print("sudo: password incorrect")
                    return False

        # Elevate privileges to root (uid 0)
        root_user = users.users.get("root")
        if not root_user:
            print("sudo: root user not found")
            return False

        original_user = users.current_user
        users.current_user = root_user

        # Extract sub-command parts and raw line
        target_parts = parts[1:]
        target_raw_line = None
        if raw_line:
            import re

            match = re.match(r"^\s*sudo\s+(.*)$", raw_line)
            if match:
                target_raw_line = match.group(1)
            else:
                target_raw_line = " ".join(target_parts)

        try:
            result = self.kernel.shell.registry.execute(
                target_parts,
                input_data=input_data,
                capture_output=capture_output,
                raw_line=target_raw_line,
            )
            return result
        finally:
            users.current_user = original_user


class LoginCommand(Command):
    name = "login"
    description = "Log in as a user interactively"
    usage = "login [username]"

    def execute(
        self,
        parts: List[str],
        input_data=None,
        capture_output=False,
        raw_line=None,
    ):
        users = self.kernel.users
        if not users:
            print("login: User database not initialized")
            return False

        if len(parts) > 1:
            username = parts[1]
        else:
            try:
                username = input("Username: ").strip()
            except (EOFError, KeyboardInterrupt):
                print()
                return False

        if username not in users.users:
            print(f"login: user '{username}' does not exist")
            return False

        target_user = users.users[username]
        if target_user.locked:
            print(f"login: account '{username}' is locked")
            return False

        if target_user.password_hash:
            try:
                if sys.stdin.isatty():
                    import getpass

                    password = getpass.getpass("Password: ")
                else:
                    password = input("Password: ")
            except (EOFError, KeyboardInterrupt):
                print("\nlogin: Authentication failure")
                return False
            if not target_user.check_password(password):
                print("login: Authentication failure")
                return False

        users.current_user = target_user
        users.save_login_session(username)
        print(f"Welcome, {username}!")
        return True


class LastCommand(Command):
    name = "last"
    description = "Show recent login history from /var/log/lastlog"
    usage = "last [username]"

    def execute(
        self,
        parts: List[str],
        input_data=None,
        capture_output=False,
        raw_line=None,
    ):
        if not self.kernel.fs.exists("/var/log/lastlog"):
            out = "lastlog: no login records found"
            if capture_output:
                return out
            print(out)
            return True

        content = self.kernel.fs.read("/var/log/lastlog") or ""
        filter_user = parts[1] if len(parts) > 1 else None
        lines = []
        for line in content.splitlines():
            if not line.strip():
                continue
            if filter_user and not line.startswith(filter_user + "\t"):
                continue
            fields = line.split("\t")
            if len(fields) >= 3:
                user, ts, tty = fields[0], fields[1], fields[2]
                lines.append(f"{user:<16} {tty:<8} {ts}")
            else:
                lines.append(line)

        if not lines:
            out = (
                f"last: no records for '{filter_user}'"
                if filter_user
                else "last: no records"
            )
        else:
            lines.append("")
            lines.append(f"wtmp begins {lines[0].split()[-1] if lines else 'unknown'}")
            out = "\n".join(lines)

        if capture_output:
            return out
        print(out)
        return True
