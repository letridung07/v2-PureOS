from typing import List, Optional, Tuple


def split_command_sequence(line: str) -> List[Tuple[str, Optional[str]]]:
    commands: List[Tuple[str, Optional[str]]] = []
    current: List[str] = []
    quote: Optional[str] = None
    escaped = False
    separator: Optional[str] = None
    index = 0
    while index < len(line):
        char = line[index]
        if escaped:
            current.append("\\" + char)
            escaped = False
            index += 1
            continue
        if char == "\\":
            escaped = True
            index += 1
            continue
        if quote:
            if char == quote:
                quote = None
            current.append(char)
            index += 1
            continue
        if char in ('"', "'"):
            quote = char
            current.append(char)
            index += 1
            continue
        if line.startswith("&&", index):
            command = "".join(current).strip()
            if command:
                commands.append((command, separator))
            separator = "&&"
            current = []
            index += 2
            continue
        if line.startswith("||", index):
            command = "".join(current).strip()
            if command:
                commands.append((command, separator))
            separator = "||"
            current = []
            index += 2
            continue
        if char == ";":
            command = "".join(current).strip()
            if command:
                commands.append((command, separator))
            separator = ";"
            current = []
            index += 1
            continue
        current.append(char)
        index += 1
    if escaped:
        current.append("\\")
    command = "".join(current).strip()
    if command:
        commands.append((command, separator))
    return commands


def split_pipeline(line: str) -> List[str]:
    stages: List[str] = []
    current: List[str] = []
    quote: Optional[str] = None
    escaped = False
    index = 0
    while index < len(line):
        char = line[index]
        if escaped:
            current.append("\\" + char)
            escaped = False
            index += 1
            continue
        if char == "\\":
            escaped = True
            index += 1
            continue
        if quote:
            if char == quote:
                quote = None
            current.append(char)
            index += 1
            continue
        if char in ('"', "'"):
            quote = char
            current.append(char)
            index += 1
            continue
        if char == "|":
            stages.append("".join(current).strip())
            current = []
            index += 1
            continue
        current.append(char)
        index += 1
    if escaped:
        current.append("\\")
    stage = "".join(current).strip()
    if stage:
        stages.append(stage)
    return stages


def tokenize(line: str) -> List[str]:
    parts: List[str] = []
    current: List[str] = []
    quote: Optional[str] = None
    escaped = False
    index = 0
    while index < len(line):
        char = line[index]
        if escaped:
            current.append(char)
            escaped = False
            index += 1
            continue
        if char == "\\":
            escaped = True
            index += 1
            continue
        if quote:
            if char == quote:
                quote = None
            else:
                current.append(char)
            index += 1
            continue
        if char in ('"', "'"):
            quote = char
            index += 1
            continue
        if char.isspace():
            if current:
                parts.append("".join(current))
                current = []
            index += 1
            continue
        current.append(char)
        index += 1
    if escaped:
        current.append("\\")
    if current:
        parts.append("".join(current))
    return parts
