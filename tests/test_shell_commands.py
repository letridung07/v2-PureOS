import importlib
import os
import sys
import time

try:
    kernel_mod = importlib.import_module("pureos.kernel")
except Exception:
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
    kernel_mod = importlib.import_module("pureos.kernel")

Kernel = kernel_mod.Kernel


def test_shell_fs_and_processes_and_services(tmp_path, capsys):
    backing = tmp_path / "store.json"
    k = Kernel(config={"fs_backing": str(backing)})
    k.initialize()
    sh = k.shell

    # mkdir
    sh.execute("mkdir /tmp/dir")
    assert k.fs.exists("/tmp/dir/")

    # touch
    sh.execute("touch /tmp/a")
    assert k.fs.exists("/tmp/a")

    # write
    sh.execute("write /tmp/a hello")
    assert k.fs.read("/tmp/a") == "hello"

    # append
    sh.execute("append /tmp/a world")
    assert k.fs.read("/tmp/a") == "helloworld"

    # mv
    sh.execute("mv /tmp/a /tmp/b")
    assert k.fs.read("/tmp/b") == "helloworld"
    assert k.fs.read("/tmp/a") is None

    # cp
    sh.execute("cp /tmp/b /tmp/c")
    assert k.fs.read("/tmp/c") == "helloworld"

    # format
    sh.execute("format")
    assert k.fs.read("/tmp/c") is None
    assert k.fs.read("/etc/motd") == "Welcome to v2-PureOS"

    # rm
    sh.execute("rm /tmp/b")
    assert k.fs.read("/tmp/b") is None

    # echo redirect
    sh.execute("echo hi > /tmp/d")
    assert k.fs.read("/tmp/d") == "hi\n"

    # echo -n
    sh.execute("echo -n hi > /tmp/d_n")
    assert k.fs.read("/tmp/d_n") == "hi"

    # head/tail
    lines = "\n".join(f"line {i}" for i in range(1, 21))
    k.fs.write("/tmp/lines", lines)
    sh.execute("head /tmp/lines 3")
    captured = capsys.readouterr()
    assert "line 1" in captured.out
    sh.execute("tail /tmp/lines 2")
    captured = capsys.readouterr()
    assert "line 20" in captured.out

    # services
    start_file = tmp_path / "started"

    def svc(ev=None):
        start_file.write_text("started")
        if ev:
            ev.wait(0.2)

    k.services.register("testsrv", svc, daemon=False, stoppable=True)
    sh.execute("service start testsrv")
    time.sleep(0.05)
    assert start_file.exists()

    # status
    sh.execute("service status testsrv")
    captured = capsys.readouterr()
    assert "running=" in captured.out

    # stop
    sh.execute("service stop testsrv")
    time.sleep(0.05)
    t = k.services._threads.get("testsrv")
    assert not (t and t.is_alive())

    # spawn and kill
    sh.execute("spawn worker")
    assert len(k.scheduler.list()) >= 1
    pid = k.scheduler.list()[0].pid
    sh.execute(f"kill {pid}")
    assert k.scheduler.processes[pid].status == "killed"


def test_shell_ls_vs_find_direct_children(tmp_path, capsys):
    backing = tmp_path / "store.json"
    k = Kernel(config={"fs_backing": str(backing)})
    k.initialize()
    sh = k.shell

    sh.execute("mkdir /tmp")
    sh.execute("mkdir /tmp/dir")
    sh.execute("mkdir /tmp/dir/sub")
    sh.execute("write /tmp/dir/file.txt hello")
    sh.execute("write /tmp/dir/sub/file2.txt world")
    capsys.readouterr()

    sh.execute("ls /tmp/dir")
    captured = capsys.readouterr()
    assert "/tmp/dir/file.txt" in captured.out
    assert "/tmp/dir/sub/" in captured.out
    assert "/tmp/dir/sub/file2.txt" not in captured.out

    sh.execute("find /tmp/dir")
    captured = capsys.readouterr()
    assert "/tmp/dir/sub/file2.txt" in captured.out


def test_shell_relative_paths_with_cd_and_rmdir(tmp_path, capsys):
    backing = tmp_path / "store.json"
    k = Kernel(config={"fs_backing": str(backing)})
    k.initialize()
    sh = k.shell
    capsys.readouterr()

    sh.execute("pwd")
    captured = capsys.readouterr()
    assert captured.out.strip() == "/"

    sh.execute("mkdir tmp")
    assert k.fs.exists("/tmp/")

    sh.execute("cd tmp")
    assert k.shell.cwd == "/tmp/"
    capsys.readouterr()

    sh.execute("pwd")
    captured = capsys.readouterr()
    assert captured.out.strip() == "/tmp/"

    sh.execute("write foo hello")
    assert k.fs.read("/tmp/foo") == "hello"

    sh.execute("find")
    captured = capsys.readouterr()
    assert "/tmp/foo" in captured.out

    sh.execute("cd /")
    sh.execute("mkdir /tmp/emptydir")
    sh.execute("rmdir /tmp/emptydir")
    assert not k.fs.exists("/tmp/emptydir/")

    sh.execute("mkdir /tmp/nonempty")
    sh.execute("write /tmp/nonempty/file data")
    sh.execute("rmdir /tmp/nonempty")
    captured = capsys.readouterr()
    assert "Directory not empty" in captured.out
    assert k.fs.exists("/tmp/nonempty/")


