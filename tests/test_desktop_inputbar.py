"""Tests for the CommandInput line editor (non-curses logic)."""

import curses

from pureos.desktop.inputbar import CommandInput


class DummyShell:
    def __init__(self):
        self.history = []
        self._completion_matches = []

    def completer(self, text, state):
        if state < len(self._completion_matches):
            return self._completion_matches[state]
        return None


class TestCommandInput:
    def test_initial_state(self):
        sh = DummyShell()
        ci = CommandInput(sh)
        assert ci.text == ""

    def test_type_characters(self):
        sh = DummyShell()
        ci = CommandInput(sh)
        for ch in map(ord, "hello"):
            ci.handle_key(ch)
        assert ci.text == "hello"

    def test_backspace(self):
        sh = DummyShell()
        ci = CommandInput(sh)
        ci.set_text("hello")
        ci.handle_key(curses.KEY_BACKSPACE)
        assert ci.text == "hell"

    def test_backspace_at_beginning(self):
        sh = DummyShell()
        ci = CommandInput(sh)
        ci.handle_key(curses.KEY_BACKSPACE)
        assert ci.text == ""

    def test_delete_char(self):
        sh = DummyShell()
        ci = CommandInput(sh)
        ci.set_text("hello")
        ci._cursor = 2
        ci.handle_key(curses.KEY_DC)
        assert ci.text == "helo"

    def test_enter_returns_command(self):
        sh = DummyShell()
        ci = CommandInput(sh)
        ci.set_text("ls -la")
        action, value = ci.handle_key(ord("\n"))
        assert action == "enter"
        assert value == "ls -la"

    def test_enter_returns_text_and_preserves_it(self):
        sh = DummyShell()
        ci = CommandInput(sh)
        ci.set_text("ls")
        action, value = ci.handle_key(ord("\n"))
        assert action == "enter"
        assert value == "ls"
        assert ci.text == "ls"
        ci.clear()
        assert ci.text == ""

    def test_left_right_arrows(self):
        sh = DummyShell()
        ci = CommandInput(sh)
        ci.set_text("abc")
        ci.handle_key(curses.KEY_LEFT)
        assert ci._cursor == 2
        ci.handle_key(curses.KEY_RIGHT)
        assert ci._cursor == 3

    def test_home_end_keys(self):
        sh = DummyShell()
        ci = CommandInput(sh)
        ci.set_text("hello")
        ci._cursor = 2
        ci.handle_key(curses.KEY_HOME)
        assert ci._cursor == 0
        ci.handle_key(curses.KEY_END)
        assert ci._cursor == 5

    def test_ctrl_u_clears_line(self):
        sh = DummyShell()
        ci = CommandInput(sh)
        ci.set_text("hello world")
        ci.handle_key(21)  # Ctrl+U
        assert ci.text == ""
        assert ci._cursor == 0

    def test_clear(self):
        sh = DummyShell()
        ci = CommandInput(sh)
        ci.set_text("test")
        ci.clear()
        assert ci.text == ""
        assert ci._cursor == 0

    def test_set_text(self):
        sh = DummyShell()
        ci = CommandInput(sh)
        ci.set_text("new text")
        assert ci.text == "new text"
        assert ci._cursor == 8

    def test_history_up_selects_last(self):
        sh = DummyShell()
        sh.history = ["cmd1", "cmd2", "cmd3"]
        ci = CommandInput(sh)
        ci.handle_key(curses.KEY_UP)
        assert ci.text == "cmd3"

    def test_history_up_then_down(self):
        sh = DummyShell()
        sh.history = ["cmd1", "cmd2"]
        ci = CommandInput(sh)
        ci.handle_key(curses.KEY_UP)
        assert ci.text == "cmd2"
        ci.handle_key(curses.KEY_DOWN)
        assert ci.text == ""


class TestCommandInputTabCompletion:
    def test_single_match(self):
        sh = DummyShell()
        sh._completion_matches = ["hello"]
        ci = CommandInput(sh)
        ci.set_text("hel")
        result = ci.do_tab_completion()
        assert result is True
        assert ci.text == "hello"

    def test_no_matches(self):
        sh = DummyShell()
        sh._completion_matches = []
        ci = CommandInput(sh)
        ci.set_text("xyz")
        result = ci.do_tab_completion()
        assert result is False
        assert ci.text == "xyz"

    def test_multiple_matches_common_prefix(self):
        sh = DummyShell()
        sh._completion_matches = ["hello", "help", "helios"]
        ci = CommandInput(sh)
        ci.set_text("hel")
        result = ci.do_tab_completion()
        assert result is True
        assert ci.text == "hel"

    def test_multiple_matches_no_common_prefix(self):
        sh = DummyShell()
        sh._completion_matches = ["abc", "xyz"]
        ci = CommandInput(sh)
        ci.set_text("a")
        result = ci.do_tab_completion()
        assert result is True
        assert ci.text == "a"


class TestCommandInputExtra:
    def test_kill_word_backward(self):
        sh = DummyShell()
        ci = CommandInput(sh)
        ci.set_text("hello world")
        ci.do_kill_word_backward()
        assert ci.text == "hello "

    def test_kill_word_with_spaces(self):
        sh = DummyShell()
        ci = CommandInput(sh)
        ci.set_text("ls -la  ")
        ci.do_kill_word_backward()
        assert ci.text == "ls "

    def test_render_with_mock_win(self):
        from unittest.mock import MagicMock

        sh = DummyShell()
        ci = CommandInput(sh)
        ci.set_text("some command")
        win = MagicMock()
        ci.render(win, 80)
        win.erase.assert_called_once()
        win.addstr.assert_called_once()
        win.noutrefresh.assert_called_once()
