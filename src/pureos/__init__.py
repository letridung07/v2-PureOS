"""v2-PureOS package

Small collection of OS-like components.
"""

from .core import Kernel, __version__, run

# Ensure subpackages are available as attributes for mock.patch and general discovery
from . import core, drivers, subsystems, shell

__all__ = ["Kernel", "__version__", "run", "core", "drivers", "subsystems", "shell"]
