"""Package manager subsystem for v2-PureOS."""

import urllib.request
from typing import List


class PackageManager:
    """Manages dynamic package loading, installation, and uninstallation."""

    def __init__(self, kernel):
        self.kernel = kernel
        self.package_dir = "/usr/lib/pureos/packages/"

    def is_valid_name(self, name: str) -> bool:
        """Check if package name is a valid Python identifier."""
        return name.isidentifier() and not name.startswith("_")

    def install(self, url: str, name: str) -> bool:
        """Download package from URL, save to VirtualFS, and load into command registry."""
        file_path = f"{self.package_dir}{name}.py"
        try:
            print(f"Fetching package from {url}...")
            # Set a timeout for the network request
            with urllib.request.urlopen(url, timeout=10) as response:
                content = response.read().decode("utf-8")

            if not self.kernel.fs.exists(self.package_dir):
                self.kernel.fs.mkdir(self.package_dir, parents=True)

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

    def list(self) -> List[str]:
        """List all installed package names."""
        if not self.kernel.fs.exists(self.package_dir):
            return []

        pkgs = self.kernel.fs.list(self.package_dir)
        names = []
        for p in pkgs:
            if p.endswith(".py"):
                pkg_name = p.split("/")[-1].replace(".py", "")
                names.append(pkg_name)
        return names

    def remove(self, name: str) -> bool:
        """Deregister dynamic package commands and remove the package script from VFS."""
        file_path = f"{self.package_dir}{name}.py"
        if not self.kernel.fs.exists(file_path):
            print(f"Package '{name}' not found.")
            return False

        # Deregister commands first
        self.kernel.shell.registry.unregister_from_vfs(file_path)

        # Then delete the file
        self.kernel.fs.delete(file_path)
        print(f"Package '{name}' removed successfully.")
        return True

    def load_all_packages(self):
        """Load all dynamic packages from the VirtualFS on boot."""
        if self.kernel.fs.exists(self.package_dir):
            # Sort packages alphabetically to ensure deterministic loading order
            pkgs = sorted(self.kernel.fs.list(self.package_dir))
            for p in pkgs:
                if p.endswith(".py"):
                    self.kernel.shell.registry.load_from_vfs(p)
