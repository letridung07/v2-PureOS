# Shell and Commands

The interactive shell in v2-PureOS simulates standard bash-like behavior, including command chaining, piping, redirection, and environment variables.

## Execution Lifecycle

When a user enters a command line in the shell (`pureos.shell.Shell`), the following steps occur:

1. **History Recall**:
   Lines starting with `!` are processed for history recall:
   - `!N`: Recalls the N-th command in the history (1-based).
   - `!prefix`: Recalls the most recent command starting with `prefix`.
   The recalled command is printed and then executed.
2. **Command Sequence Splitting (`parser.py`)**: 
   The input line is split into logical execution units using `&&` (AND), `||` (OR), and `;` (sequential). Background jobs (`&`) are also separated here.
3. **Environment Variable Substitution**:
   Variables prefixed with `$` or enclosed in `${}` are substituted with their values from the shell's environment map.
4. **Pipeline Splitting**:
   Each command sequence is further split by the pipe operator `|`. Output from the left command becomes the input to the right command.
5. **Redirection Processing**:
   The parser scans for `>` (overwrite), `>>` (append), and `<` (input redirection). Redirect targets are handled within the VirtualFS.
6. **Tokenization & Aliasing**:
   The command string is split into tokens (words), respecting quotes (`"` and `'`) and escaped characters (`\`). The first token is checked against defined aliases; if a match is found, the alias is expanded recursively (up to 10 levels deep to prevent infinite loops).
7. **Execution (`commands.registry.CommandRegistry`)**:
   The `CommandRegistry` looks up the command class based on the first token and calls its `execute` method, passing the parsed tokens, pipeline input data (if any), and whether the output should be captured or directly printed.

## Command Registry

Commands are dynamically registered on startup by scanning the `pureos.commands` package. 

- **Automatic Registration**: Any class inheriting from `Command` that has a `name` attribute is automatically registered.
- **Manual Registration**: Modules can optionally provide a `register_<module>_commands(registry)` function for custom registration logic.

## Creating New Commands

To create a new shell command, create a subclass of `Command` (`pureos.commands.base.Command`).

### Dynamic Commands
Commands can be installed at runtime using the `pkg install <url> <name>` command. These are stored in `/usr/lib/pureos/packages/` and loaded as Python modules. When loaded via the `pkg` system, common dependencies like `Command`, `json`, `re`, and `math` are automatically injected into the module namespace for convenience.

## Driver System

For more persistent system extensions that require background logic or lifecycle management, v2-PureOS provides a **Driver** system.

### Creating a Driver
Create a subclass of `Driver` (`pureos.drivers.Driver`) and implement the lifecycle methods:

```python
from pureos.drivers import Driver

class MyDriver(Driver):
    name = "mydriver"
    description = "A persistent system driver"

    def on_load(self):
        self.logger.info("Driver loaded")

    def start(self):
        self.logger.info("Driver started")

    def stop(self):
        self.logger.info("Driver stopped")
```

### Driver Management
Drivers can be managed using the `driver` command:
- `driver list`: List all loaded drivers.
- `driver load <module> <class>`: Load a driver from a module (e.g., `driver load pureos_vfs.my_mod MyDriver`).
- `driver unload <name>`: Unload a specific driver.

## Memory Commands

The memory management subsystem provides several commands for inspecting system and per-process memory usage. All commands read live data from the `MemoryDriver`.

### `mem` — Memory Statistics
```text
mem [pid]
```

Without arguments, displays global memory statistics (Total, Used, Free, Cached, Available, Swap Total/Used) followed by a per-process table showing VSZ, RSS, and `%MEM` for every process with active allocations.

With a `pid`, shows detailed memory info for that specific process (Status, VSZ, RSS, %MEM, Nice value).

### `free` — Memory Usage Display
```text
free [-h]
```

Displays a human-readable table of memory usage (Mem: total, used, free, buff/cache, available; Swap: total, used, free). The `-h` flag formats values as human-readable sizes (GiB, MiB, KiB).

### `ps` — Enhanced Process Listing
The `ps` command now includes `VSZ` and `RSS` columns alongside the existing PID, NAME, STATUS, START, TIME, and NI columns.

### `top` — One-Shot Process Snapshot
The `top` command now includes an `RSS` column showing resident memory per process alongside elapsed time.
