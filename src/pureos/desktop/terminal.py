from collections import deque


class TerminalOutput:
    def __init__(self, max_lines=500):
        self._lines = deque(maxlen=max_lines)
        self._max_lines = max_lines
        self._scroll_offset = 0

    def append(self, text):
        if text is None:
            return
        if text == "":
            self._lines.append("")
            return
        self._lines.extend(text.splitlines())

    def append_line(self, line):
        self._lines.append(line)

    def clear(self):
        self._lines.clear()
        self._scroll_offset = 0

    @property
    def lines(self):
        return list(self._lines)

    @property
    def total_lines(self):
        return len(self._lines)

    @property
    def scroll_offset(self):
        return self._scroll_offset

    def scroll_up(self, amount=1):
        self._scroll_offset = min(
            self._scroll_offset + amount, max(0, self.total_lines - 1)
        )

    def scroll_down(self, amount=1):
        self._scroll_offset = max(self._scroll_offset - amount, 0)

    def scroll_to_bottom(self):
        self._scroll_offset = 0

    def visible_lines(self, term_height):
        buf = list(self._lines)
        if not buf:
            return []
        start = max(0, len(buf) - term_height - self._scroll_offset)
        end = len(buf) - self._scroll_offset
        return buf[start:end]

    def render(self, pad, term_height, term_width, offset_y=0, offset_x=0):
        visible = self.visible_lines(term_height)
        pad.erase()
        for i, line in enumerate(visible):
            display = line[:term_width]
            if i < term_height:
                try:
                    pad.addstr(i, 0, display)
                except Exception:
                    pass
        try:
            pad.refresh(
                0,
                0,
                offset_y,
                offset_x,
                offset_y + term_height - 1,
                offset_x + term_width - 1,
            )
        except Exception:
            pass
