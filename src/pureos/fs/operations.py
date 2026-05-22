from __future__ import annotations
from typing import List, Optional, Dict
import os
from .state import FSState
from .path import PathResolver
from .permissions import FSPermissions
from .persistence import FSPersistence


class FSOperations:
    def __init__(
        self, state: FSState, permissions: FSPermissions, persistence: FSPersistence
    ):
        self.state = state
        self.permissions = permissions
        self.persistence = persistence

    def _get_active_context(self) -> tuple[int, int]:
        if (
            self.permissions.kernel
            and hasattr(self.permissions.kernel, "users")
            and self.permissions.kernel.users
        ):
            user = self.permissions.kernel.users.current_user
            if user:
                return user.uid, user.gid
        return 0, 0

    def _set_default_metadata(
        self, path: str, uid: int, gid: int, mode: Optional[int] = None
    ):
        self.state.owners.setdefault(path, uid)
        self.state.groups.setdefault(path, gid)
        if mode is not None:
            self.state.modes.setdefault(path, mode)
        self.state.inodes.setdefault(path, self.state.next_inode())

    def format(self):
        """Reset filesystem to initial state."""
        self.state.files.clear()
        self.state.symlinks.clear()
        self.state.inodes.clear()
        self.state._inode_counter = 2
        self.state.sticky_bits = {"/tmp/"}
        self.state.dirs = {"/", "/etc/", "/tmp/"}
        self.state.modes = {
            "/": 0o755,
            "/etc/": 0o755,
            "/tmp/": 0o1777,  # sticky
            "/etc/motd": 0o644,
            "/etc/pureosrc": 0o644,
            "/etc/passwd": 0o644,
            "/etc/group": 0o644,
        }
        self.state.files["/etc/motd"] = "Welcome to v2-PureOS"
        self.state.files["/etc/pureosrc"] = (
            "alias ll ls -l\n" "alias la ls\n" "alias grep grep -i\n"
        )
        self.state.files["/etc/passwd"] = (
            "root::0:0:root:/root:/bin/sh\n"
            "guest::1000:1000:guest:/home/guest:/bin/sh\n"
        )
        self.state.files["/etc/group"] = (
            "root:x:0:root\n" "guest:x:1000:guest\n" "sudo:x:27:guest\n"
        )
        self.state.owners = {
            "/": 0,
            "/etc/": 0,
            "/tmp/": 0,
            "/etc/motd": 0,
            "/etc/pureosrc": 0,
            "/etc/passwd": 0,
            "/etc/group": 0,
        }
        self.state.groups = {
            "/": 0,
            "/etc/": 0,
            "/tmp/": 0,
            "/etc/motd": 0,
            "/etc/pureosrc": 0,
            "/etc/passwd": 0,
            "/etc/group": 0,
        }
        # Assign inodes to initial entries
        for path in list(self.state.dirs) + list(self.state.files):
            self.state.inodes[path] = self.state.next_inode()
        self.state.inodes["/"] = 1
        self.persistence.save_if_needed()

    def mkdir(self, path: str, parents: bool = True):
        path = PathResolver.normalize_path(path, is_dir=True)
        if path in self.state.files:
            raise ValueError(f"Cannot create directory, a file exists at {path}")
        self.permissions.ensure_parent_writable(path)
        uid, gid = self._get_active_context()
        if parents:
            PathResolver.ensure_dir_parents(self.state, path, uid, gid)
        self.state.dirs.add(path)
        self._set_default_metadata(path, uid, gid, 0o755)
        self.persistence.save_if_needed()

    def _get_user_usage(self, uid: int) -> int:
        total = 0
        for path, owner in self.state.owners.items():
            if owner == uid and path in self.state.files:
                total += len(self.state.files[path])
        return total

    def _check_disk_quota(self, uid: int, additional_bytes: int, current_file_path: Optional[str] = None):
        if uid == 0:
            return  # root has no quota

        if (
            not self.permissions.kernel
            or not hasattr(self.permissions.kernel, "users")
            or not self.permissions.kernel.users
        ):
            return

        user = None
        for u in self.permissions.kernel.users.users.values():
            if u.uid == uid:
                user = u
                break
        
        if not user or user.disk_quota <= 0:
            return

        current_usage = self._get_user_usage(uid)
        # If we are overwriting a file, subtract its current size from current_usage
        if current_file_path and current_file_path in self.state.files and self.state.owners.get(current_file_path) == uid:
            current_usage -= len(self.state.files[current_file_path])

        if current_usage + additional_bytes > user.disk_quota:
            import logging
            logging.getLogger("pureos.audit").warning(f"Disk quota exceeded for user {user.username}: requested {current_usage + additional_bytes}, limit {user.disk_quota}")
            raise OSError(f"Disk quota exceeded (limit: {user.disk_quota} bytes)")

    def write(self, path: str, content: str):
        normalized = PathResolver.normalize_path(path)
        if (
            normalized.endswith("/")
            or normalized in self.state.dirs
            or normalized + "/" in self.state.dirs
        ):
            raise ValueError("Cannot write to a directory path")
        if normalized in self.state.files:
            self.permissions.ensure_writable_file(normalized)
        else:
            self.permissions.ensure_parent_writable(normalized)

        uid, gid = self._get_active_context()
        self._check_disk_quota(uid, len(content), current_file_path=normalized)
        PathResolver.ensure_dir_parents(self.state, normalized, uid, gid)

        inode = self.state.inodes.get(normalized)
        if inode is None:
            inode = self.state.next_inode()
            self.state.inodes[normalized] = inode

        for p, i in list(self.state.inodes.items()):
            if i == inode and (p in self.state.files or p == normalized):
                self.state.files[p] = content
                self.state.modes.setdefault(p, 0o644)

        self._set_default_metadata(normalized, uid, gid, 0o644)
        self.persistence.save_if_needed()

    def append(self, path: str, content: str):
        normalized = PathResolver.normalize_path(path)
        if (
            normalized.endswith("/")
            or normalized in self.state.dirs
            or normalized + "/" in self.state.dirs
        ):
            raise ValueError("Cannot append to a directory path")
        if normalized in self.state.files:
            self.permissions.ensure_writable_file(normalized)
        else:
            self.permissions.ensure_parent_writable(normalized)

        uid, gid = self._get_active_context()
        self._check_disk_quota(uid, len(content))
        PathResolver.ensure_dir_parents(self.state, normalized, uid, gid)

        inode = self.state.inodes.get(normalized)
        if inode is None:
            inode = self.state.next_inode()
            self.state.inodes[normalized] = inode

        new_content = self.state.files.get(normalized, "") + content

        for p, i in list(self.state.inodes.items()):
            if i == inode and (p in self.state.files or p == normalized):
                self.state.files[p] = new_content
                self.state.modes.setdefault(p, 0o644)

        self._set_default_metadata(normalized, uid, gid, 0o644)
        self.persistence.save_if_needed()

    def read(self, path: str) -> Optional[str]:
        normalized = PathResolver.normalize_path(path, allow_dir=True)
        # Resolve symlink transparently
        normalized = self.resolve_symlink(normalized)
        if normalized.endswith("/") or normalized + "/" in self.state.dirs:
            return None
        self.permissions.ensure_readable_file(normalized)
        return self.state.files.get(normalized)

    def read_lines(self, path: str) -> Optional[List[str]]:
        content = self.read(path)
        if content is None:
            return None
        return content.splitlines()

    def list(self, prefix: str = "/", recursive: bool = False) -> List[str]:
        if recursive:
            return self.find(prefix)
        normalized = PathResolver.normalize_path(prefix, allow_dir=True)
        if normalized in self.state.files:
            return [normalized]
        if normalized != "/" and not normalized.endswith("/"):
            normalized = normalized + "/"
        self.permissions.ensure_readable_dir(normalized)
        result = []
        for d in self.state.dirs:
            if d == normalized:
                continue
            if d.startswith(normalized):
                remainder = d[len(normalized) :]
                if remainder and "/" not in remainder.rstrip("/"):
                    result.append(d)
        for f in self.state.files:
            if f.startswith(normalized):
                remainder = f[len(normalized) :]
                if remainder and "/" not in remainder:
                    result.append(f)
        return sorted(result)

    def find(self, prefix: str = "/") -> List[str]:
        normalized = PathResolver.normalize_path(prefix, allow_dir=True)
        if normalized in self.state.files:
            return [normalized]
        if normalized != "/" and not normalized.endswith("/"):
            normalized = normalized + "/"
        self.permissions.ensure_readable_dir(normalized)
        result = []
        for d in sorted(self.state.dirs):
            if d.startswith(normalized) and d != normalized:
                result.append(d)
        for f in sorted(self.state.files):
            if f.startswith(normalized):
                result.append(f)
        return result

    def exists(self, path: str) -> bool:
        normalized = PathResolver.normalize_path(path, allow_dir=True)
        # A symlink entry counts as existing even if its target doesn't
        if normalized in self.state.symlinks:
            return True
        resolved = self.resolve_symlink(normalized)
        return (
            resolved in self.state.files
            or resolved in self.state.dirs
            or resolved + "/" in self.state.dirs
        )

    def is_dir(self, path: str) -> bool:
        normalized = PathResolver.normalize_path(path, allow_dir=True)
        return normalized in self.state.dirs or normalized + "/" in self.state.dirs

    def is_file(self, path: str) -> bool:
        normalized = PathResolver.normalize_path(path, allow_dir=True)
        return normalized in self.state.files

    def stat(self, path: str) -> Optional[Dict[str, object]]:
        normalized = PathResolver.normalize_path(path, allow_dir=True)
        # Check symlink first (stat on the link itself)
        if normalized in self.state.symlinks:
            target = self.state.symlinks[normalized]
            mode = self.state.modes.get(normalized, 0o777)
            inode = self.state.inodes.get(normalized, 0)
            return {
                "path": normalized,
                "type": "symlink",
                "inode": inode,
                "link_count": 1,
                "mode": mode,
                "mode_str": self.permissions.format_mode(mode, False, is_link=True),
                "size": len(target),
                "symlink_target": target,
            }
        # Resolve symlink for regular stat
        resolved = self.resolve_symlink(normalized)
        if resolved in self.state.files:
            mode = self.state.modes.get(resolved, 0o644)
            inode = self.state.inodes.get(resolved, 0)
            # Hard link count = number of paths sharing this inode
            link_count = sum(
                1
                for p, i in self.state.inodes.items()
                if i == inode and p in self.state.files
            )
            return {
                "path": resolved,
                "type": "file",
                "inode": inode,
                "link_count": link_count,
                "mode": mode,
                "mode_str": self.permissions.format_mode(mode, False),
                "size": len(self.state.files[resolved]),
            }
        dir_path = resolved if resolved.endswith("/") else resolved + "/"
        if dir_path in self.state.dirs:
            mode = self.state.modes.get(dir_path, 0o755)
            inode = self.state.inodes.get(dir_path, 0)
            return {
                "path": dir_path,
                "type": "dir",
                "inode": inode,
                "link_count": 2,
                "mode": mode,
                "mode_str": self.permissions.format_mode(mode, True),
                "size": 0,
            }
        return None

    def chmod(self, path: str, mode: int):
        normalized = PathResolver.normalize_path(path, allow_dir=True)
        if normalized in self.state.files:
            self.permissions.ensure_chmod_allowed(normalized)
            inode = self.state.inodes.get(normalized)
            if inode is not None:
                for p, i in list(self.state.inodes.items()):
                    if i == inode and p in self.state.files:
                        self.state.modes[p] = mode
            else:
                self.state.modes[normalized] = mode
            self.persistence.save_if_needed()
            return
        dir_path = normalized if normalized.endswith("/") else normalized + "/"
        if dir_path in self.state.dirs:
            self.permissions.ensure_chmod_allowed(dir_path)
            self.state.modes[dir_path] = mode
            # Sync sticky_bits set with mode
            if mode & 0o1000:
                self.state.sticky_bits.add(dir_path)
            else:
                self.state.sticky_bits.discard(dir_path)
            self.persistence.save_if_needed()
            return
        raise FileNotFoundError(path)

    def chown(self, path: str, uid: int):
        normalized = PathResolver.normalize_path(path, allow_dir=True)
        # Handle directory normalization
        if not self.exists(normalized) and not self.exists(normalized + "/"):
            raise FileNotFoundError(f"No such file or directory: '{path}'")
        if not self.exists(normalized) and self.exists(normalized + "/"):
            normalized += "/"

        # Only root can change owner
        current_uid, _ = self._get_active_context()
        if current_uid != 0:
            raise PermissionError("Permission denied")

        self.state.owners[normalized] = uid
        self.persistence.save_if_needed()

    def chgrp(self, path: str, gid: int):
        normalized = PathResolver.normalize_path(path, allow_dir=True)
        if not self.exists(normalized) and not self.exists(normalized + "/"):
            raise FileNotFoundError(f"No such file or directory: '{path}'")
        if not self.exists(normalized) and self.exists(normalized + "/"):
            normalized += "/"

        # Check permissions: only root or owner can change group
        # and if owner, must be a member of the target group
        uid, active_gid = self._get_active_context()
        owner = self.state.owners.get(normalized, 0)
        if uid != 0:
            if uid != owner:
                raise PermissionError("Permission denied")
            # If owner but not root, check if gid is in user's groups
            if (
                self.permissions.kernel
                and hasattr(self.permissions.kernel, "users")
                and self.permissions.kernel.users
            ):
                user = self.permissions.kernel.users.current_user
                if user and gid not in user.gids:
                    raise PermissionError("Permission denied")

        self.state.groups[normalized] = gid
        self.persistence.save_if_needed()

    def delete(self, path: str):
        normalized = PathResolver.normalize_path(path, allow_dir=True)
        if normalized == "/":
            raise PermissionError("Cannot delete root directory")
        self.permissions.ensure_parent_writable(normalized)
        if normalized in self.state.files:
            del self.state.files[normalized]
            self.state.modes.pop(normalized, None)
            self.state.owners.pop(normalized, None)
            self.state.groups.pop(normalized, None)
            self.state.inodes.pop(normalized, None)
            self.persistence.save_if_needed()
            return
        if (
            normalized not in self.state.dirs
            and normalized + "/" not in self.state.dirs
        ):
            return
        if normalized not in self.state.dirs:
            normalized += "/"
        for file_path in list(self.state.files):
            if file_path.startswith(normalized):
                del self.state.files[file_path]
                self.state.modes.pop(file_path, None)
                self.state.owners.pop(file_path, None)
                self.state.groups.pop(file_path, None)
                self.state.inodes.pop(file_path, None)
        for dir_path in list(self.state.dirs):
            if dir_path.startswith(normalized):
                self.state.dirs.discard(dir_path)
                self.state.modes.pop(dir_path, None)
                self.state.owners.pop(dir_path, None)
                self.state.groups.pop(dir_path, None)
                self.state.inodes.pop(dir_path, None)
        self.state.dirs.discard(normalized)
        self.state.modes.pop(normalized, None)
        self.state.owners.pop(normalized, None)
        self.state.groups.pop(normalized, None)
        self.state.inodes.pop(normalized, None)
        self.persistence.save_if_needed()

    def rename(self, src: str, dst: str):
        src = PathResolver.normalize_path(src, allow_dir=True)
        if src in self.state.files:
            self.permissions.ensure_readable_file(src)
            self.permissions.ensure_parent_writable(dst)
            self._rename_file(src, dst)
        elif src in self.state.dirs or src + "/" in self.state.dirs:
            self.permissions.ensure_parent_writable(dst)
            self._rename_dir(src, dst)

    def copy(self, src: str, dst: str):
        src = PathResolver.normalize_path(src, allow_dir=True)
        if src in self.state.files:
            self.permissions.ensure_readable_file(src)
            self.permissions.ensure_parent_writable(dst)
            self._copy_file(src, dst)
        elif src in self.state.dirs or src + "/" in self.state.dirs:
            self.permissions.ensure_parent_writable(dst)
            self._copy_dir(src, dst)

    def _rename_file(self, src: str, dst: str):
        normalized_dst = PathResolver.normalize_path(dst, allow_dir=True)
        if (
            normalized_dst.endswith("/")
            or normalized_dst in self.state.dirs
            or normalized_dst + "/" in self.state.dirs
        ):
            dir_path = PathResolver.normalize_path(normalized_dst, is_dir=True)
            if dir_path not in self.state.dirs:
                self.mkdir(dir_path, parents=True)
            normalized_dst = dir_path + os.path.basename(src.rstrip("/"))
        PathResolver.ensure_dir_parents(self.state, normalized_dst)
        self.state.files[normalized_dst] = self.state.files.pop(src)
        self.state.modes[normalized_dst] = self.state.modes.pop(src, 0o644)
        self.state.owners[normalized_dst] = self.state.owners.pop(src, 0)
        self.state.groups[normalized_dst] = self.state.groups.pop(src, 0)
        self.state.inodes[normalized_dst] = self.state.inodes.pop(
            src, self.state.next_inode()
        )
        self.persistence.save_if_needed()

    def _copy_file(self, src: str, dst: str):
        normalized_dst = PathResolver.normalize_path(dst, allow_dir=True)
        if (
            normalized_dst.endswith("/")
            or normalized_dst in self.state.dirs
            or normalized_dst + "/" in self.state.dirs
        ):
            dir_path = PathResolver.normalize_path(normalized_dst, is_dir=True)
            if dir_path not in self.state.dirs:
                self.mkdir(dir_path, parents=True)
            normalized_dst = dir_path + os.path.basename(src.rstrip("/"))
        PathResolver.ensure_dir_parents(self.state, normalized_dst)
        self.state.files[normalized_dst] = self.state.files[src]
        self.state.modes[normalized_dst] = self.state.modes.get(src, 0o644)
        uid, gid = self._get_active_context()
        self.state.owners[normalized_dst] = uid
        self.state.groups[normalized_dst] = gid
        self.persistence.save_if_needed()

    def _rename_dir(self, src: str, dst: str):
        src_dir = PathResolver.normalize_path(src, is_dir=True)
        dst_dir = PathResolver.normalize_path(dst, is_dir=True)
        if dst_dir == src_dir:
            return
        if dst_dir.startswith(src_dir):
            raise ValueError(
                f"Cannot rename directory into its own subdirectory: {dst_dir}"
            )
        self.mkdir(dst_dir, parents=True)
        self.state.owners[dst_dir] = self.state.owners.pop(src_dir, 0)
        self.state.groups[dst_dir] = self.state.groups.pop(src_dir, 0)
        self.state.inodes[dst_dir] = self.state.inodes.pop(
            src_dir, self.state.next_inode()
        )
        for directory in sorted(self.state.dirs):
            if directory.startswith(src_dir):
                relative = directory[len(src_dir) :]
                self.state.dirs.add(dst_dir + relative)
                self.state.modes[dst_dir + relative] = self.state.modes.pop(
                    directory, 0o755
                )
                self.state.owners[dst_dir + relative] = self.state.owners.pop(
                    directory, 0
                )
                self.state.groups[dst_dir + relative] = self.state.groups.pop(
                    directory, 0
                )
                self.state.inodes[dst_dir + relative] = self.state.inodes.pop(
                    directory, self.state.next_inode()
                )
                self.state.dirs.discard(directory)
        for file_path in list(self.state.files):
            if file_path.startswith(src_dir):
                relative = file_path[len(src_dir) :]
                self.state.files[dst_dir + relative] = self.state.files.pop(file_path)
                self.state.modes[dst_dir + relative] = self.state.modes.pop(
                    file_path, 0o644
                )
                self.state.owners[dst_dir + relative] = self.state.owners.pop(
                    file_path, 0
                )
                self.state.groups[dst_dir + relative] = self.state.groups.pop(
                    file_path, 0
                )
                self.state.inodes[dst_dir + relative] = self.state.inodes.pop(
                    file_path, self.state.next_inode()
                )
        self.delete(src_dir)
        self.persistence.save_if_needed()

    def _copy_dir(self, src: str, dst: str):
        src_dir = PathResolver.normalize_path(src, is_dir=True)
        dst_dir = PathResolver.normalize_path(dst, is_dir=True)
        if dst_dir == src_dir:
            return
        if dst_dir.startswith(src_dir):
            raise ValueError(
                f"Cannot copy directory into its own subdirectory: {dst_dir}"
            )
        self.mkdir(dst_dir, parents=True)
        uid, gid = self._get_active_context()
        self.state.owners[dst_dir] = uid
        self.state.groups[dst_dir] = gid
        for directory in sorted(self.state.dirs):
            if directory.startswith(src_dir):
                relative = directory[len(src_dir) :]
                self.state.dirs.add(dst_dir + relative)
                self.state.modes[dst_dir + relative] = self.state.modes.get(
                    directory, 0o755
                )
                self.state.owners[dst_dir + relative] = uid
                self.state.groups[dst_dir + relative] = gid
        for file_path, content in list(self.state.files.items()):
            if file_path.startswith(src_dir):
                relative = file_path[len(src_dir) :]
                self.state.files[dst_dir + relative] = content
                self.state.modes[dst_dir + relative] = self.state.modes.get(
                    file_path, 0o644
                )
                self.state.owners[dst_dir + relative] = uid
                self.state.groups[dst_dir + relative] = gid
        self.persistence.save_if_needed()

    # ------------------------------------------------------------------
    # Symlink support
    # ------------------------------------------------------------------

    def link(self, target: str, link_path: str):
        """Create a hard link at link_path pointing to target's inode."""
        target_resolved = PathResolver.normalize_path(target, allow_dir=True)
        link_path_resolved = PathResolver.normalize_path(link_path)

        if not self.exists(target_resolved):
            raise FileNotFoundError(f"No such file or directory: '{target}'")
        if self.is_dir(target_resolved):
            raise ValueError("Hard links to directories are not allowed")
        if self.exists(link_path_resolved):
            raise FileExistsError(f"File already exists: '{link_path}'")

        self.permissions.ensure_parent_writable(link_path_resolved)
        uid, gid = self._get_active_context()
        PathResolver.ensure_dir_parents(self.state, link_path_resolved, uid, gid)

        target_inode = self.state.inodes.get(target_resolved)
        if target_inode is None:
            target_inode = self.state.next_inode()
            self.state.inodes[target_resolved] = target_inode

        self.state.files[link_path_resolved] = self.state.files[target_resolved]
        self.state.modes[link_path_resolved] = self.state.modes.get(
            target_resolved, 0o644
        )
        self.state.inodes[link_path_resolved] = target_inode
        self.state.owners[link_path_resolved] = self.state.owners.get(
            target_resolved, uid
        )
        self.state.groups[link_path_resolved] = self.state.groups.get(
            target_resolved, gid
        )
        self.persistence.save_if_needed()

    def symlink(self, target: str, link_path: str):
        """Create a symbolic link at link_path pointing to target."""
        normalized = PathResolver.normalize_path(link_path)
        if normalized in self.state.files:
            raise FileExistsError(f"File already exists at {link_path}")
        if normalized in self.state.dirs or normalized + "/" in self.state.dirs:
            raise FileExistsError(f"Directory already exists at {link_path}")
        self.permissions.ensure_parent_writable(normalized)
        self.state.symlinks[normalized] = target
        self.state.modes[normalized] = 0o777
        self.state.inodes.setdefault(normalized, self.state.next_inode())
        uid, gid = self._get_active_context()
        self.state.owners.setdefault(normalized, uid)
        self.state.groups.setdefault(normalized, gid)
        self.persistence.save_if_needed()

    def readlink(self, path: str) -> Optional[str]:
        """Return the target of a symbolic link, or None if not a symlink."""
        normalized = PathResolver.normalize_path(path)
        return self.state.symlinks.get(normalized)

    def resolve_symlink(self, path: str, _depth: int = 0) -> str:
        """Resolve a symlink chain, returning the final path. Stops at depth 8."""
        if _depth > 8:
            return path  # avoid infinite loops
        if path in self.state.symlinks:
            target = self.state.symlinks[path]
            if not target.startswith("/"):
                # Relative target: resolve relative to link's directory
                parent = "/".join(path.rstrip("/").split("/")[:-1]) or "/"
                target = parent.rstrip("/") + "/" + target
            target = PathResolver.normalize_path(target, allow_dir=True)
            return self.resolve_symlink(target, _depth + 1)
        return path

    def du(self, path: str) -> int:
        """Return total byte count (disk usage) for a file or directory tree."""
        normalized = PathResolver.normalize_path(path, allow_dir=True)
        if normalized in self.state.files:
            return len(self.state.files[normalized])
        dir_path = normalized if normalized.endswith("/") else normalized + "/"
        if dir_path not in self.state.dirs and normalized not in self.state.dirs:
            return 0
        total = 0
        for f_path, content in self.state.files.items():
            if f_path.startswith(dir_path):
                total += len(content)
        return total
