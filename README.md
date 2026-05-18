# v2-PureOS

![CI](https://github.com/letridung07/v2-PureOS/actions/workflows/ci.yml/badge.svg)

v2-PureOS is a minimal, OS-like project implemented entirely using Python's standard library. No third-party packages are required — there is no `pip install` step.

**Key points**
- Implemented with native Python modules such as `os`, `sys`, `math`, `pathlib`, `json`, `socket`, and `threading`.
- No external dependencies or packages from PyPI.
- Runs on any system with Python 3.8 or newer.

Running tests

- Locally: python -m pip install -U pip && python -m pip install -q pytest pytest-cov && pytest
- CI: GitHub Actions workflow located at `.github/workflows/ci.yml` runs pytest, coverage, ruff and black.

**Getting started**
- Clone the repository.
- Run the project's entrypoint (example): `python3 main.py`
- Or run the package directly: `python3 -m pureos`

**Shell commands**
After initializing the kernel you can start the interactive shell (`--shell`) and run simple commands:

- `help`: show available commands
- `info`: show kernel, filesystem, process and service counts
- `ls [prefix]`: list files in the virtual filesystem (default `/`)
- `cat <path>`: print the contents of a file in the virtual filesystem
- `write <path> <content>`: write `content` to `path` in the virtual filesystem
- `mkdir <path>`, `rm <path>`, `mv <src> <dst>`, `cp <src> <dst>`, `touch <path>`
- `echo <text> > <path>` (or print to stdout)
- `head <path> [n]`, `tail <path> [n]`
- `ps`, `spawn <name>`, `kill <pid>`
- `services` and `service start|stop|status|restart <name>`
- `exit` / `quit`: leave the shell

Example:

`python3 -m pureos --shell`

Then at the prompt:

`v2-pureos> write /var/data hello world`

`v2-pureos> cat /var/data`


**Contributing**
- Contributions are welcome. Please open issues or pull requests and keep changes compatible with the
	standard library.

**License**
- See the `LICENSE` file if present.
