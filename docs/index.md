# v2-PureOS Documentation

Welcome to the documentation for v2-PureOS. This guide provides a reference for the system, including how the shell works, available commands, filesystem behavior, service management, and project structure.

## Documentation Index

For detailed information about the inner workings of v2-PureOS, please consult the following specialized documentation files:

- [v2-PureOS Architecture](architecture.md): Kernel, Boot Sequence, Process Scheduler, Service Manager, Memory Manager, and Networking.
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
- `pureos.pkg` — dynamic package manager subsystem
- `pureos.services` — lightweight service management
- `pureos.processes` — simple process scheduler and lifecycle control
- `pureos.memory` — memory management subsystem (allocation, swap, /proc filesystem)
- `pureos.drivers` — system driver manager and base driver class
- `pureos.syslog` — system logging driver subsystem
- `pureos.users` — POSIX-like user and group database
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
- `!N` / `!prefix` — recall command from history (e.g. `!10` or `!ls`)
- `export VAR=value` — set a shell variable
- `$VAR` — substitute the variable value in the command line
- `alias name command` — define a shorthand command
- `unalias name` — remove an alias
- `history` — display the session command history
- `help` — show available commands and usage
- `env` / `printenv` — list all active environment variables
- `which <command>` — locate a command in the path
- `clear` — clear the terminal screen
- `exit` — terminate the shell session

### System Information

- `uptime` — show how long the system has been running
- `date` — display the current date and time
- `df` — show disk space usage
- `free` — display memory usage
- `mem [pid]` / `memory` — show memory statistics and per-process memory usage
- `sleep <seconds>` — pause for a specified duration
- `info` — show system and kernel information (includes memory stats)
- `driver [list|load|unload]` — manage system drivers

### File system

- `pwd` — show current working directory
- `cd <path>` — change directory
- `find [path]` — recursively list files and directories under a path
- `ls [-l] [prefix]` — list directory contents or a file
- `cat <path>` — display file contents
- `edit <path>` — interactive line-based text editor
- `write <path> <content>` — overwrite or create a file
- `append <path> <content>` — append text to a file
- `echo [-n] [-e] <text> [> path]` — write text to stdout or a file; `-e` expands escapes
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
- `ln [-s] <target> <link>` — create a hard link or symbolic link (`-s`)
- `readlink <path>` — print the target of a symbolic link
- `du [-h] [path]` — show disk usage for a file or directory tree

### User Management

- `whoami` — print effective user name
- `login` — begin a new session as a different user
- `su [user]` — switch to another user (defaults to root)
- `sudo <command>` — execute a command with root privileges
- `passwd [-l|-u] [user]` — change password, or lock (`-l`) / unlock (`-u`) account
- `useradd <name>` — create a new user account
- `userdel <name>` — delete a user account
- `groups [user]` — show group memberships
- `chown <user> <path>` — change file owner
- `chgrp <group> <path>` — change group ownership
- `last` — show a list of last logged in users (simulated)

### Text Pipeline Tools

All commands below are pipeline-aware: they read from a file argument **or** from stdin (a prior pipe stage).

- `wc [-l] [-w] [-c] [file]` — count lines, words, and bytes
- `grep [-i] [-v] [-n] [-c] [-E] <pattern> [file]` — filter lines by pattern; `-i` case-insensitive, `-v` invert, `-n` number, `-c` count, `-E` extended regex
- `sort [-r] [-n] [-u] [file]` — sort lines; `-r` reverse, `-n` numeric, `-u` deduplicate
- `uniq [-c] [-d] [-u] [file]` — deduplicate adjacent lines; `-c` prefix count, `-d` dup-only, `-u` unique-only
- `cut -f <fields> [-d <delim>] [file]` — extract delimited fields (e.g. `-f 1,3 -d :`)
- `cut -c <range> [file]` — extract character positions (e.g. `-c 1-5`)
- `tr [-d] [-s] <set1> [set2]` — translate or delete characters; supports `a-z` ranges
- `base64 [-d|-D] [-w cols] [file]` — encode or decode text using Base64
- `xargs [-n <max>] <command> [args...]` — build commands from stdin words

### Processes & Services

- `ps` — list active processes (PID, NAME, STATUS, START, TIME, NI, VSZ, RSS)
- `spawn <name> [runtime]` — create a new background process with a name and optional runtime duration in seconds (default: 5.0)
- `kill [-<signal>] <pid>` — terminate a process (default SIGTERM; `-9` for SIGKILL)
- `wait [pid]...` — wait for specific background processes (or all active background processes if none specified) to complete
- `top` — one-shot snapshot of processes ranked by elapsed time, including RSS
- `renice <priority> <pid>` — change the nice value (priority) of a process
- `jobs` — list background processes with status
- `fg <pid>` — bring a background process to the foreground
- `bg <pid>` — resume a suspended background process
- `time <command>` — measure wall-clock execution time of a command
- `set [-e] [-x] [+e] [+x]` — enable/disable shell options (exit-on-error, trace)
- `services` — list registered services
- `service start <name>` — start a service
- `pkg [install <url> <name> | list | remove <name>]` — manage dynamic commands downloaded from the web
- `service stop <name>` — stop a service
- `service status <name>` — show service state
- `service restart <name>` — restart a service
- `crontab [-l|-r|<file>]` — list, remove, or install a crontab schedule file

### Networking

- `ifconfig` — display network interface configuration
- `ping <host> [port]` — check host or port reachability
- `nc` / `netcat <host> <port> [message]` — connect to a TCP port, send data, and print response
- `curl [options] <url>` — transfer data from or to a server using HTTP/HTTPS
- `wget [options] <url>` — retrieve files over HTTP/HTTPS
- `host <domain>` — DNS lookup for a domain name
- `nslookup <domain>` — query DNS (shows nameserver details)
- `ip <addr|link|route>` — show interface addresses, link info, or routing table
- `ss` — show mock socket statistics
- `traceroute <host>` — simulate hop-by-hop route tracing
- `iptables [-L|-A|-D|-F] [chain] [rule]` — manage simulated firewall rules

### Example session

```text
v2-pureos> mkdir /tmp
v2-pureos> write /tmp/hello "hello world"
v2-pureos> cat /tmp/hello
v2-pureos> chmod 600 /tmp/hello
v2-pureos> service status noop
v2-pureos> spawn worker
v2-pureos> mem
v2-pureos> ps
v2-pureos> exit
```

---

## Testing

Run the test suite from the repository root:

```bash
python3 -m pip install -q pytest pytest-cov pytest-xdist
pytest
```

## Project structure

- `main.py` — executable launcher script
- `src/pureos` — main Python package
  - `kernel.py` — kernel orchestrator
  - `memory.py` — memory management subsystem
  - `processes.py` — process scheduler
  - `pkg.py` — package manager subsystem
  - `drivers.py` — system driver manager and base class
  - `syslog.py` — system logging driver
  - `users.py` — POSIX-like user and group database
  - `services.py` — service manager subsystem
  - `network.py` — simulated networking
  - `fs/` — virtual filesystem
  - `commands/` — interactive shell commands
- `tests` — unit and integration tests
- `docs/` — comprehensive documentation
  - `index.md` — landing page and command reference
  - `architecture.md` — system architecture overview
  - `filesystem.md` — virtual filesystem internals
  - `shell_and_commands.md` — shell parsing and command plugins

## Design notes

This project is not a production operating system. It is intended as a demonstration of Python-based OS-like subsystems and shell interaction.
