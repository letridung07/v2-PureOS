import json
import os
from .state import FSState
from .path import PathResolver


class FSPersistence:
    def __init__(self, state: FSState):
        self.state = state

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
        with open(temp_path, "w", encoding="utf-8") as f:
            json.dump(
                {
                    "files": self.state.files,
                    "dirs": sorted(self.state.dirs),
                    "modes": {path: mode for path, mode in self.state.modes.items()},
                    "owners": {path: uid for path, uid in self.state.owners.items()},
                    "groups": {path: gid for path, gid in self.state.groups.items()},
                },
                f,
                indent=2,
            )
        os.replace(temp_path, self.state.backing_path)

    def load(self):
        """Load persisted filesystem state from the backing store."""
        if not self.state.backing_path or not os.path.exists(self.state.backing_path):
            return
        try:
            self._load()
        except (OSError, ValueError, json.JSONDecodeError):
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
