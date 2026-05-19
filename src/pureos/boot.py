"""Boot and initialization routines for v2-PureOS."""


def run_boot_sequence(kernel):
    """Execute early boot tasks like filesystem initialization."""
    kernel.logger.info("Kernel: executing boot sequence")
    if kernel.config.format_on_boot or not kernel.fs.has_content():
        print("Kernel: formatting filesystem...")
        kernel.fs.format()
    else:
        _ensure_default_files(kernel.fs)

    _load_packages(kernel)


def _ensure_default_files(fs):
    """Ensure essential configuration files exist in the filesystem."""
    if "/etc/motd" not in fs.files:
        if not fs.exists("/etc/"):
            fs.mkdir("/etc/")
        fs.write("/etc/motd", "Welcome to v2-PureOS")
    if "/etc/pureosrc" not in fs.files:
        if not fs.exists("/etc/"):
            fs.mkdir("/etc/")
        fs.write(
            "/etc/pureosrc",
            "alias ll ls -l\n" "alias la ls\n" "alias grep grep -i\n",
        )


def _load_packages(kernel):
    """Load dynamically installed packages from the VirtualFS."""
    pkg_dir = "/usr/lib/pureos/packages/"
    if kernel.fs.exists(pkg_dir):
        pkgs = kernel.fs.list(pkg_dir)
        for p in pkgs:
            if p.endswith(".py"):
                file_path = p
                kernel.shell.registry.load_from_vfs(file_path)
