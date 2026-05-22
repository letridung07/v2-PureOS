"""Curses compatibility layer for systems without native curses support (e.g., Windows)."""

import sys

try:
    import curses
    import curses.ascii
except (ImportError, ModuleNotFoundError):
    from unittest.mock import MagicMock

    curses = MagicMock()
    # Provide common constants used in the codebase
    curses.KEY_ENTER = 10
    curses.KEY_BACKSPACE = 263
    curses.KEY_DC = 330
    curses.KEY_LEFT = 260
    curses.KEY_RIGHT = 261
    curses.KEY_UP = 259
    curses.KEY_DOWN = 258
    curses.KEY_HOME = 262
    curses.KEY_END = 360
    curses.KEY_PPAGE = 339
    curses.KEY_NPAGE = 338
    curses.KEY_RESIZE = 410
    curses.KEY_F1 = 265
    curses.A_REVERSE = 262144

    curses.ascii = MagicMock()
    curses.ascii.isprint = lambda x: 32 <= x <= 126

    # Optional: Mock wrapper if anyone calls it
    def _wrapper(func, *args, **kwargs):
        print("Warning: curses is not available on this system.")
        return None

    curses.wrapper = _wrapper
