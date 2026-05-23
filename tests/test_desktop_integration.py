"""Integration tests for Desktop class (non-curses logic)."""

from pureos.shell.desktop.curses_compat import curses
from unittest.mock import MagicMock, patch
from pureos.shell.desktop.desktop import Desktop


class TestDesktopInit:
    def test_constructor_takes_kernel(self, kernel):
        d = Desktop(kernel)
        assert d.kernel is kernel
        assert d.shell is kernel.shell

    def test_init_run_method_exists(self, kernel):
        d = Desktop(kernel)
        assert callable(d.run)

    def test_init_loads_history(self, kernel):
        kernel.fs.write("/etc/history", "cmd1\ncmd2")
        d = Desktop(kernel)
        d.shell.load_history()
        assert d.shell.history == ["cmd1", "cmd2"]

    def test_init_sources_pureosrc(self, kernel):
        kernel.fs.write("/etc/pureosrc", "echo hello")
        t = Desktop(kernel)
        t.shell.execute("alias testalias=echo", add_to_history=False)
        assert "testalias" not in t.shell.aliases
        t.shell.aliases["testalias"] = "echo"
        assert t.shell.aliases["testalias"] == "echo"


class TestDesktopLogic:
    def test_execute_command(self, kernel):
        d = Desktop(kernel)
        d._terminal = MagicMock()
        d._stdscr = MagicMock()
        d._input_win = MagicMock()
        d._status_win = MagicMock()
        d._term_height = 20
        d._term_width = 80
        d._term_offset_y = 0
        d._term_offset_x = 0
        d._term_pad = MagicMock()
        d._cmd_input = MagicMock()
        d._statusbar = MagicMock()

        with patch("curses.doupdate"):
            d._execute_command("echo hello")
        assert d._terminal.append.called

    def test_execute_exit(self, kernel):
        d = Desktop(kernel)
        d._running = True
        d._execute_command("exit")
        assert d._running is False

    def test_relayout(self, kernel):
        d = Desktop(kernel)
        d._stdscr = MagicMock()
        d._stdscr.getmaxyx.return_value = (24, 80)
        d._input_win = MagicMock()
        d._status_win = MagicMock()
        with patch("curses.newpad"):
            d._relayout()
        assert d._term_height == 22
        assert d._term_width == 80

    def test_handle_exit_check(self, kernel):
        d = Desktop(kernel)
        d._running = True
        d._cmd_input = MagicMock()
        d._cmd_input.text = ""
        d._handle_exit_check(4, None)  # Ctrl+D
        assert d._running is False

    def test_handle_key_resize(self, kernel):
        d = Desktop(kernel)
        d._stdscr = MagicMock()
        d._stdscr.getmaxyx.return_value = (24, 80)
        d._input_win = MagicMock()
        d._status_win = MagicMock()
        d._terminal = MagicMock()
        d._cmd_input = MagicMock()
        d._statusbar = MagicMock()
        d._term_height = 22
        d._term_width = 80
        d._term_offset_y = 0
        d._term_offset_x = 0

        with patch("curses.newpad"), patch("curses.doupdate"):
            d._handle_key(curses.KEY_RESIZE)
            assert d._stdscr.getmaxyx.called

    def test_handle_key_scrolling(self, kernel):
        d = Desktop(kernel)
        d._stdscr = MagicMock()
        d._terminal = MagicMock()
        d._cmd_input = MagicMock()
        d._statusbar = MagicMock()
        d._term_height = 22
        d._term_width = 80
        d._term_offset_y = 0
        d._term_offset_x = 0
        d._term_pad = MagicMock()
        d._input_win = MagicMock()
        d._status_win = MagicMock()

        with patch("curses.doupdate"):
            d._handle_key(curses.KEY_PPAGE)
            d._terminal.scroll_up.assert_called_with(10)

            d._handle_key(curses.KEY_NPAGE)
            d._terminal.scroll_down.assert_called_with(10)

    def test_handle_key_clear(self, kernel):
        d = Desktop(kernel)
        d._stdscr = MagicMock()
        d._terminal = MagicMock()
        d._cmd_input = MagicMock()
        d._statusbar = MagicMock()
        d._term_height = 22
        d._term_width = 80
        d._term_offset_y = 0
        d._term_offset_x = 0
        d._term_pad = MagicMock()
        d._input_win = MagicMock()
        d._status_win = MagicMock()

        with patch("curses.doupdate"):
            d._handle_key(12)  # Ctrl+L
            d._terminal.clear.assert_called_once()

    def test_handle_key_enter(self, kernel):
        d = Desktop(kernel)
        d._stdscr = MagicMock()
        d._terminal = MagicMock()
        d._cmd_input = MagicMock()
        d._statusbar = MagicMock()
        d._term_height = 22
        d._term_width = 80
        d._term_offset_y = 0
        d._term_offset_x = 0
        d._term_pad = MagicMock()
        d._input_win = MagicMock()
        d._status_win = MagicMock()

        d._cmd_input.handle_key.return_value = ("enter", "echo hi")

        with patch("curses.doupdate"):
            d._handle_key(ord("\n"))
            d._cmd_input.clear.assert_called_once()

    def test_handle_key_tab(self, kernel):
        d = Desktop(kernel)
        d._stdscr = MagicMock()
        d._terminal = MagicMock()
        d._cmd_input = MagicMock()
        d._statusbar = MagicMock()
        d._term_height = 22
        d._term_width = 80
        d._term_offset_y = 0
        d._term_offset_x = 0
        d._term_pad = MagicMock()
        d._input_win = MagicMock()
        d._status_win = MagicMock()

        d._cmd_input.handle_key.return_value = ("tab", None)

        with patch("curses.newpad"), patch("curses.doupdate"):
            d._handle_key(9)
            d._cmd_input.do_tab_completion.assert_called_once()

    def test_run_with_rc_error(self, kernel):
        # Force an error when reading pureosrc
        kernel.fs.write("/etc/pureosrc", "echo hello")
        d = Desktop(kernel)
        with patch.object(kernel.fs, "read", side_effect=Exception("fs error")):
            with patch("curses.wrapper"):
                d.run()
        # Should not crash

    def test_relayout_exception(self, kernel):
        d = Desktop(kernel)
        d._stdscr = MagicMock()
        d._stdscr.getmaxyx.return_value = (24, 80)
        # Force resize to fail
        d._input_win = MagicMock()
        d._input_win.resize.side_effect = Exception("resize failed")
        d._status_win = MagicMock()
        d._status_win.resize.side_effect = Exception("resize failed")

        with patch("curses.newpad"), patch("curses.newwin") as mock_newwin:
            d._relayout()
            assert mock_newwin.call_count >= 2
