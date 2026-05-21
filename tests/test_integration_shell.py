import io
import contextlib
import time
import importlib
import os
import sys

try:
    kernel_mod = importlib.import_module("pureos.kernel")
except Exception:
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
    kernel_mod = importlib.import_module("pureos.kernel")

Kernel = kernel_mod.Kernel


def test_echo_redirection():
    k = Kernel()
    k.initialize()
    shell = k.shell

    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        res = shell.execute('echo hello > /tmp/hello', add_to_history=False)

    assert res is not False
    assert k.fs.read('/tmp/hello') == 'hello\n'
    k.shutdown()


def test_pipeline_capture():
    k = Kernel()
    k.initialize()
    shell = k.shell

    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        # echo with -e expands \n sequences
        res = shell.execute('echo -e "one\\ntwo\\nthree" | grep two', add_to_history=False)

    out = buf.getvalue().strip()
    assert 'two' in out
    k.shutdown()


def test_background_job_creates_process():
    k = Kernel()
    k.initialize()
    shell = k.shell

    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        res = shell.execute('sleep 0.05 &', add_to_history=False)

    # allow scheduler to spawn the background process
    time.sleep(0.02)
    procs = k.scheduler.list()
    assert any('sleep' in p.name for p in procs)
    k.shutdown()