def test_shell_cwd_edge_cases(tmp_path, capsys):
    backing = tmp_path / "store.json"
    k = Kernel(config={"fs_backing": str(backing)})
    k.initialize()
    sh = k.shell
    capsys.readouterr()

    sh.execute("mkdir /tmp")
    sh.execute("mkdir /tmp/inner")
    sh.execute("cd /tmp/inner")
    assert sh.cwd == "/tmp/inner/"

    sh.execute("cd ..")
    assert sh.cwd == "/tmp/"

    sh.execute("cd .")
    assert sh.cwd == "/tmp/"

    sh.execute("touch ./file")
    assert k.fs.exists("/tmp/file")

    sh.execute("write ../rootfile hello")
    assert k.fs.read("/rootfile") == "hello"

    sh.execute("cd /")
    sh.execute("find .")
    captured = capsys.readouterr()
    assert "/tmp/" in captured.out
    assert "/rootfile" in captured.out

    sh.execute("rmdir /doesnotexist")
    captured = capsys.readouterr()
    assert "not found" in captured.out

    sh.execute("rmdir /")
    captured = capsys.readouterr()
    assert "Cannot remove root directory" in captured.out


def test_shell_permissions_and_chaining(tmp_path, capsys):
    backing = tmp_path / "store.json"
    k = Kernel(config={"fs_backing": str(backing)})
    k.initialize()
    sh = k.shell

    sh.execute("mkdir /tmp")
    sh.execute("write /tmp/a hello")
    sh.execute("chmod 600 /tmp/a")
    sh.execute("stat /tmp/a")
    captured = capsys.readouterr()
    assert "type: file" in captured.out
    assert "mode: 0o600" in captured.out
    assert "mode_str: -rw-------" in captured.out

    sh.execute("ls -l /tmp")
    captured = capsys.readouterr()
    assert "-rw-------" in captured.out
    assert "/tmp/a" in captured.out

    sh.execute("unknowncmd || echo ok > /tmp/ok")
    assert k.fs.read("/tmp/ok") == "ok\n"

    sh.execute("mkdir /chain ; touch /chain/a && write /chain/a data || echo fail")
    assert k.fs.read("/chain/a") == "data"


def test_shell_export_and_variable_substitution(tmp_path, capsys):
    backing = tmp_path / "store.json"
    k = Kernel(config={"fs_backing": str(backing)})
    k.initialize()
    sh = k.shell

    sh.execute("export GREETING=hello")
    sh.execute("echo $GREETING > /tmp/greeting")
    assert k.fs.read("/tmp/greeting") == "hello\n"

    sh.execute("export FILE_NAME=world")
    sh.execute("write /tmp/$FILE_NAME test")
    assert k.fs.read("/tmp/world") == "test"


def test_shell_alias_and_history(tmp_path, capsys):
    backing = tmp_path / "store.json"
    k = Kernel(config={"fs_backing": str(backing)})
    k.initialize()
    sh = k.shell

    sh.execute("alias ll ls -l")
    sh.execute("mkdir /tmp")
    sh.execute("touch /tmp/file")
    sh.execute("ll /tmp")
    captured = capsys.readouterr()
    assert "/tmp/file" in captured.out

    sh.execute("history")
    captured = capsys.readouterr()
    assert "alias ll ls -l" in captured.out
    assert "ll /tmp" in captured.out

    sh.execute("unalias ll")
    sh.execute("ll /tmp")
    captured = capsys.readouterr()
    assert "Unknown command" in captured.out


