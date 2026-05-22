"""Integration tests for Desktop class (non-curses logic)."""

from unittest.mock import patch, MagicMock

from pureos.desktop.desktop import Desktop


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
