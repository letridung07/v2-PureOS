from __future__ import annotations

import argparse
from abc import ABC, abstractmethod
from typing import List, Optional, Union

CommandResult = Optional[Union[str, bool]]


class PureOSArgumentParser(argparse.ArgumentParser):
    """ArgumentParser that raises ValueError on error/exit instead of sys.exit."""

    def error(self, message):
        raise ValueError(message)

    def exit(self, status=0, message=None):
        if message:
            raise ValueError(message)


class Command(ABC):
    name: str
    description: str = ""
    usage: str = ""
    aliases: List[str] = []

    def __init__(self, kernel):
        self.kernel = kernel

    @abstractmethod
    def execute(
        self,
        parts: List[str],
        input_data: Optional[str] = None,
        capture_output: bool = False,
        raw_line: Optional[str] = None,
    ) -> CommandResult: ...

    def resolve_path(
        self,
        path: str,
        is_dir: bool = False,
        allow_dir: bool = False,
    ) -> str:
        return self.kernel.shell.resolve_path(path, is_dir=is_dir, allow_dir=allow_dir)

    def read_input(
        self,
        parts: List[str],
        input_data: Optional[str],
        file_arg_index: int = 1,
    ) -> Optional[str]:
        """Return text to process.

        Priority:
        1. File path at *file_arg_index* in *parts* (if present and not a flag).
           Treats '-' as a request for *input_data*.
        2. *input_data* from a pipeline.
        Returns None and prints an error when neither is available.
        """
        if len(parts) > file_arg_index:
            path_arg = parts[file_arg_index]
            # Skip if it's a flag (starts with - and length > 1)
            # But allow '-' specifically as standard input
            if path_arg.startswith("-") and len(path_arg) > 1:
                pass
            else:
                if path_arg == "-":
                    if input_data is not None:
                        return input_data
                    print(f"{parts[0]}: -: Standard input not available")
                    return None

                path = self.resolve_path(path_arg)
                if not self.kernel.fs.exists(path):
                    print(f"{parts[0]}: {path_arg}: No such file or directory")
                    return None
                if self.kernel.fs.is_dir(path):
                    print(f"{parts[0]}: {path_arg}: Is a directory")
                    return None
                try:
                    content = self.kernel.fs.read(path)
                except PermissionError as exc:
                    print(str(exc))
                    return None
                return content or ""

        if input_data is not None:
            return input_data

        print(f"Usage: {parts[0]} [file]")
        return None

    def emit(self, text: str, capture_output: bool) -> CommandResult:
        """Print or return *text* depending on pipeline context."""
        if capture_output:
            return text
        if text:
            print(text)
        return True
