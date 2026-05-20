import sys
import importlib.abc
import importlib.util


class VFSImporter(importlib.abc.MetaPathFinder, importlib.abc.Loader):
    """
    A custom importer that allows Python modules to be imported directly from the
    VirtualFS. It hooks into sys.meta_path to resolve modules under
    'pureos_vfs.*'.
    """

    def __init__(self, fs):
        self.fs = fs
        self.prefix = "pureos_vfs"

    def _get_vfs_path(self, fullname):
        parts = fullname.split(".")
        if len(parts) > 1 and parts[1] == "packages":
            # pureos_vfs.packages.mycmd -> /usr/lib/pureos/packages/mycmd
            return "/usr/lib/pureos/packages/" + "/".join(parts[2:])
        # pureos_vfs.mod -> /usr/lib/python/mod
        return "/usr/lib/python/" + "/".join(parts[1:])

    def find_spec(self, fullname, path, target=None):
        if fullname == self.prefix:
            return importlib.util.spec_from_loader(fullname, self, is_package=True)

        if not fullname.startswith(self.prefix + "."):
            return None

        vfs_path = self._get_vfs_path(fullname)

        # Check for package (directory with __init__.py)
        init_path = vfs_path + "/__init__.py"
        if self.fs.exists(init_path):
            return importlib.util.spec_from_loader(fullname, self, is_package=True)

        # Check for single file module
        file_path = vfs_path + ".py"
        if self.fs.exists(file_path):
            return importlib.util.spec_from_loader(fullname, self, is_package=False)

        # Check for directory without __init__.py (treat as namespace package)
        if self.fs.exists(vfs_path) and self.fs.is_dir(vfs_path):
            return importlib.util.spec_from_loader(fullname, self, is_package=True)

        # Special case for 'pureos_vfs.packages' if it's being requested
        # but doesn't exist yet.
        # It will be created when we try to list or write to it, but the
        # importer might be called first.
        if fullname == self.prefix + ".packages":
            return importlib.util.spec_from_loader(fullname, self, is_package=True)

        return None

    def exec_module(self, module):
        fullname = module.__name__
        if fullname == self.prefix or fullname == self.prefix + ".packages":
            module.__path__ = []  # Mark as a namespace-like package
            return

        vfs_path = self._get_vfs_path(fullname)

        if self.fs.exists(vfs_path + "/__init__.py"):
            source_path = vfs_path + "/__init__.py"
        elif self.fs.exists(vfs_path + ".py"):
            source_path = vfs_path + ".py"
        else:
            # Must be a namespace package (directory without __init__.py)
            module.__path__ = []
            return

        source = self.fs.read(source_path)
        if source is None:
            raise ImportError(f"Could not read source from VFS: {source_path}")

        # Inject common utilities for backward compatibility
        from pureos.commands.base import Command
        import json
        import re
        import math

        module.__dict__.setdefault("Command", Command)
        module.__dict__.setdefault("json", json)
        module.__dict__.setdefault("re", re)
        module.__dict__.setdefault("math", math)

        code = compile(source, f"vfs://{source_path}", "exec")
        # Ensure the module has a __file__ attribute that makes sense
        module.__file__ = f"vfs://{source_path}"
        exec(code, module.__dict__)

    @classmethod
    def register(cls, fs):
        # Check if already registered for this FS
        for importer in sys.meta_path:
            if isinstance(importer, cls) and importer.fs == fs:
                return importer

        importer = cls(fs)
        sys.meta_path.insert(0, importer)
        return importer

    @classmethod
    def unregister(cls, fs):
        to_remove = []
        for importer in sys.meta_path:
            if isinstance(importer, cls) and importer.fs == fs:
                to_remove.append(importer)

        for importer in to_remove:
            sys.meta_path.remove(importer)
