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
Checks UNIX-style permissions based on bitwise operations. It provides methods like `ensure_parent_writable` and `ensure_readable_file` to enforce security rules.

### `FSPersistence` (`persistence.py`)
Handles loading and saving the `FSState` to a JSON file. This allows v2-PureOS to resume from where it left off across reboots.

## Filesystem Interface (`VirtualFS`)

The `VirtualFS` class (`core.py`) serves as the primary facade for the OS to interact with the filesystem. It composes all the above components together and exposes high-level methods that mirror standard library filesystem interfaces.
