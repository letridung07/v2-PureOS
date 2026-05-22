from unittest.mock import MagicMock
from pureos.desktop.statusbar import StatusBar


class TestStatusBar:
    def test_get_text_default(self):
        shell = MagicMock()
        shell.kernel = None
        shell._last_exit_code = 0
        shell.cwd = "/"
        sb = StatusBar(shell)
        assert "root@pureos:/" in sb.get_text()

    def test_get_text_with_user(self):
        shell = MagicMock()
        shell.kernel.users.current_user.username = "alice"
        shell._last_exit_code = 0
        shell.cwd = "/home/alice"
        sb = StatusBar(shell)
        assert "alice@pureos:/home/alice" in sb.get_text()

    def test_get_text_with_exit_code(self):
        shell = MagicMock()
        shell.kernel = None
        shell._last_exit_code = 127
        shell.cwd = "/"
        sb = StatusBar(shell)
        assert "[127]" in sb.get_text()

    def test_render(self):
        shell = MagicMock()
        shell.kernel = None
        shell._last_exit_code = 0
        shell.cwd = "/"
        sb = StatusBar(shell)

        win = MagicMock()
        sb.render(win, 80)
        win.erase.assert_called_once()
        win.addstr.assert_called_once()
        win.noutrefresh.assert_called_once()
