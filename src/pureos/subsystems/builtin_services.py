"""Built-in background services for v2-PureOS."""

import datetime
import time


def _noop_service(stop_event=None):
    # simple background task that can be stopped when given an event
    while not (stop_event and stop_event.is_set()):
        if stop_event:
            stop_event.wait(0.1)
        else:
            time.sleep(0.1)


def _echo_server_service(stop_event=None):
    from ..drivers.network import start_echo_server

    port, thread, srv_stop_event = start_echo_server(host="127.0.0.1", port=50007)
    while not (stop_event and stop_event.is_set()):
        if stop_event:
            stop_event.wait(0.1)
        else:
            time.sleep(0.1)
    srv_stop_event.set()
    thread.join()


def _http_server_service(kernel, stop_event=None):
    import http.server
    import socketserver

    class VFSHandler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            path = self.path
            if path == "/":
                path = "/index.html"

            # Simple path resolution for /var/www/html
            vfs_path = f"/var/www/html{path}"

            try:
                if kernel.fs.exists(vfs_path):
                    content = kernel.fs.read(vfs_path)
                    self.send_response(200)
                    self.send_header("Content-type", "text/html")
                    self.end_headers()
                    self.wfile.write(
                        content.encode("utf-8") if isinstance(content, str) else content
                    )
                else:
                    self.send_error(404, "File Not Found")
            except Exception as e:
                self.send_error(500, str(e))

        def log_message(self, format, *args):
            # Log to kernel logger instead of stderr
            kernel.logger.info("HTTP: " + (format % args))

    port = 80
    handler = VFSHandler

    # We'll try port 80, if fails try 8080 (common for dev), then try any ephemeral port
    httpd = None
    try:
        httpd = socketserver.TCPServer(("127.0.0.1", port), handler)
    except Exception:
        try:
            port = 8080
            httpd = socketserver.TCPServer(("127.0.0.1", port), handler)
        except Exception:
            try:
                port = 0
                httpd = socketserver.TCPServer(("127.0.0.1", port), handler)
                port = httpd.server_address[1]
            except Exception as exc:
                kernel.logger.error("Failed to start HTTP server: %s", exc)
                return

    # Register socket in driver
    net_driver = kernel.drivers.drivers.get("network")
    if net_driver:
        net_driver.add_socket("tcp", "LISTEN", f"127.0.0.1:{port}", "0.0.0.0:*")

    httpd.timeout = 0.5
    while not (stop_event and stop_event.is_set()):
        httpd.handle_request()

    httpd.server_close()
    if net_driver:
        net_driver.remove_socket(f"127.0.0.1:{port}", "0.0.0.0:*")


def _field_matches(
    field_str: str, current_val: int, min_val: int, max_val: int
) -> bool:
    if field_str == "*":
        return True

    parts = field_str.split(",")
    for part in parts:
        part = part.strip()
        if not part:
            continue

        step = 1
        range_part = part
        if "/" in part:
            range_part, step_str = part.split("/", 1)
            try:
                step = int(step_str)
                if step <= 0:
                    continue
            except ValueError:
                continue

        if range_part == "*":
            vals = list(range(min_val, max_val + 1))
        elif "-" in range_part:
            start_str, end_str = range_part.split("-", 1)
            try:
                start = int(start_str)
                end = int(end_str)
            except ValueError:
                continue
            vals = list(range(start, end + 1))
        else:
            try:
                val = int(range_part)
                vals = [val]
            except ValueError:
                continue

        matching_vals = [v for idx, v in enumerate(vals) if idx % step == 0]
        if current_val in matching_vals:
            return True
        if current_val == 0 and 7 in matching_vals:
            return True

    return False


def _cron_service(kernel, stop_event=None):
    MONTHS = {
        "jan": 1,
        "feb": 2,
        "mar": 3,
        "apr": 4,
        "may": 5,
        "jun": 6,
        "jul": 7,
        "aug": 8,
        "sep": 9,
        "oct": 10,
        "nov": 11,
        "dec": 12,
    }
    DAYS = {"sun": 0, "mon": 1, "tue": 2, "wed": 3, "thu": 4, "fri": 5, "sat": 6}

    def normalize_field(field_str: str, mapping: dict) -> str:
        s = field_str.lower()
        for name, num in mapping.items():
            s = s.replace(name, str(num))
        return s

    last_run_time = None

    while not (stop_event and stop_event.is_set()):
        now = datetime.datetime.now()
        current_time = (now.year, now.month, now.day, now.hour, now.minute)

        if current_time != last_run_time:
            last_run_time = current_time

            crontab_path = "/etc/crontab"
            if kernel.fs.exists(crontab_path):
                try:
                    content = kernel.fs.read(crontab_path)
                except Exception:
                    content = ""

                if content:
                    min_val = now.minute
                    hour_val = now.hour
                    dom_val = now.day
                    mon_val = now.month
                    dow_val = (now.weekday() + 1) % 7

                    for line in content.splitlines():
                        line = line.strip()
                        if not line or line.startswith("#"):
                            continue

                        parts = line.split(maxsplit=5)
                        if len(parts) < 6:
                            continue

                        if any("=" in f for f in parts[:5]):
                            continue

                        f_min, f_hour, f_dom, f_mon, f_dow = parts[:5]
                        command = parts[5]

                        f_mon = normalize_field(f_mon, MONTHS)
                        f_dow = normalize_field(f_dow, DAYS)

                        try:
                            match_min = _field_matches(f_min, min_val, 0, 59)
                            match_hour = _field_matches(f_hour, hour_val, 0, 23)
                            match_dom = _field_matches(f_dom, dom_val, 1, 31)
                            match_mon = _field_matches(f_mon, mon_val, 1, 12)
                            match_dow = _field_matches(f_dow, dow_val, 0, 6)
                        except Exception:
                            continue

                        if (
                            match_min
                            and match_hour
                            and match_dom
                            and match_mon
                            and match_dow
                        ):

                            def make_target(cmd):
                                def run_job(stop_event=None):
                                    from ..shell.shell import Shell

                                    subshell = Shell(kernel)
                                    subshell.execute(cmd, add_to_history=False)

                                return run_job

                            kernel.scheduler.spawn(
                                f"cron:{command}", target_func=make_target(command)
                            )

        if stop_event:
            stop_event.wait(1.0)
        else:
            time.sleep(1.0)


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

    kernel.register_service(
        "cron",
        lambda stop_event=None: _cron_service(kernel, stop_event),
        daemon=True,
        stoppable=True,
        description="Cron daemon background service",
        auto_start=True,
    )

    kernel.register_service(
        "http_server",
        lambda stop_event=None: _http_server_service(kernel, stop_event),
        daemon=True,
        stoppable=True,
        description="HTTP server service on port 80",
        auto_start=False,
    )
