"""Utility helpers."""


def human_list(seq):
    return ", ".join(str(x) for x in seq)


def format_size(size: int, human: bool = True) -> str:
    """Format a byte size into a human-readable string."""
    if not human:
        return str(size)
    fsize = float(size)
    for unit in ["B", "K", "M", "G", "T"]:
        if fsize < 1024:
            return f"{fsize:.0f}{unit}"
        fsize /= 1024
    return f"{fsize:.0f}P"
