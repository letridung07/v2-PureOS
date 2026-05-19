"""Text-processing pipeline commands for v2-PureOS.

All commands are pipeline-aware:
- They read from *input_data* when no file argument is given.
- They return a string when *capture_output* is True.
"""

from __future__ import annotations

import re
import shlex
from typing import List, Optional

from .base import Command

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _read_input(
    cmd: Command,
    parts: List[str],
    input_data: Optional[str],
    file_arg_index: int = 1,
) -> Optional[str]:
    """Return text to process.

    Priority:
    1. File path at *file_arg_index* in *parts* (if present and not a flag).
    2. *input_data* from a pipeline.
    Returns None and prints an error when neither is available.
    """
    if len(parts) > file_arg_index and not parts[file_arg_index].startswith("-"):
        path = cmd.resolve_path(parts[file_arg_index])
        if not cmd.kernel.fs.exists(path):
            print(f"{parts[0]}: {parts[file_arg_index]}: No such file or directory")
            return None
        if cmd.kernel.fs.is_dir(path):
            print(f"{parts[0]}: {parts[file_arg_index]}: Is a directory")
            return None
        try:
            content = cmd.kernel.fs.read(path)
        except PermissionError as exc:
            print(str(exc))
            return None
        return content or ""
    if input_data is not None:
        return input_data
    print(f"Usage: {parts[0]} [file]")
    return None


def _emit(text: str, capture_output: bool):
    """Print or return *text* depending on pipeline context."""
    if capture_output:
        return text
    print(text)
    return True


# ---------------------------------------------------------------------------
# wc
# ---------------------------------------------------------------------------


class WcCommand(Command):
    name = "wc"
    usage = "wc [-l] [-w] [-c] [file]"
    description = "Count lines, words, and bytes in text input."

    def execute(
        self,
        parts: List[str],
        input_data=None,
        capture_output=False,
        raw_line=None,
    ):
        # Parse flags; consume them so file arg detection works
        flags = set()
        remaining = [parts[0]]
        for tok in parts[1:]:
            if tok.startswith("-") and len(tok) > 1 and not tok.startswith("--"):
                for ch in tok[1:]:
                    flags.add(ch)
            else:
                remaining.append(tok)

        text = _read_input(self, remaining, input_data, file_arg_index=1)
        if text is None:
            return False

        lines = text.splitlines()
        words = text.split()
        chars = len(text.encode("utf-8"))

        show_all = not flags or not (flags & {"l", "w", "c"})

        parts_out = []
        if show_all or "l" in flags:
            parts_out.append(str(len(lines)))
        if show_all or "w" in flags:
            parts_out.append(str(len(words)))
        if show_all or "c" in flags:
            parts_out.append(str(chars))

        out = "  ".join(parts_out)
        return _emit(out, capture_output)


# ---------------------------------------------------------------------------
# grep
# ---------------------------------------------------------------------------


class GrepCommand(Command):
    name = "grep"
    usage = "grep [-i] [-v] [-n] [-c] [-E] <pattern> [file]"
    description = "Filter lines matching a pattern."

    def execute(
        self,
        parts: List[str],
        input_data=None,
        capture_output=False,
        raw_line=None,
    ):
        flags: set = set()
        positional: List[str] = [parts[0]]

        i = 1
        while i < len(parts):
            tok = parts[i]
            if tok.startswith("-") and len(tok) > 1 and not tok.startswith("--"):
                for ch in tok[1:]:
                    flags.add(ch)
            elif tok == "--":
                positional.extend(parts[i + 1 :])
                break
            else:
                positional.append(tok)
            i += 1

        if len(positional) < 2:
            print("Usage: grep [-i] [-v] [-n] [-c] [-E] <pattern> [file]")
            return False

        pattern_str = positional[1]
        file_positional = [positional[0]] + positional[2:]

        re_flags = re.IGNORECASE if "i" in flags else 0
        try:
            if "E" in flags:
                # -E: extended regex — compile as-is
                compiled = re.compile(pattern_str, re_flags)
            else:
                # No -E: always treat the pattern as a literal string
                compiled = re.compile(re.escape(pattern_str), re_flags)
        except re.error as exc:
            print(f"grep: invalid pattern: {exc}")
            return False

        text = _read_input(self, file_positional, input_data, file_arg_index=1)
        if text is None:
            return False

        invert = "v" in flags
        number = "n" in flags
        count_only = "c" in flags

        matched_lines = []
        for idx, line in enumerate(text.splitlines(), 1):
            match = bool(compiled.search(line))
            if match != invert:
                if number:
                    matched_lines.append(f"{idx}:{line}")
                else:
                    matched_lines.append(line)

        if count_only:
            return _emit(str(len(matched_lines)), capture_output)

        if not matched_lines:
            if capture_output:
                return ""
            return False

        out = "\n".join(matched_lines)
        return _emit(out, capture_output)


