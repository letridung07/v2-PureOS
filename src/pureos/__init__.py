"""v2-PureOS package

Small collection of OS-like components.
"""

from .kernel import Kernel

__version__ = "0.1.0"


def run(shell: bool = False):
    """Initialize kernel components and optionally run the interactive shell."""
    k = Kernel()
    k.initialize()
    if shell:
        k.shell.run()
    return k
