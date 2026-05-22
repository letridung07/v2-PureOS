import io
import os
import tarfile
import time
from typing import Dict, List, Optional, Union

from .base import FileCommand


class TarCommand(FileCommand):
    name = "tar"
    usage = "tar [-c|-x|-t] [-z] [-v] [-C <dir>] -f <archive> [paths...]"
    description = "Create, extract, or list files in a tar archive."

    def execute(
        self,
        parts: List[str],
        input_data=None,
        capture_output=False,
        raw_line=None,
    ):
        options: Dict[str, Union[bool, str, None]] = {
            "create": False,
            "extract": False,
            "list": False,
            "gzip": False,
            "verbose": False,
            "file": None,
            "directory": None,
        }
        paths = []

        args = parts[1:]
        i = 0
        while i < len(args):
            arg = args[i]
            if arg == "-C":
                if i + 1 >= len(args):
                    print("tar: option requires an argument -- C")
                    return False
                options["directory"] = args[i + 1]
                i += 1
            elif arg.startswith("-") and len(arg) > 1:
                has_f = False
                for char in arg[1:]:
                    if char == "c":
                        options["create"] = True
                    elif char == "x":
                        options["extract"] = True
                    elif char == "t":
                        options["list"] = True
                    elif char == "z":
                        options["gzip"] = True
                    elif char == "v":
                        options["verbose"] = True
                    elif char == "f":
                        has_f = True
                    else:
                        print(f"tar: invalid option -- {char}")
                        return False
                if has_f:
                    if i + 1 >= len(args):
                        print("tar: option requires an argument -- f")
                        return False
                    options["file"] = args[i + 1]
                    i += 1
            else:
                paths.append(arg)
            i += 1

        # Validation
        ops = [bool(options["create"]), bool(options["extract"]), bool(options["list"])]
        if sum(ops) != 1:
            print("tar: You must specify exactly one of -c, -x, or -t")
            return False

        if not options["file"]:
            print("tar: Archive file must be specified with -f")
            return False

        # Resolve archive file path before changing CWD
        options["file"] = self.resolve_path(str(options["file"]))

        old_cwd = self.kernel.shell.cwd
        try:
            if options["directory"]:
                target_dir = self.resolve_path(
                    str(options["directory"]), allow_dir=True
                )
                if not self.kernel.fs.exists(target_dir) or not self.kernel.fs.is_dir(
                    target_dir
                ):
                    print(f"tar: {options['directory']}: No such directory")
                    return False
                self.kernel.shell.cwd = target_dir

            if options["create"]:
                if not paths:
                    print("tar: No files specified for creation")
                    return False
                return self._create_archive(options, paths)
            elif options["list"]:
                return self._list_archive(options)
            elif options["extract"]:
                return self._extract_archive(options)
        finally:
            self.kernel.shell.cwd = old_cwd

        return False

    def _add_to_tar(self, tar, path, base_path, verbose):
        base_parent = os.path.dirname(base_path.rstrip("/"))
        if base_parent == "/":
            arcname = path.lstrip("/")
        else:
            arcname = path[len(base_parent) :].lstrip("/")

        arcname = arcname.rstrip("/")
        if not arcname:
            return

        tarinfo = tarfile.TarInfo(name=arcname)
        tarinfo.mtime = int(time.time())
        tarinfo.uid = self.kernel.fs.state.owners.get(path, 0)
        tarinfo.gid = self.kernel.fs.state.groups.get(path, 0)

        if self.kernel.fs.is_dir(path):
            tarinfo.type = tarfile.DIRTYPE
            tarinfo.mode = self.kernel.fs.state.modes.get(path, 0o755)
            tar.addfile(tarinfo)
            if verbose:
                print(arcname + "/")
        else:
            tarinfo.type = tarfile.REGTYPE
            tarinfo.mode = self.kernel.fs.state.modes.get(path, 0o644)
            content = self.kernel.fs.read(path) or ""
            content_bytes = content.encode("latin-1")
            tarinfo.size = len(content_bytes)
            tar.addfile(tarinfo, fileobj=io.BytesIO(content_bytes))
            if verbose:
                print(arcname)

    def _create_archive(self, options, paths):
        bio = io.BytesIO()
        mode = "w:gz" if options["gzip"] else "w"

        try:
            with tarfile.open(fileobj=bio, mode=mode) as tar:
                for path in paths:
                    abs_path = self.resolve_path(path, allow_dir=True)
                    if not self.kernel.fs.exists(abs_path):
                        print(f"tar: {path}: No such file or directory")
                        return False

                    if self.kernel.fs.is_dir(abs_path):
                        self._add_to_tar(tar, abs_path, abs_path, options["verbose"])
                        for item in self.kernel.fs.find(abs_path):
                            self._add_to_tar(tar, item, abs_path, options["verbose"])
                    else:
                        self._add_to_tar(tar, abs_path, abs_path, options["verbose"])
        except Exception as exc:
            print(f"tar: failed to create archive: {exc}")
            return False

        archive_path = self.resolve_path(options["file"])
        try:
            archive_data = bio.getvalue().decode("latin-1")
            self.kernel.fs.write(archive_path, archive_data)
        except Exception as exc:
            print(f"tar: failed to write archive file: {exc}")
            return False

        return True

    def _list_archive(self, options):
        archive_path = self.resolve_path(options["file"])
        if not self.kernel.fs.exists(archive_path):
            print(f"tar: {options['file']}: No such file or directory")
            return False

        try:
            archive_data = self.kernel.fs.read(archive_path) or ""
            bio = io.BytesIO(archive_data.encode("latin-1"))
            mode = "r:gz" if options["gzip"] else "r"
            with tarfile.open(fileobj=bio, mode=mode) as tar:
                for member in tar.getmembers():
                    name = member.name
                    if member.isdir() and not name.endswith("/"):
                        name += "/"
                    print(name)
        except Exception as exc:
            print(f"tar: failed to list archive: {exc}")
            return False
        return True

    def _extract_archive(self, options):
        archive_path = self.resolve_path(options["file"])
        if not self.kernel.fs.exists(archive_path):
            print(f"tar: {options['file']}: No such file or directory")
            return False

        try:
            archive_data = self.kernel.fs.read(archive_path) or ""
            bio = io.BytesIO(archive_data.encode("latin-1"))
            mode = "r:gz" if options["gzip"] else "r"
            with tarfile.open(fileobj=bio, mode=mode) as tar:
                for member in tar.getmembers():
                    # Strip leading slashes to prevent arbitrary path write/traversal
                    name = member.name.lstrip("/")
                    # Resolve destination relative to CWD
                    dst_path = self.resolve_path(name, allow_dir=member.isdir())

                    if member.isdir():
                        self.kernel.fs.mkdir(dst_path, parents=True)
                        self.kernel.fs.chmod(dst_path, member.mode)
                        try:
                            self.kernel.fs.chown(dst_path, member.uid)
                            self.kernel.fs.chgrp(dst_path, member.gid)
                        except PermissionError:
                            pass
                        if options["verbose"]:
                            print(name + "/")
                    else:
                        f = tar.extractfile(member)
                        if f is not None:
                            content_bytes = f.read()
                            content = content_bytes.decode("latin-1")
                            self.kernel.fs.write(dst_path, content)
                            self.kernel.fs.chmod(dst_path, member.mode)
                            try:
                                self.kernel.fs.chown(dst_path, member.uid)
                                self.kernel.fs.chgrp(dst_path, member.gid)
                            except PermissionError:
                                pass
                            if options["verbose"]:
                                print(name)
        except Exception as exc:
            print(f"tar: failed to extract archive: {exc}")
            return False
        return True
