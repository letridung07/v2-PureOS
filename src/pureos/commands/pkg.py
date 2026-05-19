import urllib.request
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
            return self._install(url, name)
        elif subcommand == "list":
            return self._list()
        elif subcommand == "remove":
            if len(parts) < 3:
                print("Usage: pkg remove <name>")
                return False
            name = parts[2]
            return self._remove(name)
        else:
            print(f"Unknown subcommand: {subcommand}")
            return False

    def _install(self, url, name):
        try:
            print(f"Fetching package from {url}...")
            with urllib.request.urlopen(url) as response:
                content = response.read().decode("utf-8")
            
            pkg_dir = "/usr/lib/pureos/packages/"
            if not self.kernel.fs.exists(pkg_dir):
                self.kernel.fs.mkdir(pkg_dir)
            
            file_path = f"{pkg_dir}{name}.py"
            self.kernel.fs.write(file_path, content)
            
            print(f"Installing {name}...")
            success = self.kernel.shell.registry.load_from_vfs(file_path)
            if success:
                print(f"Successfully installed and registered '{name}'.")
                return True
            else:
                print(f"Failed to register commands from '{name}'. Check the script content.")
                return False
        except Exception as e:
            print(f"Error installing package: {e}")
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
                    # list returns full paths, extract filename
                    name = p.split("/")[-1].replace(".py", "")
                    print(f" - {name}")
        return True

    def _remove(self, name):
        file_path = f"/usr/lib/pureos/packages/{name}.py"
        if not self.kernel.fs.exists(file_path):
            print(f"Package '{name}' not found.")
            return False
        
        self.kernel.fs.delete(file_path)
        print(f"Package '{name}' removed from VFS. Note: Command will remain registered until restart.")
        return True