# ---------------------------------------------------------------------------
# sort
# ---------------------------------------------------------------------------


class SortCommand(Command):
    name = "sort"
    usage = "sort [-r] [-n] [-u] [file]"
    description = "Sort lines of text input."

    def execute(
        self,
        parts: List[str],
        input_data=None,
        capture_output=False,
        raw_line=None,
    ):
        flags: set = set()
        remaining = [parts[0]]
        for tok in parts[1:]:
            if tok.startswith("-") and len(tok) > 1:
                for ch in tok[1:]:
                    flags.add(ch)
            else:
                remaining.append(tok)

        text = _read_input(self, remaining, input_data, file_arg_index=1)
        if text is None:
            return False

        lines = text.splitlines()

        reverse = "r" in flags
        numeric = "n" in flags
        unique = "u" in flags

        if numeric:

            def key_fn(line: str):
                stripped = line.strip()
                # extract leading number
                m = re.match(r"^-?\d+(\.\d+)?", stripped)
                return float(m.group()) if m else 0.0

        else:
            key_fn = None  # type: ignore[assignment]

        lines.sort(key=key_fn, reverse=reverse)

        if unique:
            seen = []
            deduped = []
            for ln in lines:
                if ln not in seen:
                    seen.append(ln)
                    deduped.append(ln)
            lines = deduped

        out = "\n".join(lines)
        return _emit(out, capture_output)


# ---------------------------------------------------------------------------
# uniq
# ---------------------------------------------------------------------------


class UniqCommand(Command):
    name = "uniq"
    usage = "uniq [-c] [-d] [-u] [file]"
    description = "Report or filter adjacent duplicate lines."

    def execute(
        self,
        parts: List[str],
        input_data=None,
        capture_output=False,
        raw_line=None,
    ):
        flags: set = set()
        remaining = [parts[0]]
        for tok in parts[1:]:
            if tok.startswith("-") and len(tok) > 1:
                for ch in tok[1:]:
                    flags.add(ch)
            else:
                remaining.append(tok)

        text = _read_input(self, remaining, input_data, file_arg_index=1)
        if text is None:
            return False

        lines = text.splitlines()
        count = "c" in flags
        dups_only = "d" in flags
        unique_only = "u" in flags

        # Group adjacent identical lines
        groups: List[tuple] = []  # (line, count)
        for line in lines:
            if groups and groups[-1][0] == line:
                groups[-1] = (line, groups[-1][1] + 1)
            else:
                groups.append((line, 1))

        result = []
        for line, cnt in groups:
            if dups_only and cnt == 1:
                continue
            if unique_only and cnt > 1:
                continue
            if count:
                result.append(f"{cnt:>7} {line}")
            else:
                result.append(line)

        out = "\n".join(result)
        return _emit(out, capture_output)


# ---------------------------------------------------------------------------
# cut
# ---------------------------------------------------------------------------


