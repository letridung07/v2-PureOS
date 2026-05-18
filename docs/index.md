# v2-PureOS Documentation

This guide provides a detailed reference for v2-PureOS, including how the shell works, available commands, filesystem behavior, service management, and project structure.

## Overview

v2-PureOS is a minimal OS-like system built with Python 3.8+. The package includes:

- `pureos.kernel` — kernel initialization and service startup
- `pureos.fs` — virtual filesystem with path resolution and permission checks
- `pureos.commands` — interactive shell command registry
- `pureos.services` — lightweight service management
- `pureos.processes` — simple process scheduler and lifecycle control
- `pureos.shell` — interactive shell loop and command parsing

## Running the shell

From the project root:

```bash
python3 main.py --shell
```

This prints a startup banner and system info, then enters the shell prompt.

Package-style execution:

```bash
PYTHONPATH=src python3 -m pureos --shell
```

## CLI options

The package supports the following launch options:

- `--shell` — start the interactive shell after initialization
- `--version` — print the package version and exit

## Shell command workflow

The shell accepts a single command line or a chained command sequence. Command chaining is supported using:

- `;` — run commands sequentially
- `&&` — run the next command only if the previous succeeded
- `||` — run the next command only if the previous failed

Quoted strings are preserved during parsing, allowing multi-word content for commands such as `write` and `append`.

## File system commands

The shell exposes a virtual filesystem with support for relative and absolute paths. The current working directory is tracked in the shell and affects relative path resolution.

### Navigation

- `pwd` — show current working directory
- `cd <path>` — change directory
- `find [path]` — recursively list files and directories under a path
- `ls [-l] [prefix]` — list directory contents or a file

### File operations

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

### Permissions and metadata

- `chmod <mode> <path>` — set a file or directory mode
- `stat <path>` — display metadata for a path

### Shell scripting

- `source <path>` — read a file from the virtual filesystem and execute each non-comment line as a shell command

### File preview

- `head <path> [n]` — display the first `n` lines of a file (default 10)
- `tail <path> [n]` — display the last `n` lines of a file (default 10)

## Process and service commands

v2-PureOS includes basic process and service management from the shell.

### Processes

- `ps` — list active processes
- `spawn <name>` — create a new process with a name
- `kill <pid>` — terminate a process by PID

### Services

- `services` — list registered services
- `service start <name>` — start a service
- `service stop <name>` — stop a service
- `service status <name>` — show service state
- `service restart <name>` — restart a service

## Example commands

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
- `docs/index.md` — detailed user and command reference

## Design notes

This project is not a production operating system. It is intended as a demonstration of Python-based OS-like subsystems and shell interaction.
