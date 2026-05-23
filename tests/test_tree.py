import pytest
from pureos.core.kernel import Kernel


@pytest.fixture
def kernel():
    k = Kernel({"format_on_boot": True, "auto_start_services": False})
    k.initialize()
    return k


def test_tree_command_basic(kernel):
    fs = kernel.fs
    fs.mkdir("/tmp/a/b", parents=True)
    fs.write("/tmp/a/file1.txt", "content")
    fs.write("/tmp/a/b/file2.txt", "content")

    # We use registry.execute directly to capture output
    out = kernel.registry.execute(["tree", "/tmp/a"], capture_output=True)

    expected_lines = ["/tmp/a/", "├── b/", "│   └── file2.txt", "└── file1.txt"]
    # Note: entries are sorted, so 'b/' comes before 'file1.txt' if using alphanumeric
    # But wait, 'b/' rstripped split is 'b'. 'file1.txt' rstripped split is 'file1.txt'.
    # 'b' < 'file1.txt'. Correct.

    # Actually, let's check what exactly the output looks like
    print(out)
    for line in expected_lines:
        assert line in out


def test_tree_command_cwd(kernel):
    fs = kernel.fs
    fs.mkdir("/home/user/docs", parents=True)
    fs.write("/home/user/docs/resume.pdf", "data")

    kernel.shell.execute("cd /home/user")
    out = kernel.registry.execute(["tree"], capture_output=True)

    assert "/home/user/" in out
    assert "└── docs/" in out
    assert "    └── resume.pdf" in out


def test_tree_command_not_found(kernel, capsys):
    kernel.shell.execute("tree /nonexistent")
    captured = capsys.readouterr()
    assert "/nonexistent: not found" in captured.out


def test_tree_command_not_dir(kernel, capsys):
    kernel.fs.write("/tmp/file.txt", "hello")
    kernel.shell.execute("tree /tmp/file.txt")
    captured = capsys.readouterr()
    assert "/tmp/file.txt: not a directory" in captured.out
