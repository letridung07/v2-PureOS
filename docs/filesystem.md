# Virtual Filesystem Architecture

v2-PureOS implements a custom in-memory filesystem that simulates standard UNIX-like behavior, including nested directories, file metadata (permissions), and persistence. 

## State-Manager Architecture

The filesystem (`pureos.fs`) is built using a State-Manager pattern, separating data from behavior to improve modularity and maintainability.

### `FSState` (`state.py`)
This is a simple data container that holds:
- `files`: A dictionary mapping absolute paths to file contents (strings).
- `dirs`: A set of absolute directory paths (always ending with `/`).
- `modes`: A dictionary mapping paths to their UNIX-style permission modes (e.g., `0o755`, `0o644`).
- `backing_path`: An optional file path on the host system used to persist the filesystem state.

### `FSOperations` (`operations.py`)
This component implements the core filesystem manipulations (e.g., `mkdir`, `read`, `write`, `delete`, `rename`, `copy`). It delegates to other components:
- Calls `FSPermissions` to check access rights before executing a command.
- Calls `PathResolver` to normalize user input paths.
- Modifies `FSState`.
- Calls `FSPersistence` to save state changes if a backing file is configured.

### `PathResolver` (`path.py`)
Responsible for normalizing paths. It resolves `..`, handles redundant slashes, and correctly formats directories (ensuring they end in a `/` when requested).

### `FSPermissions` (`permissions.py`)
Checks UNIX-style permissions based on bitwise operations. It provides methods to enforce security rules, including:
- **rwxrwxrwx** checks for owner, group, and others.
- **Sticky Bit (0o1000)** enforcement on directories to prevent unauthorized deletions (users can only delete/rename files they own in sticky directories).
- **Execute Permission (0o100)** verification for shell scripts and dynamic commands.
- **SUID/SGID (0o4000/0o2000)** support for privilege elevation during command and script execution.


### `FSPersistence` (`persistence.py`)
Handles loading and saving the `FSState` to a JSON file. This allows v2-PureOS to resume from where it left off across reboots.

## Filesystem Interface (`VirtualFS`)

The `VirtualFS` class (`core.py`) serves as the primary facade for the OS to interact with the filesystem. It composes all the above components together and exposes high-level methods that mirror standard library filesystem interfaces.

### Python Module Import mapping
The `VirtualFS` supports direct Python module imports via a custom `VFSImporter`. This maps specific VFS directories to the `pureos_vfs` namespace:
- `/usr/lib/python/` maps to `pureos_vfs.*`
- `/usr/lib/pureos/packages/` maps to `pureos_vfs.packages.*`

This allows the OS to load drivers and dynamic shell commands using standard Python `import` statements.

## Standard System Files

v2-PureOS uses several standardized files in the `/etc/` directory to manage system state and configuration:

- **/etc/passwd**: Stores user account information (username, UID, GID, password hash).
- **/etc/group**: Stores group information and memberships.
- **/etc/hosts**: Local hostname-to-IP mappings for simulated DNS resolution.
- **/etc/resolv.conf**: Mock DNS configuration, specifying nameserver hints.
- **/etc/crontab**: The system-wide schedule for the background `cron` service.
- **/etc/motd**: "Message of the Day" — displayed by the shell upon login.
- **/etc/pureosrc**: Default shell initialization script (aliases, exports).
- **/etc/iptables/rules**: Persisted firewall rules for the `iptables` command.
- **/proc/meminfo**: Global memory statistics (MemTotal, MemFree, MemAvailable, Cached, SwapTotal, SwapFree), updated by the MemoryDriver on every memory operation.
- **/proc/<pid>/status**: Per-process memory and status information (Name, Pid, State, VmSize, VmRSS), maintained for each process with active memory allocations.

