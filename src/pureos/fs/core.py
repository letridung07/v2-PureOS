from typing import Optional, List, Dict, Set
from .state import FSState
from .path import PathResolver
from .permissions import FSPermissions
from .persistence import FSPersistence
from .operations import FSOperations


class VirtualFS:
    def __init__(self, backing_path: Optional[str] = None, kernel=None):
        self.kernel = kernel
        self.state = FSState(backing_path)
        self.permissions = FSPermissions(self.state, kernel=kernel)
        self.persistence = FSPersistence(self.state)
        self.operations = FSOperations(self.state, self.permissions, self.persistence)
        if backing_path:
            self.persistence.load()

    @property
    def files(self) -> Dict[str, str]:
        return self.state.files

    @property
    def dirs(self) -> Set[str]:
        return self.state.dirs

    @property
    def modes(self) -> Dict[str, int]:
        return self.state.modes

    @property
    def symlinks(self) -> Dict[str, str]:
        return self.state.symlinks

    def has_content(self) -> bool:
        return self.state.has_content()

    def load(self):
        self.persistence.load()

    def format(self):
        self.operations.format()

    def normalize_path(
        self, path: str, is_dir: bool = False, allow_dir: bool = False
    ) -> str:
        return PathResolver.normalize_path(path, is_dir=is_dir, allow_dir=allow_dir)

    def mkdir(self, path: str, parents: bool = True):
        self.operations.mkdir(path, parents)

    def write(self, path: str, content: str):
        self.operations.write(path, content)

    def append(self, path: str, content: str):
        self.operations.append(path, content)

    def read(self, path: str) -> Optional[str]:
        return self.operations.read(path)

    def read_lines(self, path: str) -> Optional[List[str]]:
        return self.operations.read_lines(path)

    def list(self, prefix: str = "/", recursive: bool = False) -> List[str]:
        return self.operations.list(prefix, recursive)

    def find(self, prefix: str = "/") -> List[str]:
        return self.operations.find(prefix)

    def exists(self, path: str) -> bool:
        return self.operations.exists(path)

    def is_dir(self, path: str) -> bool:
        return self.operations.is_dir(path)

    def is_file(self, path: str) -> bool:
        return self.operations.is_file(path)

    def stat(self, path: str) -> Optional[Dict[str, object]]:
        return self.operations.stat(path)

    def chmod(self, path: str, mode: int):
        self.operations.chmod(path, mode)

    def delete(self, path: str):
        self.operations.delete(path)

    def rename(self, src: str, dst: str):
        self.operations.rename(src, dst)

    def copy(self, src: str, dst: str):
        self.operations.copy(src, dst)

    def symlink(self, target: str, link_path: str):
        self.operations.symlink(target, link_path)

    def readlink(self, path: str):
        return self.operations.readlink(path)

    def resolve_symlink(self, path: str) -> str:
        return self.operations.resolve_symlink(path)

    def du(self, path: str) -> int:
        return self.operations.du(path)
