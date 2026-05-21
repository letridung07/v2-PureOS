from pureos.services import ServiceManager


def test_service_start_records_failure():
    sm = ServiceManager()

    def bad_svc():
        raise RuntimeError("boom")

    sm.register("bad", bad_svc, daemon=False, stoppable=False)
    t = sm.start("bad")
    # wait for the thread to run and finish
    t.join(timeout=0.2)
    status = sm.status("bad")
    assert status is not None
    assert status["error"] is not None
