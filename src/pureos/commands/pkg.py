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
        pm = self.kernel.package_manager

        if subcommand == "install":
            if len(parts) < 4:
                print("Usage: pkg install <url> <name>")
                return False
            url = parts[2]
            name = parts[3]
            if not pm.is_valid_name(name):
                print(
                    f"Error: Invalid package name '{name}'. "
                    "Use alphanumeric characters only."
                )
                return False

            # Simple URL scheme validation
            if not (url.startswith("http://") or url.startswith("https://")):
                print("Error: URL must start with http:// or https://")
                return False

            return pm.install(url, name)
        elif subcommand == "list":
            pkgs = pm.list()
            if not pkgs:
                print("No packages installed.")
            else:
                print("Installed packages:")
                for p in pkgs:
                    print(f" - {p}")
            return True
        elif subcommand == "remove":
            if len(parts) < 3:
                print("Usage: pkg remove <name>")
                return False
            name = parts[2]
            if not pm.is_valid_name(name):
                print(f"Error: Invalid package name '{name}'.")
                return False
            return pm.remove(name)
        else:
            print(f"Unknown subcommand: {subcommand}")
            return False