class CutCommand(Command):
    name = "cut"
    usage = "cut -f <fields> [-d <delim>] [file]  |  cut -c <range> [file]"
    description = "Extract fields or characters from lines."

    def execute(
        self,
        parts: List[str],
        input_data=None,
        capture_output=False,
        raw_line=None,
    ):
        delim = "\t"
        fields: Optional[List[int]] = None
        chars: Optional[List[int]] = None
        file_args = [parts[0]]

        i = 1
        while i < len(parts):
            tok = parts[i]
            if tok in ("-d",) and i + 1 < len(parts):
                delim = parts[i + 1]
                i += 2
            elif tok.startswith("-d") and len(tok) > 2:
                delim = tok[2:]
                i += 1
            elif tok in ("-f",) and i + 1 < len(parts):
                try:
                    fields = self._parse_range(parts[i + 1])
                except ValueError as exc:
                    print(str(exc))
                    return False
                i += 2
            elif tok.startswith("-f") and len(tok) > 2:
                try:
                    fields = self._parse_range(tok[2:])
                except ValueError as exc:
                    print(str(exc))
                    return False
                i += 1
            elif tok in ("-c",) and i + 1 < len(parts):
                try:
                    chars = self._parse_range(parts[i + 1])
                except ValueError as exc:
                    print(str(exc))
                    return False
                i += 2
            elif tok.startswith("-c") and len(tok) > 2:
                try:
                    chars = self._parse_range(tok[2:])
                except ValueError as exc:
                    print(str(exc))
                    return False
                i += 1
            else:
                file_args.append(tok)
                i += 1

        if fields is None and chars is None:
            print("cut: you must specify either -f or -c")
            return False
        if fields is not None and chars is not None:
            print("cut: options -f and -c are mutually exclusive")
            return False

        text = _read_input(self, file_args, input_data, file_arg_index=1)
        if text is None:
            return False

        result = []
        for line in text.splitlines():
            if chars is not None:
                extracted = "".join(line[c - 1] for c in chars if 0 < c <= len(line))
            else:
                col_parts = line.split(delim)
                extracted = delim.join(
                    col_parts[f - 1]
                    for f in fields  # type: ignore[index]
                    if 0 < f <= len(col_parts)
                )
            result.append(extracted)

        out = "\n".join(result)
        return _emit(out, capture_output)

    @staticmethod
    def _parse_range(spec: str) -> List[int]:
        """Parse a cut field/char specification like '1,3-5,7'.

        Raises ValueError on malformed specs so callers can report an error.
        """
        indices = []
        for part in spec.split(","):
            part = part.strip()
            if not part:
                continue
            if "-" in part:
                lo_s, hi_s = part.split("-", 1)
                try:
                    lo = int(lo_s) if lo_s else 1
                    hi = int(hi_s) if hi_s else 9999
                except ValueError:
                    raise ValueError(f"cut: invalid field/char spec: {spec!r}")
                if lo < 1 or hi < lo:
                    raise ValueError(f"cut: invalid range {part!r} in spec {spec!r}")
                indices.extend(range(lo, hi + 1))
            else:
                try:
                    n = int(part)
                except ValueError:
                    raise ValueError(f"cut: invalid field/char spec: {spec!r}")
                if n < 1:
                    raise ValueError("cut: fields/chars are numbered from 1")
                indices.append(n)
        if not indices:
            raise ValueError(f"cut: empty field/char spec: {spec!r}")
        return sorted(set(indices))


# ---------------------------------------------------------------------------
# tr
# ---------------------------------------------------------------------------


