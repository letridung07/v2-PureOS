from __future__ import annotations

from abc import ABC, abstractmethod
from typing import List, Optional, Union

CommandResult = Optional[Union[str, bool]]


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
    ) -> CommandResult:
        ...

    def resolve_path(
        self,
        path: str,
        is_dir: bool = False,
        allow_dir: bool = False,
    ) -> str:
        return self.kernel.shell.resolve_path(
            path, is_dir=is_dir, allow_dir=allow_dir
        )
