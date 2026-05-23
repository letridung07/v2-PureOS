from typing import List, Optional, Tuple


def split_command_sequence(line: str) -> List[Tuple[str, Optional[str]]]:
    commands: List[Tuple[str, Optional[str]]] = []
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
        if line.startswith("&&", index):
            command = "".join(current).strip()
            if command:
                commands.append((command, "&&"))
            current = []
            index += 2
            continue
        if line.startswith("||", index):
            command = "".join(current).strip()
            if command:
                commands.append((command, "||"))
            current = []
            index += 2
            continue
        if char == ";":
            command = "".join(current).strip()
            if command:
                commands.append((command, ";"))
            current = []
            index += 1
            continue
        if char == "&":
            command = "".join(current).strip()
            if command:
                commands.append((command, "&"))
            current = []
            index += 1
            continue
        current.append(char)
        index += 1
    if escaped:
        current.append("\\")
    command = "".join(current).strip()
    if command:
        commands.append((command, None))
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


def _parse_target_word(line: str, start_index: int) -> Tuple[Optional[str], int]:
    """Helper to parse the next token (target file) starting at start_index.
    Returns (target_word, consumed_chars).
    """
    index = start_index
    # Skip leading whitespace
    while index < len(line) and line[index].isspace():
        index += 1

    if index >= len(line):
        return None, index - start_index

    target_parts = []
    quote = None
    escaped = False

    while index < len(line):
        char = line[index]
        if escaped:
            target_parts.append(char)
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
                target_parts.append(char)
            index += 1
            continue
        if char in ('"', "'"):
            quote = char
            index += 1
            continue
        if char.isspace() or char in (">", "<", "|", ";", "&"):
            # Stop parsing on unquoted space or other operator
            break
        target_parts.append(char)
        index += 1

    if escaped:
        target_parts.append("\\")

    return "".join(target_parts) if target_parts else None, index - start_index


def split_redirection(
    line: str,
) -> Tuple[str, Optional[str], Optional[str], Optional[str], Optional[str]]:
    """Scan the command line to split at unquoted/unescaped redirection operators.
    Supports output redirection (> or >>) and input redirection (<).

    Returns (command_part, output_operator, output_target,
    input_operator, input_target).
    """
    quote = None
    escaped = False
    index = 0
    cmd_parts = []

    output_op = None
    output_target = None
    input_op = None
    input_target = None

    while index < len(line):
        char = line[index]
        if escaped:
            cmd_parts.append("\\" + char)
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
            cmd_parts.append(char)
            index += 1
            continue
        if char in ('"', "'"):
            quote = char
            cmd_parts.append(char)
            index += 1
            continue

        # Check for output redirection operators >> and >
        if line.startswith(">>", index):
            output_op = ">>"
            index += 2
            target, consumed = _parse_target_word(line, index)
            output_target = target
            index += consumed
            continue
        elif char == ">":
            output_op = ">"
            index += 1
            target, consumed = _parse_target_word(line, index)
            output_target = target
            index += consumed
            continue

        # Check for input redirection operator <
        elif char == "<":
            input_op = "<"
            index += 1
            target, consumed = _parse_target_word(line, index)
            input_target = target
            index += consumed
            continue

        cmd_parts.append(char)
        index += 1

    if escaped:
        cmd_parts.append("\\")

    return (
        "".join(cmd_parts).strip(),
        output_op,
        output_target,
        input_op,
        input_target,
    )