class TrCommand(Command):
    name = "tr"
    usage = "tr [-d] [-s] <set1> [set2]"
    description = "Translate or delete characters in input."

    def execute(
        self,
        parts: List[str],
        input_data=None,
        capture_output=False,
        raw_line=None,
    ):
        delete = False
        squeeze = False
        positional = [parts[0]]

        i = 1
        while i < len(parts):
            tok = parts[i]
            if tok.startswith("-") and len(tok) > 1:
                for ch in tok[1:]:
                    if ch == "d":
                        delete = True
                    elif ch == "s":
                        squeeze = True
            else:
                positional.append(tok)
            i += 1

        if len(positional) < 2:
            print("Usage: tr [-d] [-s] <set1> [set2]")
            return False

        if input_data is None:
            print("tr: no input (use in a pipeline or redirect)")
            return False

        set1 = self._expand_set(positional[1])
        set2 = self._expand_set(positional[2]) if len(positional) > 2 else ""

        if not set1:
            print("tr: set1 must not be empty")
            return False
        if set2 and not delete and len(set2) == 0:
            # guard: set2 is referenced via [-1] below; already empty-checked above
            print("tr: set2 must not be empty when translating")
            return False

        text = input_data

        if delete:
            # -d: delete chars in set1; set2 is ignored per POSIX
            text = "".join(c for c in text if c not in set1)
        elif set2:
            # Build a translation table; if set2 is shorter, last char repeats
            table = {}
            for idx, ch in enumerate(set1):
                dest = set2[idx] if idx < len(set2) else set2[-1]
                table[ch] = dest
            text = "".join(table.get(c, c) for c in text)

        if squeeze and set2:
            # Squeeze repeated chars in set2
            result = []
            prev = None
            for c in text:
                if c in set2 and c == prev:
                    continue
                result.append(c)
                prev = c
            text = "".join(result)
        elif squeeze and not set2:
            # Squeeze repeated chars in set1
            result = []
            prev = None
            for c in text:
                if c in set1 and c == prev:
                    continue
                result.append(c)
                prev = c
            text = "".join(result)

        return _emit(text, capture_output)

    @staticmethod
    def _expand_set(spec: str) -> str:
        """Expand a tr set specification, handling a-z ranges."""
        result = []
        i = 0
        while i < len(spec):
            if i + 2 < len(spec) and spec[i + 1] == "-":
                start, end = ord(spec[i]), ord(spec[i + 2])
                result.extend(chr(c) for c in range(start, end + 1))
                i += 3
            else:
                result.append(spec[i])
                i += 1
        return "".join(result)


# ---------------------------------------------------------------------------
# xargs
# ---------------------------------------------------------------------------


class XargsCommand(Command):
    name = "xargs"
    usage = "xargs [-n <max_args>] <command> [initial_args...]"
    description = "Build and execute a command from stdin arguments."

    def execute(
        self,
        parts: List[str],
        input_data=None,
        capture_output=False,
        raw_line=None,
    ):
        if input_data is None:
            print("xargs: no input (use in a pipeline)")
            return False

        # Parse -n flag
        max_args: Optional[int] = None
        positional = [parts[0]]
        i = 1
        while i < len(parts):
            tok = parts[i]
            if tok == "-n" and i + 1 < len(parts):
                try:
                    max_args = int(parts[i + 1])
                except ValueError:
                    print("xargs: -n requires an integer")
                    return False
                i += 2
            elif tok.startswith("-n") and len(tok) > 2:
                try:
                    max_args = int(tok[2:])
                except ValueError:
                    print("xargs: -n requires an integer")
                    return False
                i += 1
            else:
                positional.append(tok)
                i += 1

        if len(positional) < 2:
            print("Usage: xargs [-n <max>] <command> [initial_args...]")
            return False

        base_cmd = positional[1]
        initial_args = positional[2:]

        # Tokenize stdin into words (honours simple quoting)
        try:
            stdin_words = shlex.split(input_data)
        except ValueError:
            stdin_words = input_data.split()

        if not stdin_words:
            # Nothing to do — success like POSIX xargs
            return True

        chunk_size = max_args if max_args and max_args > 0 else len(stdin_words)
        outputs = []
        success = True

        for start in range(0, len(stdin_words), chunk_size):
            chunk = stdin_words[start : start + chunk_size]
            cmd_parts = [base_cmd] + initial_args + chunk
            result = self.kernel.shell.registry.execute(
                cmd_parts,
                capture_output=capture_output,
            )
            if result is False:
                success = False
            elif isinstance(result, str):
                outputs.append(result)

        if capture_output:
            return "\n".join(outputs)
        return success


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------


def register_text_commands(registry):
    registry.register(WcCommand(registry.kernel))
    registry.register(GrepCommand(registry.kernel))
    registry.register(SortCommand(registry.kernel))
    registry.register(UniqCommand(registry.kernel))
    registry.register(CutCommand(registry.kernel))
    registry.register(TrCommand(registry.kernel))
    registry.register(XargsCommand(registry.kernel))
