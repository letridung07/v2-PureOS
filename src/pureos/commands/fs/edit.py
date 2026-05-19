from typing import List
from .base import FileCommand


class EditCommand(FileCommand):
    name = "edit"
    usage = "edit <path>"
    description = "Interactive line-based text editor."

    def execute(
        self, parts: List[str], input_data=None, capture_output=False, raw_line=None
    ):
        if len(parts) < 2:
            print("Usage: edit <path>")
            return False
        path = self._resolve_path(parts[1])

        # Load file content if it exists
        buffer = []
        if self.kernel.fs.exists(path):
            if self.kernel.fs.is_dir(path):
                print(f"Error: {parts[1]} is a directory")
                return False
            try:
                content = self.kernel.fs.read(path)
                if content is not None:
                    buffer = content.splitlines()
            except PermissionError as exc:
                print(str(exc))
                return False

        print(f"Entering edit mode for {parts[1]}")
        print("Commands:")
        print("  :wq  - save and quit")
        print("  :q   - quit without saving")
        print("  :w   - save current buffer")
        print("  :l   - list lines with line numbers")
        print("  :d <line_number> - delete line at 1-indexed number")
        print("  :a <line_number> <content> - insert after line (0 for top)")
        print("Type any text to append to the end of the file.")
        print("-" * 48)

        # Show current content
        for idx, line in enumerate(buffer, 1):
            print(f"{idx}: {line}")

        while True:
            try:
                line = input("edit> ")
            except (EOFError, KeyboardInterrupt):
                print("\nQuit editor without saving.")
                break

            if line.startswith(":"):
                sub_parts = line.split(maxsplit=2)
                cmd = sub_parts[0]
                if cmd == ":q":
                    break
                elif cmd == ":w":
                    content = "\n".join(buffer)
                    try:
                        self.kernel.fs.write(path, content)
                        print(f"Saved {len(content)} bytes to {parts[1]}")
                    except (ValueError, PermissionError) as exc:
                        print(f"Error saving: {exc}")
                elif cmd == ":wq":
                    content = "\n".join(buffer)
                    try:
                        self.kernel.fs.write(path, content)
                        print(f"Saved {len(content)} bytes to {parts[1]}")
                    except (ValueError, PermissionError) as exc:
                        print(f"Error saving: {exc}")
                        continue
                    break
                elif cmd in (":l", ":list"):
                    for idx, buf_line in enumerate(buffer, 1):
                        print(f"{idx}: {buf_line}")
                elif cmd in (":d", ":delete"):
                    if len(sub_parts) < 2:
                        print("Usage: :d <line_number>")
                        continue
                    try:
                        line_num = int(sub_parts[1])
                        if 1 <= line_num <= len(buffer):
                            removed = buffer.pop(line_num - 1)
                            print(f"Deleted line {line_num}: {removed}")
                        else:
                            print("Line number out of range.")
                    except ValueError:
                        print("Invalid line number.")
                elif cmd in (":a", ":append", ":i", ":insert"):
                    if len(sub_parts) < 3:
                        print("Usage: :a <line_number> <content>")
                        continue
                    try:
                        line_num = int(sub_parts[1])
                        insert_content = sub_parts[2]
                        if 0 <= line_num <= len(buffer):
                            buffer.insert(line_num, insert_content)
                            print(f"Inserted line after {line_num}")
                        else:
                            print("Line number out of range.")
                    except ValueError:
                        print("Invalid line number.")
                else:
                    print(f"Unknown editor command: {cmd}")
            else:
                buffer.append(line)
        return True
