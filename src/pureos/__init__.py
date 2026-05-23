"""v2-PureOS package

Small collection of OS-like components.
"""

from typing import Optional

from .core.kernel import Kernel

__version__ = "0.1.0"


def run(shell: bool = False, desktop: bool = False, config: Optional[dict] = None):
    """Initialize kernel components and run the interactive shell or TUI desktop."""
    k = Kernel(config=config)
    k.initialize()
    if desktop:
        from .shell.desktop.desktop import Desktop

        Desktop(k).run()
    elif shell:
        k.shell.run()
    return k
