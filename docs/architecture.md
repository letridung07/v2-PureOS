# v2-PureOS Architecture

This document provides a detailed overview of the core architectural components of v2-PureOS. The system is designed to simulate OS-like behavior within a Python runtime, with discrete components handling distinct responsibilities.

## 1. The Kernel (`pureos.kernel`)

The Kernel is the central orchestrator of v2-PureOS. It initializes and manages the lifecycle of the entire system.

**Key Responsibilities:**
- **Initialization**: Bootstrapping the Virtual Filesystem (`VirtualFS`), Scheduler, and Service Manager.
- **Boot Sequence Execution**: Running `run_boot_sequence` to ensure the filesystem is formatted or populated with default configurations (e.g., `/etc/motd`, `/etc/pureosrc`).
- **Service Registration**: Registering default built-in background services via `register_builtin_services`.
- **System Lifecycle**: Handling the `initialize()` routine (starting auto-started services) and the `shutdown()` routine (gracefully stopping all processes and services).

## 2. Boot Sequence (`pureos.boot`)

The boot sequence simulates the early user-space initialization (similar to an init system).

- It checks if the filesystem is empty or if the `format_on_boot` configuration is set.
- If necessary, it creates essential files like `/etc/motd` (Message of the Day) and `/etc/pureosrc` (default shell aliases).

## 3. Process Manager (`pureos.processes`)

The `Scheduler` provides a simplified process management layer. Each process runs in its own background daemon thread.

**Features:**
- **Process Spawning**: Using `spawn(name, target_func)`, you can launch arbitrary Python functions as isolated background "processes".
- **Tracking & Status**: Each process is assigned a PID and a status (`running`, `completed`, `failed`, `killed`).
- **Control**: Supports waiting for processes (`wait()`) and forcefully terminating them (`kill()`). Threads are cooperative; long-running functions should check `stop_event.is_set()` if passed.

## 4. Service Manager (`pureos.services`)

The `ServiceManager` handles long-running, daemonized tasks. Unlike ephemeral processes, services are designed to be stopped and restarted.

**Service Types:**
- **Non-stoppable**: Basic background threads that run until completion or system shutdown.
- **Stoppable**: Functions that accept a `stop_event` (a `threading.Event`). These can be gracefully stopped using `service stop <name>`.

**Service States:** `stopped`, `starting`, `running`, `stopping`, `failed`.

## 5. Networking (`pureos.network`)

v2-PureOS includes minimal networking utilities to simulate network access.

- **Host Resolution**: `resolve_host` simulates DNS resolution. It first checks `/etc/hosts` in the VirtualFS. If not found, it falls back to the real system's `socket.gethostbyname()`.
- **Background Servers**: Functions like `start_echo_server` demonstrate how networking can integrate with the process and service managers.

---
*For details on the filesystem, see [Virtual Filesystem Architecture](filesystem.md).*
*For details on the shell and CLI, see [Shell and Command Execution](shell_and_commands.md).*
