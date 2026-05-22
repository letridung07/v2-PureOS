import curses
import curses.ascii


class CommandInput:
    def __init__(self, shell):
        self._shell = shell
        self._text = ""
        self._cursor = 0
        self._history_index = -1

    @property
    def text(self):
        return self._text

    def clear(self):
        self._text = ""
        self._cursor = 0

    def set_text(self, text):
        self._text = text
        self._cursor = len(text)

    def handle_key(self, ch):
        if ch in (ord("\n"), curses.KEY_ENTER):
            result = self._text
            self._clear_for_history()
            return ("enter", result)
        elif ch == curses.KEY_BACKSPACE or ch in (127, 8):
            if self._cursor > 0:
                self._text = self._text[:self._cursor - 1] + self._text[self._cursor:]
                self._cursor -= 1
            return ("edit", None)
        elif ch == curses.KEY_DC:
            if self._cursor < len(self._text):
                self._text = self._text[:self._cursor] + self._text[self._cursor + 1:]
            return ("edit", None)
        elif ch == curses.KEY_LEFT:
            if self._cursor > 0:
                self._cursor -= 1
            return ("edit", None)
        elif ch == curses.KEY_RIGHT:
            if self._cursor < len(self._text):
                self._cursor += 1
            return ("edit", None)
        elif ch == curses.KEY_HOME or ch == 1:
            self._cursor = 0
            return ("edit", None)
        elif ch == curses.KEY_END or ch == 5:
            self._cursor = len(self._text)
            return ("edit", None)
        elif ch == curses.KEY_UP:
            self._recall_history_previous()
            return ("edit", None)
        elif ch == curses.KEY_DOWN:
            self._recall_history_next()
            return ("edit", None)
        elif ch == 9:
            return ("tab", None)
        elif ch == 23:
            return ("ctrl_w", None)
        elif ch == 21:
            self._text = ""
            self._cursor = 0
            return ("edit", None)
        elif ch == curses.KEY_RESIZE:
            return ("resize", None)
        elif curses.ascii.isprint(ch):
            self._text = self._text[:self._cursor] + chr(ch) + self._text[self._cursor:]
            self._cursor += 1
            return ("edit", None)
        return (None, None)

    def _recall_history_previous(self):
        history = self._shell.history
        if not history:
            return
        if self._history_index == -1:
            self._saved_before_history = self._text
            self._history_index = len(history) - 1
        elif self._history_index > 0:
            self._history_index -= 1
        self._text = history[self._history_index]
        self._cursor = len(self._text)

    def _recall_history_next(self):
        history = self._shell.history
        if self._history_index == -1:
            return
        if self._history_index < len(history) - 1:
            self._history_index += 1
            self._text = history[self._history_index]
        else:
            self._history_index = -1
            self._text = getattr(self, "_saved_before_history", "")
        self._cursor = len(self._text)

    def _clear_for_history(self):
        self._history_index = -1

    def do_tab_completion(self):
        try:
            completer = self._shell.completer
        except AttributeError:
            return False
        matches = []
        for state in range(100):
            match = completer(self._text, state)
            if match is None:
                break
            matches.append(match)
        if not matches:
            return False
        if len(matches) == 1:
            self._text = matches[0]
            self._cursor = len(self._text)
        else:
            common_prefix = matches[0]
            for m in matches[1:]:
                while not m.startswith(common_prefix):
                    common_prefix = common_prefix[:-1]
                    if not common_prefix:
                        break
                if not common_prefix:
                    break
            if common_prefix and len(common_prefix) > len(self._text):
                self._text = common_prefix
                self._cursor = len(self._text)
        return True

    def do_kill_word_backward(self):
        pos = self._cursor
        while pos > 0 and self._text[pos - 1].isspace():
            pos -= 1
        while pos > 0 and not self._text[pos - 1].isspace():
            pos -= 1
        killed = self._text[pos:self._cursor]
        self._text = self._text[:pos] + self._text[self._cursor:]
        self._cursor = pos
        return killed

    def render(self, win, term_width):
        draw = self._text[:term_width - 2]
        cursor_x = min(self._cursor, term_width - 2)
        win.erase()
        try:
            win.addstr(0, 0, draw[:term_width - 2])
        except Exception:
            pass
        try:
            curses.curs_set(1)
            win.move(0, cursor_x)
        except Exception:
            pass
        win.noutrefresh()
