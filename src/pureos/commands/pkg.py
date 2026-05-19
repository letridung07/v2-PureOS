import urllib.request
import re
from .base import Command


class PkgCommand(Command):
    name = "pkg"
    usage = "pkg [install <url> <name> | list | remove <name>]"
    description = "Package manager for dynamic commands."

    def execute(self, parts, input_data=None, capture_output=False, raw_line=None):
        if len(parts) < 2:
            print(f"Usage: {self.usage}")
            return False

        subcommand = parts[1]

        if subcommand == "install":
            if len(parts) < 4:
                print("Usage: pkg install <url> <name>")
                return False
            url = parts[2]
            name = parts[3]
            if not self._is_valid_name(name):
                print(
                    f"Error: Invalid package name '{name}'. "
                    "Use alphanumeric characters only."
                )
                return False

            # Simple URL scheme validation
            if not (url.startswith("http://") or url.startswith("https://")):
                print("Error: URL must start with http:// or https://")
                return False

            return self._install(url, name)
        elif subcommand == "list":
            return self._list()
        elif subcommand == "remove":
            if len(parts) < 3:
                print("Usage: pkg remove <name>")
                return False
            name = parts[2]
            if not self._is_valid_name(name):
                print(f"Error: Invalid package name '{name}'.")
                return False
            return self._remove(name)
        else:
            print(f"Unknown subcommand: {subcommand}")
            return False

    def _is_valid_name(self, name):
        # Prevent path traversal and restrict to safe filenames
        return bool(re.match(r"^[a-zA-Z0-9_\-]+$", name))

    def _install(self, url, name):
        file_path = f"/usr/lib/pureos/packages/{name}.py"
        try:
            print(f"Fetching package from {url}...")
            # Set a timeout for the network request
            with urllib.request.urlopen(url, timeout=10) as response:
                content = response.read().decode("utf-8")

            pkg_dir = "/usr/lib/pureos/packages/"
            if not self.kernel.fs.exists(pkg_dir):
                self.kernel.fs.mkdir(pkg_dir, parents=True)

            self.kernel.fs.write(file_path, content)

            print(f"Installing {name}...")
            success = self.kernel.shell.registry.load_from_vfs(file_path)
            if success:
                print(f"Successfully installed and registered '{name}'.")
                return True
            else:
                print(
                    f"Failed to register commands from '{name}'. "
                    "Check the script content. Cleaning up..."
                )
                self.kernel.fs.delete(file_path)
                return False
        except Exception as e:
            print(f"Error installing package: {e}")
            if self.kernel.fs.exists(file_path):
                self.kernel.fs.delete(file_path)
            return False

    def _list(self):
        pkg_dir = "/usr/lib/pureos/packages/"
        if not self.kernel.fs.exists(pkg_dir):
            print("No packages installed.")
            return True

        pkgs = self.kernel.fs.list(pkg_dir)
        if not pkgs:
            print("No packages installed.")
        else:
            print("Installed packages:")
            for p in pkgs:
                if p.endswith(".py"):
                    pkg_name = p.split("/")[-1].replace(".py", "")
                    print(f" - {pkg_name}")
        return True

    def _remove(self, name):
        file_path = f"/usr/lib/pureos/packages/{name}.py"
        if not self.kernel.fs.exists(file_path):
            print(f"Package '{name}' not found.")
            return False

        # Deregister commands first
        self.kernel.shell.registry.unregister_from_vfs(file_path)

        # Then delete the file
        self.kernel.fs.delete(file_path)
        print(f"Package '{name}' removed successfully.")
        return True
