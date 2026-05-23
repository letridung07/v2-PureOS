import time

from pureos.subsystems.services import ServiceManager


def test_stop_all_no_threads():
    sm = ServiceManager()
    # Should not raise and should return quickly when no threads
    sm.stop_all(timeout=None)


def test_stop_all_joins_running_service():
    sm = ServiceManager()

    def svc(stop_event=None):
        # block until stop_event is set by ServiceManager.stop
        if stop_event:
            stop_event.wait(1)

    sm.register("testsvc", svc, daemon=False, stoppable=True)
    _ = sm.start("testsvc")
    # allow service thread to start
    time.sleep(0.01)
    sm.stop_all(timeout=1.0)
    # After stop_all, service thread should be stopped (joined)
    assert not any(thread.is_alive() for thread in sm._threads.values())
