import curses


class StatusBar:
    def __init__(self, shell):
        self._shell = shell

    def get_text(self):
        username = "root"
        try:
            if (
                self._shell.kernel
                and self._shell.kernel.users
                and self._shell.kernel.users.current_user
            ):
                username = self._shell.kernel.users.current_user.username
        except Exception:
            pass
        exit_code = self._shell._last_exit_code
        code_str = f"[{exit_code}]" if exit_code != 0 else ""
        cwd = self._shell.cwd
        return f" {username}@pureos:{cwd} {code_str}"

    def render(self, win, term_width):
        text = self.get_text()[: term_width - 1]
        win.erase()
        try:
            win.addstr(
                0, 0, text.ljust(term_width - 1)[: term_width - 1], curses.A_REVERSE
            )
        except Exception:
            pass
        win.noutrefresh()