def test_shell_quoted_arguments_and_escaped_pipes(tmp_path, capsys):
    backing = tmp_path / "store.json"
    k = Kernel(config={"fs_backing": str(backing)})
    k.initialize()
    sh = k.shell
    capsys.readouterr()

    sh.execute('echo "hello world"')
    captured = capsys.readouterr()
    assert captured.out.strip() == "hello world"

    sh.execute("echo hello\\|world")
    captured = capsys.readouterr()
    assert captured.out.strip() == "hello|world"

    sh.execute('echo "a > b" > /tmp/quoted')
    captured = capsys.readouterr()
    assert k.fs.read("/tmp/quoted") == "a > b\n"

    sh.execute("echo a >> /tmp/append")
    sh.execute("echo b >> /tmp/append")
    captured = capsys.readouterr()
    assert k.fs.read("/tmp/append") == "a\nb\n"

    sh.execute('echo "foo > bar"')
    captured = capsys.readouterr()
    assert captured.out.strip() == "foo > bar"

    sh.execute("echo '$FOO'")
    captured = capsys.readouterr()
    assert captured.out.strip() == "$FOO"

    sh.execute("export FOO=hello")
    sh.execute("echo '$FOO'")
    captured = capsys.readouterr()
    assert captured.out.strip() == "$FOO"

    sh.execute(r"echo foo\\")
    captured = capsys.readouterr()
    assert captured.out.strip() == "foo\\"

    sh.execute("help")
    captured = capsys.readouterr()
    assert "echo [-n] [-e] [text] [> path]" in captured.out
    assert "alias [name command]" in captured.out

    sh.execute('alias ll "ls -l"')
    sh.execute("mkdir /tmp")
    sh.execute("touch /tmp/file")
    sh.execute("ll /tmp")
    captured = capsys.readouterr()
    assert "/tmp/file" in captured.out

    sh.execute("alias a b")
    sh.execute("alias b a")
    sh.execute("a")
    captured = capsys.readouterr()
    assert "Unknown command" in captured.out


def test_shell_pipes_and_grep(tmp_path, capsys):
    backing = tmp_path / "store.json"
    k = Kernel(config={"fs_backing": str(backing)})
    k.initialize()
    sh = k.shell

    k.fs.write("/tmp/lines", "one\ntwo\nthree\n")
    sh.execute("cat /tmp/lines | grep o")
    captured = capsys.readouterr()
    assert "one" in captured.out
    assert "two" in captured.out
    assert "three" not in captured.out


def test_shell_head_tail_with_n(tmp_path, capsys):
    backing = tmp_path / "store.json"
    k = Kernel(config={"fs_backing": str(backing)})
    k.initialize()
    sh = k.shell

    k.fs.write("/tmp/lines", "one\ntwo\nthree\n")
    capsys.readouterr()
    sh.execute("cat /tmp/lines | grep t | head -n 1")
    captured = capsys.readouterr()
    assert captured.out.strip() == "two"


def test_shell_source_script(tmp_path):
    backing = tmp_path / "store.json"
    k = Kernel(config={"fs_backing": str(backing)})
    k.initialize()
    sh = k.shell

    k.fs.write(
        "/tmp/script", "# sample script\nmkdir /scriptdir\nwrite /scriptdir/foo bar\n"
    )
    sh.execute("source /tmp/script")
    assert k.fs.read("/scriptdir/foo") == "bar"


def test_general_redirection(tmp_path, capsys):
    k = Kernel(config={"fs_backing": str(tmp_path / "store.json")})
    k.initialize()
    sh = k.shell

    # Test ls redirection
    sh.execute("mkdir /tmp")
    sh.execute("touch /tmp/a")
    sh.execute("ls /tmp > /tmp/out")
    assert k.fs.read("/tmp/out") == "/tmp/a"

    # Test ps redirection
    sh.execute("spawn test_proc")
    sh.execute("ps > /tmp/ps_out")
    ps_content = k.fs.read("/tmp/ps_out")
    assert "test_proc" in ps_content

    # Test append redirection
    sh.execute("echo hello > /tmp/out")
    sh.execute("echo world >> /tmp/out")
    assert k.fs.read("/tmp/out") == "hello\nworld\n"

    # Test syntax error for missing redirection target
    capsys.readouterr()
    res = sh.execute("echo hello >")
    captured = capsys.readouterr()
    assert "Syntax error: redirect target not specified" in captured.out
    assert res is False

    # Clean shutdown
    k.shutdown()


def test_background_jobs(tmp_path, capsys):
    k = Kernel(config={"fs_backing": str(tmp_path / "store.json")})
    k.initialize()
    sh = k.shell

    # Create a script that writes to a file
    k.fs.write("/tmp/bg_script", "touch /tmp/bg_done")

    # Run the script in the background using &
    sh.execute("source /tmp/bg_script &")

    # Check if a process is registered and runs
    import time

    time.sleep(0.2)
    assert k.fs.exists("/tmp/bg_done")

    # Check jobs output
    sh.execute("jobs")
    captured = capsys.readouterr()
    assert "running" in captured.out or "completed" in captured.out or not captured.out

    k.shutdown()


