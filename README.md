# v2-PureOS

v2-PureOS is a minimal, OS-like project implemented entirely using Python's standard library. No third-party
packages are required — there is no `pip install` step.

**Key points**
- Implemented with native Python modules such as `os`, `sys`, `math`, `pathlib`, `json`, `socket`, and
	`threading`.
- No external dependencies or packages from PyPI.
- Runs on any system with Python 3.8 or newer.

**Getting started**
- Clone the repository.
- Run the project's entrypoint (example): `python3 main.py`
	Replace `main.py` with the actual entrypoint if different.

**Shell commands**
After initializing the kernel you can start the interactive shell (`--shell`) and run simple commands:

- `help`: show available commands
- `info`: show kernel, filesystem, process and service counts
- `ls [prefix]`: list files in the virtual filesystem (default `/`)
- `ps`: list spawned processes
- `services`: list registered services
- `cat <path>`: print the contents of a file in the virtual filesystem
- `write <path> <content>`: write `content` to `path` in the virtual filesystem
- `exit` / `quit`: leave the shell

Example:

`python3 main.py --shell`

Then at the prompt:

`v2-pureos> write /var/data hello world`

`v2-pureos> cat /var/data`


**Contributing**
- Contributions are welcome. Please open issues or pull requests and keep changes compatible with the
	standard library.

**License**
- See the `LICENSE` file if present.
