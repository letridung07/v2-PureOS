__version__ = "0.1.0"

from typing import Optional


def run(shell: bool = False, desktop: bool = False, config: Optional[dict] = None):
    """Initialize kernel components and run the interactive shell or TUI desktop."""
    k = Kernel(config=config)
    k.initialize()
    if desktop:
        from ..shell.desktop.desktop import Desktop

        Desktop(k).run()
    elif shell:
        k.shell.run()
    return k


from .kernel import Kernel
from .config import Config

__all__ = ["Kernel", "Config", "__version__", "run"]
