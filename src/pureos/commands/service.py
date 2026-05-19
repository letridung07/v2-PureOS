from typing import List

from .base import Command


class ServicesCommand(Command):
    name = "services"
    usage = "services"
    description = "List registered services."

    def execute(
        self, parts: List[str], input_data=None, capture_output=False, raw_line=None
    ):
        print(", ".join(self.kernel.services.list()))
        return True


class ServiceCommand(Command):
    name = "service"
    usage = "service start|stop|status|restart <name>"
    description = "Control a registered service."

    def execute(
        self, parts: List[str], input_data=None, capture_output=False, raw_line=None
    ):
        if len(parts) < 3:
            print("Usage: service start|stop|status|restart <name>")
            return False
        action = parts[1]
        name = parts[2]
        if action == "start":
            try:
                self.kernel.services.start(name)
                print(f"Started service {name}")
                return True
            except KeyError:
                print(f"{name}: not registered")
                return False
        if action == "stop":
            self.kernel.services.stop(name)
            print(f"Stopped service {name}")
            return True
        if action == "status":
            st = self.kernel.services.status(name)
            if st is None:
                print(f"{name}: not registered")
                return False
            print(f"running={st['alive']}, stoppable={st['stoppable']}")
            return True
        if action == "restart":
            self.kernel.services.restart(name)
            print(f"Restarted service {name}")
            return True
        print("Unknown service action")
        return False


def register_service_commands(registry):
    registry.register(ServicesCommand(registry.kernel))
    registry.register(ServiceCommand(registry.kernel))
