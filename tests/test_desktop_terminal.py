"""Tests for the TerminalOutput scrollable buffer."""

from pureos.desktop.terminal import TerminalOutput


class TestTerminalOutput:
    def test_append_adds_lines(self):
        t = TerminalOutput(max_lines=100)
        t.append("hello\nworld")
        assert t.lines == ["hello", "world"]

    def test_append_empty_adds_blank_line(self):
        t = TerminalOutput(max_lines=100)
        t.append_line("keep")
        t.append("")
        assert t.lines == ["keep", ""]

    def test_append_line_adds_single_line(self):
        t = TerminalOutput(max_lines=100)
        t.append_line("single")
        assert t.lines == ["single"]

    def test_clear_removes_all_lines(self):
        t = TerminalOutput(max_lines=100)
        t.append("a\nb\nc")
        t.clear()
        assert t.lines == []
        assert t.total_lines == 0

    def test_max_lines_truncates(self):
        t = TerminalOutput(max_lines=3)
        t.append("1\n2\n3\n4\n5")
        assert t.lines == ["3", "4", "5"]

    def test_scroll_down_and_up(self):
        t = TerminalOutput(max_lines=100)
        t.append("1\n2\n3\n4\n5")
        t.scroll_up(2)
        assert t.scroll_offset == 2
        t.scroll_down(1)
        assert t.scroll_offset == 1
        t.scroll_to_bottom()
        assert t.scroll_offset == 0

    def test_visible_lines_respects_height(self):
        t = TerminalOutput(max_lines=100)
        t.append("1\n2\n3\n4\n5")
        visible = t.visible_lines(term_height=3)
        assert visible == ["3", "4", "5"]

    def test_visible_lines_with_scroll(self):
        t = TerminalOutput(max_lines=100)
        t.append("1\n2\n3\n4\n5")
        t.scroll_up(1)
        visible = t.visible_lines(term_height=3)
        assert visible == ["2", "3", "4"]

    def test_visible_lines_empty_buffer(self):
        t = TerminalOutput(max_lines=100)
        assert t.visible_lines(term_height=3) == []

    def test_total_lines_tracks_count(self):
        t = TerminalOutput(max_lines=100)
        assert t.total_lines == 0
        t.append("a\nb")
        assert t.total_lines == 2

    def test_append_single_line_string(self):
        t = TerminalOutput(max_lines=100)
        t.append("just one line no newline")
        assert t.lines == ["just one line no newline"]

    def test_render_with_mock_pad(self):
        from unittest.mock import MagicMock
        t = TerminalOutput(max_lines=100)
        t.append("line1\nline2")
        pad = MagicMock()
        t.render(pad, term_height=10, term_width=80)
        pad.erase.assert_called_once()
        assert pad.addstr.call_count == 2
        pad.refresh.assert_called_once()
