"""Tests for the --desktop CLI flag."""

from pureos.shell.cli import parse_args


class TestDesktopCliFlag:
    def test_desktop_flag_short(self):
        args = parse_args(["-d"])
        assert args.desktop is True

    def test_desktop_flag_long(self):
        args = parse_args(["--desktop"])
        assert args.desktop is True

    def test_no_desktop_flag(self):
        args = parse_args([])
        assert args.desktop is False

    def test_shell_and_desktop_independent(self):
        args = parse_args(["--shell", "--desktop"])
        assert args.shell is True
        assert args.desktop is True

    def test_version_flag_still_works(self):
        args = parse_args(["--version"])
        assert args.version is True
