"""Default configuration for v2-PureOS."""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class Config:
    shell_prompt: str = "v2-pureos> "
    format_on_boot: bool = False
    auto_start_services: Optional[List[str]] = field(default_factory=lambda: ["noop"])
    fs_backing: Optional[str] = None

    @classmethod
    def from_dict(cls, config: Optional[Dict[str, Any]] = None):
        if config is None:
            return cls()
        kwargs = {}
        for field_name in (
            "shell_prompt",
            "format_on_boot",
            "auto_start_services",
            "fs_backing",
        ):
            if field_name in config:
                kwargs[field_name] = config[field_name]
        return cls(**kwargs)


DEFAULT_CONFIG = Config()
