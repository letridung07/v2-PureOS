"""Boot and initialization routines for v2-PureOS."""


def run_boot_sequence(kernel):
    """Execute early boot tasks like filesystem initialization."""
    kernel.logger.info("Kernel: executing boot sequence")
    if kernel.config.format_on_boot or not kernel.fs.has_content():
        print("Kernel: formatting filesystem...")
        kernel.fs.format()

    _ensure_default_files(kernel.fs)
    _load_packages(kernel)


def _ensure_default_files(fs):
    """Ensure essential configuration files exist in the filesystem."""
    if not fs.exists("/etc/"):
        fs.mkdir("/etc/")

    if "/etc/motd" not in fs.files:
        fs.write("/etc/motd", "Welcome to v2-PureOS")

    if "/etc/pureosrc" not in fs.files:
        fs.write(
            "/etc/pureosrc",
            "alias ll ls -l\n" "alias la ls\n" "alias grep grep -i\n",
        )

    # Add default web content
    if not fs.exists("/var/www/html/"):
        fs.mkdir("/var/www/html/", parents=True)

    if "/var/www/html/index.html" not in fs.files:
        html_content = (
            "<html>\n"
            "<head><title>v2-PureOS</title></head>\n"
            "<body>\n"
            "<h1>Welcome to v2-PureOS</h1>\n"
            "<p>The HTTP server is running successfully!</p>\n"
            "</body>\n"
            "</html>"
        )
        fs.write("/var/www/html/index.html", html_content)


def _load_packages(kernel):
    """Load dynamically installed packages from the VirtualFS."""
    kernel.package_manager.load_all_packages()
