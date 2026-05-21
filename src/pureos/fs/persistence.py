import json
import os
import shutil
import time
import logging
from .state import FSState
from .path import PathResolver


class FSPersistence:
    def __init__(self, state: FSState):
        self.state = state
        self.logger = logging.getLogger("pureos.fs.persistence")

    def save_if_needed(self):
        if self.state.backing_path:
            self.save()

    def save(self):
        if not self.state.backing_path:
            return
        dirpath = os.path.dirname(self.state.backing_path)
        if dirpath and not os.path.exists(dirpath):
            os.makedirs(dirpath, exist_ok=True)
        temp_path = f"{self.state.backing_path}.tmp"
        payload = {
            "files": self.state.files,
            "dirs": sorted(self.state.dirs),
            "modes": {path: mode for path, mode in self.state.modes.items()},
            "owners": {path: uid for path, uid in self.state.owners.items()},
            "groups": {path: gid for path, gid in self.state.groups.items()},
            "symlinks": self.state.symlinks,
            "inodes": self.state.inodes,
            "inode_counter": self.state._inode_counter,
            "sticky_bits": sorted(self.state.sticky_bits),
        }
        # Write to a temp file and fsync to reduce risk of corruption on crash
        with open(temp_path, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2)
            f.flush()
            try:
                os.fsync(f.fileno())
            except OSError:
                # Best-effort; ignore if fsync is not supported
                pass

        # Attempt to create a backup of the existing backing file (best-effort)
        bak_path = f"{self.state.backing_path}.bak"
        try:
            if os.path.exists(self.state.backing_path):
                shutil.copy2(self.state.backing_path, bak_path)
        except Exception as exc:
            self.logger.debug("FSPersistence: could not create backup: %s", exc)

        # Atomically replace the backing file with the temp file
        try:
            os.replace(temp_path, self.state.backing_path)
            # Try to fsync the directory to ensure the rename is committed
            dir_to_sync = dirpath if dirpath else "."
            try:
                dirfd = os.open(dir_to_sync, os.O_RDONLY)
                try:
                    os.fsync(dirfd)
                finally:
                    os.close(dirfd)
            except Exception:
                # Ignore directory fsync errors; best-effort
                pass
        except Exception:
            # Cleanup temp file on failure
            try:
                if os.path.exists(temp_path):
                    os.remove(temp_path)
            except Exception:
                pass
            raise

    def load(self):
        """Load persisted filesystem state from the backing store."""
        if not self.state.backing_path or not os.path.exists(self.state.backing_path):
            return
        try:
            self._load()
        except (OSError, ValueError, json.JSONDecodeError):
            # Attempt recovery from temp or backup files before falling back
            temp_path = f"{self.state.backing_path}.tmp"
            bak_path = f"{self.state.backing_path}.bak"
            recovered = False
            # Try temp file
            try:
                if os.path.exists(temp_path):
                    with open(temp_path, "r", encoding="utf-8") as f:
                        json.load(f)  # validate JSON
                    os.replace(temp_path, self.state.backing_path)
                    self.logger.warning(
                        "FSPersistence: recovered backing from temp file"
                    )
                    self._load()
                    recovered = True
            except Exception:
                recovered = False

            # Try backup if not recovered
            if not recovered:
                try:
                    if os.path.exists(bak_path):
                        with open(bak_path, "r", encoding="utf-8") as f:
                            json.load(f)
                        os.replace(bak_path, self.state.backing_path)
                        self.logger.warning(
                            "FSPersistence: recovered backing from backup"
                        )
                        self._load()
                        recovered = True
                except Exception:
                    recovered = False

            if not recovered:
                # Move corrupted file out of the way for forensics, then reset state
                try:
                    ts = int(time.time())
                    corrupt_path = f"{self.state.backing_path}.corrupt.{ts}"
                    os.replace(self.state.backing_path, corrupt_path)
                    self.logger.error(
                        "FSPersistence: backing file corrupted, moved to %s",
                        corrupt_path,
                    )
                except Exception:
                    # best-effort: ignore if move fails
                    pass
                self.state.files = {}
                self.state.dirs = {"/"}
                self.state.modes = {"/": 0o755}
                self.state.owners = {"/": 0}
                self.state.groups = {"/": 0}

    def _load(self):
        if os.path.exists(self.state.backing_path):
            with open(self.state.backing_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            self.state.files = {}
            self.state.dirs = {"/"}
            self.state.modes = {"/": 0o755}
            self.state.owners = {"/": 0}
            self.state.groups = {"/": 0}
            if isinstance(data, dict) and all(
                isinstance(v, str) for v in data.values()
            ):
                for path, content in data.items():
                    normalized = PathResolver.normalize_path(
                        path, is_dir=path.endswith("/")
                    )
                    if normalized.endswith("/"):
                        self.state.dirs.add(normalized)
                        self.state.modes.setdefault(normalized, 0o755)
                    else:
                        self.state.files[normalized] = content
                        self.state.modes.setdefault(normalized, 0o644)
                    PathResolver.ensure_dir_parents(self.state, normalized)
            else:
                self.state.files = {
                    PathResolver.normalize_path(path): content
                    for path, content in data.get("files", {}).items()
                }
                self.state.dirs = {
                    PathResolver.normalize_path(path, is_dir=True)
                    for path in data.get("dirs", [])
                }
                self.state.dirs.add("/")
                self.state.modes = {
                    PathResolver.normalize_path(path, allow_dir=True): mode
                    for path, mode in data.get("modes", {}).items()
                }
                self.state.modes.setdefault("/", 0o755)
                self.state.owners = {
                    PathResolver.normalize_path(path, allow_dir=True): uid
                    for path, uid in data.get("owners", {}).items()
                }
                self.state.groups = {
                    PathResolver.normalize_path(path, allow_dir=True): gid
                    for path, gid in data.get("groups", {}).items()
                }
                # Restore symlinks, inodes, sticky_bits
                self.state.symlinks = {
                    PathResolver.normalize_path(p): t
                    for p, t in data.get("symlinks", {}).items()
                }
                self.state.inodes = {
                    PathResolver.normalize_path(path, allow_dir=True): ino
                    for path, ino in data.get("inodes", {}).items()
                }
                self.state._inode_counter = data.get("inode_counter", 2)
                self.state.sticky_bits = set(
                    PathResolver.normalize_path(p, allow_dir=True)
                    for p in data.get("sticky_bits", [])
                )
                for path in self.state.files:
                    PathResolver.ensure_dir_parents(self.state, path)
                    self.state.modes.setdefault(path, 0o644)
                for path in self.state.dirs:
                    self.state.modes.setdefault(path, 0o755)
            # Ensure default ownership for any entries that lack them
            for path in self.state.files:
                self.state.owners.setdefault(path, 0)
                self.state.groups.setdefault(path, 0)
            for path in self.state.dirs:
                self.state.owners.setdefault(path, 0)
                self.state.groups.setdefault(path, 0)
            self.state.owners.setdefault("/", 0)
            self.state.groups.setdefault("/", 0)
        else:
            self.state.files = {}
            self.state.dirs = {"/"}
            self.state.modes = {"/": 0o755}
            self.state.owners = {"/": 0}
            self.state.groups = {"/": 0}
