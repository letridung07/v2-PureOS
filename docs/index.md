# v2-PureOS Documentation

Welcome to the documentation for v2-PureOS. This guide provides a reference for the system, including how the shell works, available commands, filesystem behavior, service management, and project structure.

## Documentation Index

For detailed information about the inner workings of v2-PureOS, please consult the following specialized documentation files:

- [v2-PureOS Architecture](architecture.md): Kernel, Boot Sequence, Process Scheduler, Service Manager, and Networking.
- [Virtual Filesystem Architecture](filesystem.md): State-Manager pattern, path resolution, permissions, and persistence.
- [Shell and Commands](shell_and_commands.md): The shell execution lifecycle, command chaining, piping, redirection, and creating custom commands.
- [Text Pipeline Tools](text_tools.md): `wc`, `grep`, `sort`, `uniq`, `cut`, `tr`, and `xargs` — composable text processors.
- [Cron Daemon](cron.md): Scheduled background tasks, syntax format, and `crontab` command.

---

## Overview

v2-PureOS is a minimal OS-like system built with Python 3.8+. The package includes:

- `pureos.kernel` — kernel initialization and service startup
- `pureos.boot` — system boot sequence and startup scripts
- `pureos.builtin_services` — default background services
- `pureos.fs` — virtual filesystem
- `pureos.commands` — interactive shell command registry and modular commands
- `pureos.services` — lightweight service management
- `pureos.processes` — simple process scheduler and lifecycle control
- `pureos.shell` — interactive shell loop and command parsing

## Quickstart: Running the shell

From the project root:

```bash
python3 main.py --shell
```

This prints a startup banner and system info, then enters the shell prompt.

Package-style execution:

```bash
PYTHONPATH=src python3 -m pureos --shell
```

### CLI options

The package supports the following launch options:

- `--shell` — start the interactive shell after initialization
- `--version` — print the package version and exit
- `--backing <path>` — use a persistent backing file for the virtual filesystem

---

## Command Cheatsheet

Below is a quick reference for the commands available within the v2-PureOS interactive shell. For details on how commands are parsed and executed, see [Shell and Commands](shell_and_commands.md).

### General Shell

- `;` — run commands sequentially
- `&&` — run the next command only if the previous succeeded
- `||` — run the next command only if the previous failed
- `|` — pipe command output into the next built-in command
- `export VAR=value` — set a shell variable
- `$VAR` — substitute the variable value in the command line
- `alias name command` — define a shorthand command
- `unalias name` — remove an alias
- `history` — display the session command history
- `env` / `printenv` — list all active environment variables
- `clear` — clear the terminal screen

### File system

- `pwd` — show current working directory
- `cd <path>` — change directory
- `find [path]` — recursively list files and directories under a path
- `ls [-l] [prefix]` — list directory contents or a file
- `cat <path>` — display file contents
- `write <path> <content>` — overwrite or create a file
- `append <path> <content>` — append text to a file
- `echo <text> > <path>` — write redirected text to a file
- `mkdir <path>` — create a directory
- `touch <path>` — create or update a file
- `rm <path>` — delete a file or directory
- `rmdir <path>` — remove an empty directory
- `mv <src> <dst>` — rename or move an entry
- `cp <src> <dst>` — copy a file or directory
- `format` — reset the virtual filesystem to initial state
- `chmod <mode> <path>` — set a file or directory mode
- `stat <path>` — display metadata for a path
- `source <path>` — read a file and execute each non-comment line as a shell command
- `head <path> [n]` — display the first `n` lines of a file (default 10)
- `tail <path> [n]` — display the last `n` lines of a file (default 10)
- `tar [-c|-x|-t] [-z] [-v] [-C <dir>] -f <archive> [paths...]` — create, extract, or list files in a tar archive

### Text Pipeline Tools

All commands below are pipeline-aware: they read from a file argument **or** from stdin (a prior pipe stage).

- `wc [-l] [-w] [-c] [file]` — count lines, words, and bytes
- `grep [-i] [-v] [-n] [-c] [-E] <pattern> [file]` — filter lines by pattern; `-i` case-insensitive, `-v` invert, `-n` number, `-c` count, `-E` extended regex
- `sort [-r] [-n] [-u] [file]` — sort lines; `-r` reverse, `-n` numeric, `-u` deduplicate
- `uniq [-c] [-d] [-u] [file]` — deduplicate adjacent lines; `-c` prefix count, `-d` dup-only, `-u` unique-only
- `cut -f <fields> [-d <delim>] [file]` — extract delimited fields (e.g. `-f 1,3 -d :`)
- `cut -c <range> [file]` — extract character positions (e.g. `-c 1-5`)
- `tr [-d] [-s] <set1> [set2]` — translate or delete characters; supports `a-z` ranges
- `base64 [-d] [file]` — encode or decode text using Base64
- `xargs [-n <max>] <command> [args...]` — build commands from stdin words

### Processes & Services

- `ps` — list active processes
- `spawn <name>` — create a new process with a name
- `kill <pid>` — terminate a process by PID
- `wait [pid]...` — wait for specific background processes (or all active background processes if none specified) to complete
- `services` — list registered services
- `service start <name>` — start a service
- `pkg [install <url> <name> | list | remove <name>]` — manage dynamic commands downloaded from the web
- `service stop <name>` — stop a service
- `service status <name>` — show service state
- `service restart <name>` — restart a service
- `crontab [-l|-r|<file>]` — list, remove, or install a crontab schedule file

### Example session

```text
v2-pureos> mkdir /tmp
v2-pureos> write /tmp/hello "hello world"
v2-pureos> cat /tmp/hello
v2-pureos> chmod 600 /tmp/hello
v2-pureos> service status noop
v2-pureos> spawn worker
v2-pureos> ps
v2-pureos> exit
```

---

## Testing

Run the test suite from the repository root:

```bash
python3 -m pip install -q pytest pytest-cov
pytest
```

## Project structure

- `main.py` — executable launcher script
- `src/pureos` — main Python package
- `tests` — unit and integration tests
- `docs/` — comprehensive documentation
  - `index.md` — landing page and command reference
  - `architecture.md` — system architecture overview
  - `filesystem.md` — virtual filesystem internals
  - `shell_and_commands.md` — shell parsing and command plugins

## Design notes

This project is not a production operating system. It is intended as a demonstration of Python-based OS-like subsystems and shell interaction.
