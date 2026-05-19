from .state import FSState


class PathResolver:
    @staticmethod
    def normalize_path(path: str, is_dir: bool = False, allow_dir: bool = False) -> str:
        if path is None:
            path = ""
        path = path.replace("\\", "/")
        if path != "/" and path.endswith("/"):
            is_dir = True
        if not path.startswith("/"):
            path = "/" + path
        parts = []
        for segment in path.split("/"):
            if segment in ("", "."):
                continue
            if segment == "..":
                if parts:
                    parts.pop()
                continue
            parts.append(segment)
        normalized = "/" + "/".join(parts)
        if normalized != "/" and (is_dir or allow_dir and path.endswith("/")):
            normalized += "/"
        return normalized

    @staticmethod
    def parent_dir(path: str) -> str:
        normalized = PathResolver.normalize_path(path, allow_dir=True)
        if normalized == "/":
            return "/"
        stripped = normalized.rstrip("/")
        parent = stripped.rsplit("/", 1)[0]
        if not parent:
            return "/"
        return parent + "/"

    @staticmethod
    def ensure_dir_parents(state: FSState, path: str):
        normalized = PathResolver.normalize_path(path, allow_dir=True)
        if not normalized.endswith("/"):
            normalized = PathResolver.parent_dir(normalized)
        if normalized.rstrip("/") in state.files:
            raise ValueError(
                f"Cannot create directory under file path {normalized.rstrip('/')}"
            )
        while normalized not in state.dirs:
            if normalized.rstrip("/") in state.files:
                raise ValueError(
                    f"Cannot create directory under file path {normalized.rstrip('/')}"
                )
            state.dirs.add(normalized)
            state.modes.setdefault(normalized, 0o755)
            if normalized == "/":
                break
            normalized = PathResolver.parent_dir(normalized)
