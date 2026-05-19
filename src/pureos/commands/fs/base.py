from pureos.commands.base import Command


class FileCommand(Command):
    def _resolve_path(
        self,
        path: str,
        is_dir: bool = False,
        allow_dir: bool = False,
    ) -> str:
        return self.kernel.shell.resolve_path(path, is_dir=is_dir, allow_dir=allow_dir)