def test_autocomplete(tmp_path):
    k = Kernel(config={"fs_backing": str(tmp_path / "store.json")})
    k.initialize()
    sh = k.shell

    # Command completion
    assert sh.completer("l", 0) == "ls"

    # Path completion
    k.fs.mkdir("/testdir/")
    k.fs.write("/testdir/file1.txt", "hello")
    k.fs.write("/testdir/file2.txt", "world")

    # Completing /testdir/fi
    matches = sh._complete_path("/testdir/fi")
    assert "/testdir/file1.txt" in matches
    assert "/testdir/file2.txt" in matches

    k.shutdown()


def test_extra_commands(tmp_path, capsys):
    k = Kernel(config={"fs_backing": str(tmp_path / "store.json")})
    k.initialize()
    sh = k.shell

    # Test wc
    k.fs.write("/tmp/wc_test", "hello\nworld\n")
    wc_out = sh.registry.execute(["wc", "/tmp/wc_test"], capture_output=True)
    assert "2" in wc_out  # 2 lines
    assert "2" in wc_out  # 2 words
    assert "12" in wc_out  # 12 bytes

    # Test wc stdin/piping
    sh.execute("cat /tmp/wc_test | wc -l > /tmp/wc_l")
    assert k.fs.read("/tmp/wc_l").strip() == "2"

    # Test sort
    k.fs.write("/tmp/sort_test", "banana\napple\ncherry\n")
    sh.execute("sort /tmp/sort_test > /tmp/sort_res")
    assert k.fs.read("/tmp/sort_res") == "apple\nbanana\ncherry"

    # Test sort reverse
    sh.execute("sort -r /tmp/sort_test > /tmp/sort_res_r")
    assert k.fs.read("/tmp/sort_res_r") == "cherry\nbanana\napple"

    # Test uniq
    k.fs.write("/tmp/uniq_test", "a\na\nb\na\n")
    sh.execute("uniq /tmp/uniq_test > /tmp/uniq_res")
    # uniq groups adjacent, so: a, b, a
    assert k.fs.read("/tmp/uniq_res") == "a\nb\na"

    # uniq with counts
    sh.execute("uniq -c /tmp/uniq_test > /tmp/uniq_res_c")
    assert "2 a" in k.fs.read("/tmp/uniq_res_c")

    k.shutdown()


def test_shell_input_redirection(tmp_path, capsys):
    k = Kernel(config={"fs_backing": str(tmp_path / "store.json")})
    k.initialize()
    sh = k.shell

    # Create input file
    k.fs.write("/tmp/input.txt", "line1\nline2\nline3\n")

    # Run cat with input redirection
    sh.execute("cat < /tmp/input.txt > /tmp/out.txt")
    assert k.fs.read("/tmp/out.txt") == "line1\nline2\nline3\n"

    # Run wc with input redirection
    sh.execute("wc -l < /tmp/input.txt > /tmp/wc.txt")
    assert k.fs.read("/tmp/wc.txt").strip() == "3"

    # Test nonexistent input file redirection
    capsys.readouterr()
    res = sh.execute("cat < /tmp/missing.txt")
    captured = capsys.readouterr()
    assert "missing.txt: No such file or directory" in captured.out
    assert res is False

    k.shutdown()


def test_shell_persistent_history(tmp_path):
    k = Kernel(config={"fs_backing": str(tmp_path / "store.json")})
    k.initialize()
    sh = k.shell

    # Execute some commands
    sh.execute("mkdir /tmp")
    sh.execute("touch /tmp/abc")

    # Verify history has these commands
    assert "mkdir /tmp" in sh.history
    assert "touch /tmp/abc" in sh.history

    # Save history
    sh.save_history()
    assert k.fs.exists("/etc/history")
    history_content = k.fs.read("/etc/history")
    assert "mkdir /tmp\ntouch /tmp/abc" in history_content

    # Load history in a new shell instance
    sh2 = k.shell.__class__(k)
    assert not sh2.history
    sh2.load_history()
    assert "mkdir /tmp" in sh2.history
    assert "touch /tmp/abc" in sh2.history

    k.shutdown()


def test_shell_startup_script(tmp_path, capsys, monkeypatch):
    k = Kernel(config={"fs_backing": str(tmp_path / "store.json")})
    # Formats on boot, writing default /etc/pureosrc
    k.initialize()

    assert k.fs.exists("/etc/pureosrc")
    rc_content = k.fs.read("/etc/pureosrc")
    assert "alias ll ls -l" in rc_content

    # Mock input to raise EOFError immediately to exit run()
    def mock_input(prompt):
        raise EOFError()

    monkeypatch.setattr("builtins.input", mock_input)

    sh = k.shell
    sh.run()

    assert "ll" in sh.aliases
    assert sh.aliases["ll"] == "ls -l"

    k.shutdown()
