"""Tests for the OutputCapture context manager."""

from pureos.shell.desktop.terminal import TerminalOutput
from pureos.shell.desktop.output_capture import OutputCapture


class TestOutputCapture:
    def test_captures_print(self):
        t = TerminalOutput()
        with OutputCapture(t):
            print("hello")
            print("world")
        assert t.lines == ["hello", "world"]

    def test_captures_mixed_output(self):
        t = TerminalOutput()
        with OutputCapture(t):
            print("line1")
            print("line2\nline3")
        assert t.lines == ["line1", "line2", "line3"]

    def test_no_output_pushes_nothing(self):
        t = TerminalOutput()
        with OutputCapture(t):
            pass
        assert t.lines == []

    def test_multiple_contexts(self):
        t = TerminalOutput()
        with OutputCapture(t):
            print("first")
        with OutputCapture(t):
            print("second")
        assert t.lines == ["first", "second"]

    def test_write_method(self):
        t = TerminalOutput()
        cap = OutputCapture(t)
        cap.write("direct write")
        assert "direct write" in cap._buffer.getvalue()
