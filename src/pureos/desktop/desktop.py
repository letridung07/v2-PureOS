"""TUI desktop environment for v2-PureOS. Wraps the Shell in a curses interface."""

from .curses_compat import curses

from .terminal import TerminalOutput
from .inputbar import CommandInput
from .statusbar import StatusBar
from .output_capture import OutputCapture


class Desktop:
    def __init__(self, kernel):
        self.kernel = kernel
        self.shell = kernel.shell
        self._terminal = None
        self._cmd_input = None
        self._statusbar = None
        self._stdscr = None
        self._running = False

    def run(self):
        self.shell.load_history()
        rc_path = "/etc/pureosrc"
        if self.kernel.fs.exists(rc_path):
            try:
                content = self.kernel.fs.read(rc_path)
                if content:
                    for line in content.splitlines():
                        line = line.strip()
                        if not line or line.startswith("#"):
                            continue
                        self.shell.execute(line, add_to_history=False)
            except Exception:
                pass

        curses.wrapper(self._run_curses)

    def _run_curses(self, stdscr):
        self._stdscr = stdscr
        curses.curs_set(0)
        curses.use_default_colors()
        self._init_colors()
        self._init_layout()
        self._redraw()
        self._running = True

        while self._running:
            ch = self._stdscr.getch()
            if ch == -1:
                continue
            self._handle_key(ch)

        self.shell.save_history()

    def _init_colors(self):
        if curses.has_colors():
            curses.init_pair(1, curses.COLOR_BLACK, curses.COLOR_WHITE)
            curses.init_pair(2, curses.COLOR_WHITE, curses.COLOR_BLUE)

    def _init_layout(self):
        h, w = self._stdscr.getmaxyx()
        status_h = 1
        input_h = 1
        term_h = max(1, h - status_h - input_h)

        self._term_pad = curses.newpad(max(term_h, term_h * 4), w)
        self._term_height = term_h
        self._term_width = w
        self._term_offset_y = 0
        self._term_offset_x = 0

        self._input_win = curses.newwin(input_h, w, term_h, 0)
        self._input_win.keypad(True)

        self._status_win = curses.newwin(status_h, w, h - 1, 0)

        self._terminal = TerminalOutput(max_lines=500)
        self._cmd_input = CommandInput(self.shell)
        self._statusbar = StatusBar(self.shell)

    def _relayout(self):
        h, w = self._stdscr.getmaxyx()
        status_h = 1
        input_h = 1
        term_h = max(1, h - status_h - input_h)

        self._term_pad = curses.newpad(max(term_h, term_h * 4), w)
        self._term_height = term_h
        self._term_width = w

        try:
            self._input_win.resize(input_h, w)
            self._input_win.mvwin(term_h, 0)
        except Exception:
            self._input_win = curses.newwin(input_h, w, term_h, 0)
            self._input_win.keypad(True)

        try:
            self._status_win.resize(status_h, w)
            self._status_win.mvwin(h - 1, 0)
        except Exception:
            self._status_win = curses.newwin(status_h, w, h - 1, 0)

    def _redraw(self):
        self._stdscr.erase()
        self._terminal.render(
            self._term_pad,
            self._term_height,
            self._term_width,
            self._term_offset_y,
            self._term_offset_x,
        )
        self._cmd_input.render(self._input_win, self._term_width)
        self._statusbar.render(self._status_win, self._term_width)
        curses.doupdate()

    def _handle_key(self, ch):
        if ch == curses.KEY_RESIZE:
            self._relayout()
            self._redraw()
            return

        if ch == curses.KEY_PPAGE:
            self._terminal.scroll_up(10)
            self._redraw()
            return

        if ch == curses.KEY_NPAGE:
            self._terminal.scroll_down(10)
            self._redraw()
            return

        if ch == 12:
            self._terminal.clear()
            self._redraw()
            return

        action, value = self._cmd_input.handle_key(ch)

        if action == "enter":
            cmd = value.strip()
            if cmd:
                self._execute_command(cmd)
            elif not self.shell.history or self.shell.history[-1] != "":
                pass
            self._cmd_input.clear()
            self._redraw()

        elif action == "tab":
            self._cmd_input.do_tab_completion()
            self._redraw()

        elif action == "ctrl_w":
            self._cmd_input.do_kill_word_backward()
            self._redraw()

        elif action == "edit":
            self._redraw()

        elif action == "resize":
            self._relayout()
            self._redraw()

        self._handle_exit_check(ch, value)

    def _handle_exit_check(self, ch, value):
        if ch == 4 and not self._cmd_input.text:
            self._running = False

        if ch == curses.KEY_F1:
            self._terminal.append(
                "Help: Ctrl+D or type 'exit' to quit | Ctrl+L to clear | F1 for help"
            )
            self._redraw()

    def _execute_command(self, cmd):
        if cmd == "exit":
            self._running = False
            return

        icon = f"{self.shell.prompt}{cmd}"
        self._terminal.append(icon)

        try:
            with OutputCapture(self._terminal):
                self.shell.execute(cmd, add_to_history=True)
        except Exception as exc:
            self._terminal.append(f"Error: {exc}")

        self._terminal.scroll_to_bottom()
        self._redraw()
