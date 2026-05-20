import time
import pytest
from pureos.kernel import Kernel
from pureos.shell import Shell

@pytest.fixture
def kernel():
    k = Kernel()
    k.initialize()
    yield k
    k.shutdown()

@pytest.fixture
def shell(kernel):
    return Shell(kernel)

def test_job_control_suspend_resume_bg(shell, kernel):
    # Process that increments a file content
    def worker(stop_event=None, resume_event=None):
        count = 0
        while not (stop_event and stop_event.is_set()):
            if resume_event:
                resume_event.wait()
            kernel.fs.write("/tmp/count", str(count))
            count += 1
            time.sleep(0.05)
            
    p = kernel.scheduler.spawn("worker", target_func=worker)
    pid = p.pid
    
    time.sleep(0.2)
    c1 = int(kernel.fs.read("/tmp/count") or "0")
    assert c1 > 0
    
    # Suspend it
    shell.execute(f"kill -STOP {pid}")
    assert kernel.scheduler.status(pid).status == "suspended"
    
    time.sleep(0.2)
    c2 = int(kernel.fs.read("/tmp/count") or "0")
    # Should be suspended
    assert c2 <= c1 + 2
    
    # Resume it via bg
    shell.execute(f"bg {pid}")
    assert kernel.scheduler.status(pid).status == "running"
    
    time.sleep(0.2)
    c3 = int(kernel.fs.read("/tmp/count") or "0")
    assert c3 > c2
    
    # Cleanup
    kernel.scheduler.kill(pid)

def test_job_control_fg_resumes(shell, kernel):
    def worker(stop_event=None, resume_event=None):
        # Just run for a bit
        time.sleep(0.2)
            
    p = kernel.scheduler.spawn("worker", target_func=worker)
    pid = p.pid
    
    # Suspend it
    shell.execute(f"kill -STOP {pid}")
    assert kernel.scheduler.status(pid).status == "suspended"
    
    # Fg should resume and wait
    start = time.time()
    shell.execute(f"fg {pid}")
    end = time.time()
    
    # Should be completed now
    assert kernel.scheduler.status(pid).status == "completed"
    # Should have waited at least some time
    assert end - start > 0.1

def test_kill_resumes_to_die(shell, kernel):
    # If a process is suspended, kill should still work
    def worker(stop_event=None, resume_event=None):
        while not (stop_event and stop_event.is_set()):
            if resume_event:
                resume_event.wait()
            time.sleep(0.01)
            
    p = kernel.scheduler.spawn("worker", target_func=worker)
    pid = p.pid
    
    shell.execute(f"kill -STOP {pid}")
    assert kernel.scheduler.status(pid).status == "suspended"
    
    # Kill it
    shell.execute(f"kill {pid}")
    kernel.scheduler.wait(pid, timeout=1.0)
    assert kernel.scheduler.status(pid).status == "killed"

def test_jobs_shows_suspended(shell, kernel):
    p = kernel.scheduler.spawn("test_job", runtime=10)
    pid = p.pid
    
    shell.execute(f"kill -STOP {pid}")
    
    import io
    import contextlib
    f = io.StringIO()
    with contextlib.redirect_stdout(f):
        shell.execute("jobs")
    output = f.getvalue()
    
    assert f"[{pid}] suspended" in output
    
    kernel.scheduler.kill(pid)
