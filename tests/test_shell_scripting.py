"""Tests for Pillar 2: Shell UX & Scripting features."""

import pytest
from pureos.core.kernel import Kernel


@pytest.fixture
def kernel():
    k = Kernel({"format_on_boot": True, "auto_start_services": False})
    k.initialize()
    return k


@pytest.fixture
def shell(kernel):
    return kernel.shell


# ---------------------------------------------------------------------------
# History recall
# ---------------------------------------------------------------------------


def test_history_recall_by_number(kernel, shell, capsys):
    shell.execute("echo first")
    shell.execute("echo second")
    shell.execute("echo third")
    # !2 should recall and re-run "echo second"
    shell.execute("!2")
    captured = capsys.readouterr()
    # "echo second" re-prints the recalled command and its output
    assert "echo second" in captured.out
    assert "second" in captured.out


def test_history_recall_by_prefix(kernel, shell, capsys):
    shell.execute("echo hello")
    shell.execute("pwd")
    # !echo should re-run the last echo command
    shell.execute("!echo")
    captured = capsys.readouterr()
    assert "echo hello" in captured.out


def test_history_recall_not_found(kernel, shell, capsys):
    res = shell.execute("!99999")
    assert res is False
    captured = capsys.readouterr()
    assert "event not found" in captured.out


def test_history_recall_prefix_not_found(kernel, shell, capsys):
    res = shell.execute("!zzz_nonexistent")
    assert res is False
    captured = capsys.readouterr()
    assert "event not found" in captured.out


# ---------------------------------------------------------------------------
# Exit code in prompt / env
# ---------------------------------------------------------------------------


def test_exit_code_on_success(kernel, shell):
    shell.execute("echo ok")
    assert shell.env["?"] == "0"
    assert shell._last_exit_code == 0


def test_exit_code_on_failure(kernel, shell):
    shell.execute("unknowncmd_xyz")
    assert shell.env["?"] == "1"
    assert shell._last_exit_code == 1


def test_prompt_shows_exit_code_when_nonzero(kernel, shell):
    shell.execute("unknowncmd_xyz")
    prompt = shell.prompt
    assert "[1]" in prompt


def test_prompt_no_exit_code_on_success(kernel, shell):
    shell.execute("echo ok")
    prompt = shell.prompt
    assert "[0]" not in prompt
    assert "[" not in prompt or ">" not in prompt.split("[")[0]


# ---------------------------------------------------------------------------
# set command: -e and -x flags
# ---------------------------------------------------------------------------


def test_set_command_enables_trace(kernel, shell, capsys):
    shell.execute("set -x")
    assert shell._flags["x"] is True
    shell.execute("echo traced")
    captured = capsys.readouterr()
    assert "+ echo traced" in captured.out
    shell.execute("set +x")
    assert shell._flags["x"] is False


def test_set_command_exit_on_error(kernel, shell):
    shell.execute("set -e")
    assert shell._flags["e"] is True
    # A failure should short-circuit
    res = shell.execute("nonexistent_cmd ; echo after")
    assert res is False
    shell.execute("set +e")
    assert shell._flags["e"] is False


def test_set_command_list(kernel, shell, capsys):
    shell.registry.execute(["set"], capture_output=False)
    captured = capsys.readouterr()
    assert "-e:" in captured.out
    assert "-x:" in captured.out


# ---------------------------------------------------------------------------
# jobs command
# ---------------------------------------------------------------------------


def test_jobs_command_empty(kernel, shell):
    out = shell.registry.execute(["jobs"], capture_output=True)
    assert "No background jobs" in out


def test_jobs_command_shows_processes(kernel, shell):
    shell.execute("spawn testjob")
    out = shell.registry.execute(["jobs"], capture_output=True)
    assert "testjob" in out


# ---------------------------------------------------------------------------
# time command
# ---------------------------------------------------------------------------


def test_time_command(kernel, shell):
    out = shell.registry.execute(["time", "echo", "hello"], capture_output=True)
    assert "real" in out
    assert "s" in out


def test_time_command_no_args(kernel, shell, capsys):
    res = shell.execute("time")
    assert res is False


# ---------------------------------------------------------------------------
# fg command
# ---------------------------------------------------------------------------


def test_fg_nonexistent(kernel, shell, capsys):
    res = shell.execute("fg 99999")
    assert res is False
    captured = capsys.readouterr()
    assert "no such job" in captured.out
