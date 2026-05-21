# v2-PureOS Architecture

This document provides a detailed overview of the core architectural components of v2-PureOS. The system is designed to simulate OS-like behavior within a Python runtime, with discrete components handling distinct responsibilities.

## 1. The Kernel (`pureos.kernel`)

The Kernel is the central orchestrator of v2-PureOS. It initializes and manages the lifecycle of the entire system.

**Key Responsibilities:**
- **Initialization**: Bootstrapping the Virtual Filesystem (`VirtualFS`), Scheduler, Service Manager, Command Registry, and Package Manager.
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
- **Process Spawning**: Using `spawn(name, target_func)` (or the shell `spawn <name> [runtime]` command), you can launch arbitrary Python functions or a dummy/timer task with an optional `runtime` (default: 5.0 seconds) as isolated background "processes".
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

## 6. User Management (`pureos.users`)

The `UserDB` provides POSIX-like user and group management, enabling permission-based access control and multi-user simulation.

**Features:**
- **User Database**: Stores `User` objects with properties like `uid`, `gid`, `password_hash`, and secondary groups.
- **Persistence**: User and group information is stored in the VirtualFS at `/etc/passwd` and `/etc/group`.
- **Authentication**: Supports password hashing (SHA-256) and account locking.
- **Root & Privileges**: Includes a built-in `root` user (UID 0) and support for `sudo` via membership in the `sudo` group.
- **Session Control**: Manages the `current_user` context, which is used by the filesystem to enforce permission checks.

---
*For details on the filesystem, see [Virtual Filesystem Architecture](filesystem.md).*
*For details on the shell and CLI, see [Shell and Command Execution](shell_and_commands.md).*

## 7. Memory Manager (`pureos.memory`)

The `MemoryDriver` tracks global and per-process memory usage across physical RAM and swap space. It is loaded as a kernel driver and integrates with the scheduler on process spawn/exit.

**Features:**
- **Physical + Swap Model**: Allocations draw from physical RAM first, with spill to swap when physical is exhausted. The driver tracks `used_kb`, `cached_kb`, `swap_used_kb`, and `swap_total_kb`.
- **Per-Process Accounting**: Each allocation updates the Process dataclass fields `vsize` (virtual size) and `rss` (resident set size) in KB.
- **Capacity Checks**: Before allocating, the driver verifies that total (physical + swap) free space is sufficient. Physical-free-first allocation is enforced when `total_kb > 0`; unlimited mode is entered when `total_kb == 0`.
- **LIFO Free**: Frees drain swap first, then physical, matching the reverse of allocation order.
- **`/proc` Virtual Filesystem**: The driver writes `/proc/meminfo` (global stats) and `/proc/<pid>/status` (per-process VmSize/VmRSS) into the kernel VirtualFS on every alloc/free, making memory stats readable via standard commands like `cat /proc/meminfo`.
- **Startup Cleanup**: On `on_load`, stale `/proc/<pid>/` directories from previous sessions are purged. On process exit, `free_all` deletes the per-pid `/proc/<pid>/` directory tree.

## 8. Package Manager (`pureos.pkg`)

v2-PureOS supports runtime extension via the `PackageManager` subsystem and the user-facing `pkg` command. This allows the system to download, install, list, and remove shell commands dynamically.

**Mechanism:**
- **Encapsulation**: The package management logic is encapsulated in `pureos.pkg.PackageManager`.
- **Storage**: Packages are stored as Python scripts in the VirtualFS at `/usr/lib/pureos/packages/`.
- **Loading**: The `PackageManager` uses the centralized `CommandRegistry` (now managed by the `Kernel` as `kernel.registry` to unify command lookup) and a custom `VFSImporter` (implementing `importlib`) to import packages from the VirtualFS. This provides proper namespacing (under `pureos_vfs.packages.*`), standard tracebacks, and supports multi-file packages and dependencies.
- **Persistence**: During the boot sequence (`pureos.boot`), the `PackageManager` automatically scans the packages directory and re-registers any previously installed commands.

## 9. System Logging (`pureos.syslog`)

The `SyslogDriver` provides a centralized logging subsystem that implements standard Python `logging.Handler` interfaces, capturing records logged to the `pureos` logger and storing them in `/var/log/syslog` within the virtual filesystem.

**Features:**
- **Re-entrancy Guard**: Implements thread-local re-entrancy prevention (`emit_active` and `writing` flags) to avoid infinite recursion when filesystem operations (such as appending to `/var/log/syslog`) generate log messages themselves.
- **Buffer & File Writing**: Limits the in-memory buffer to 500 records while maintaining a persistent text log at `/var/log/syslog`.
- **Context Elevation**: Temporarily elevates the current active user context to `root` when writing or clearing syslog files to avoid permission errors from regular user sessions.
