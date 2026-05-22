"""Context manager to capture stdout/stderr and push to terminal buffer."""

import contextlib
import io
import threading


class OutputCapture:
    def __init__(self, terminal):
        self._terminal = terminal
        self._buffer = io.StringIO()
        self._lock = threading.Lock()

    def __enter__(self):
        self._stdout_ctx = contextlib.redirect_stdout(self._buffer)
        self._stderr_ctx = contextlib.redirect_stderr(self._buffer)
        self._stdout_ctx.__enter__()
        self._stderr_ctx.__enter__()
        return self

    def __exit__(self, *args):
        self._stderr_ctx.__exit__(*args)
        self._stdout_ctx.__exit__(*args)
        output = self._buffer.getvalue()
        if output:
            with self._lock:
                for line in output.splitlines():
                    self._terminal.append(line)

    def write(self, text):
        self._buffer.write(text)
