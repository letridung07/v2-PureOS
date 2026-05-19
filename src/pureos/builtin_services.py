"""Built-in background services for v2-PureOS."""

import time


def _noop_service(stop_event=None):
    # simple background task that can be stopped when given an event
    while not (stop_event and stop_event.is_set()):
        if stop_event:
            stop_event.wait(0.1)
        else:
            time.sleep(0.1)


def _echo_server_service(stop_event=None):
    from .network import start_echo_server

    port, thread, srv_stop_event = start_echo_server(host="127.0.0.1", port=50007)
    while not (stop_event and stop_event.is_set()):
        if stop_event:
            stop_event.wait(0.1)
        else:
            time.sleep(0.1)
    srv_stop_event.set()
    thread.join()


def register_builtin_services(kernel):
    """Register all built-in background services with the kernel."""
    kernel.register_service(
        "noop",
        _noop_service,
        daemon=True,
        stoppable=True,
        description="No-op background service",
        auto_start=True,
    )

    kernel.register_service(
        "echo_server",
        _echo_server_service,
        daemon=True,
        stoppable=True,
        description="TCP echo server on port 50007",
        auto_start=False,
    )
