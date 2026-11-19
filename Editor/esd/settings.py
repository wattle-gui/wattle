"""The Editor's settings file: ~/.config/wattle/editor.ini (Windows: the same folder under the user's home).

A plain text file in the INI style that anybody can edit. Lines that start with ; are comments. The Editor reads it when it starts
and never fails because of it: a wrong or unknown entry is ignored (the default is used) and `notes` says what was ignored. A missing
file is normal; it is made the first time something is saved. Saving changes only the line that changed: your own comments and
other entries stay as you wrote them."""
from __future__ import annotations

import configparser
from pathlib import Path

PATH = Path.home() / ".config" / "wattle" / "editor.ini"

TEMPLATE = """; Wattle Editor settings. Edit this file with any text editor; the Editor reads it when it starts.
; Lines that start with ; are comments. A wrong value is ignored (the default is used).

[editor]
; The board a new design is made for: the last choice in File > New Design (cyd, or the name of one of your boards).
default_device = cyd
; How fast Ctrl + mouse wheel zooms the canvas: Slow, Normal or Fast.
zoom_speed = Normal
; The folder for your designs and scripts (empty: the folder 'projects' of your Wattle folder).
projects_folder =
"""


class Settings:
    def __init__(self, path: Path | None = None) -> None:
        self.path = Path(path) if path else PATH
        self.notes: list[str] = []
        self._cp = configparser.ConfigParser(interpolation=None, inline_comment_prefixes=None)
        self.reload()

    def reload(self) -> None:
        self._cp = configparser.ConfigParser(interpolation=None, inline_comment_prefixes=None)
        self.notes = []
        try:
            text = self.path.read_text(encoding="utf-8")
        except OSError:
            return
        try:
            self._cp.read_string(text)
        except configparser.Error as e:
            self.notes.append(f"{self.path.name} could not be read ({e.__class__.__name__}); the defaults are used.")
            self._cp = configparser.ConfigParser(interpolation=None)

    def get(self, section: str, key: str, default: str = "") -> str:
        try:
            return self._cp.get(section, key).strip()
        except (configparser.Error, ValueError):
            return default

    def sections(self, prefix: str) -> list[str]:
        return [s for s in self._cp.sections() if s.startswith(prefix)]

    def set(self, section: str, key: str, value: str) -> None:
        """Change one entry in the file, keeping everything else (comments included) as it is."""
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            lines = self.path.read_text(encoding="utf-8").splitlines() if self.path.exists() else TEMPLATE.splitlines()
            head = f"[{section}]"
            start = next((i for i, l in enumerate(lines) if l.strip() == head), None)
            new = f"{key} = {value}"
            if start is None:
                lines += ["", head, new]
            else:
                end = next((i for i in range(start + 1, len(lines)) if lines[i].strip().startswith("[")), len(lines))
                hit = next((i for i in range(start + 1, end)
                            if lines[i].split("=", 1)[0].strip() == key and not lines[i].lstrip().startswith(";")), None)
                if hit is not None:
                    lines[hit] = new
                else:
                    last = max([i for i in range(start + 1, end) if lines[i].strip() and not lines[i].lstrip().startswith(";")] or [start])
                    lines.insert(last + 1, new)
            self.path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        except OSError as e:
            self.notes.append(f"The setting could not be saved: {e}")
        self.reload()

    def remove_section(self, section: str) -> None:
        """Take one [section] out of the file (its lines up to the next section); comments elsewhere stay."""
        try:
            lines = self.path.read_text(encoding="utf-8").splitlines()
            head = f"[{section}]"
            start = next((i for i, l in enumerate(lines) if l.strip() == head), None)
            if start is None:
                return
            end = next((i for i in range(start + 1, len(lines)) if lines[i].strip().startswith("[")), len(lines))
            while start > 0 and not lines[start - 1].strip():      # the blank line before it goes too
                start -= 1
            del lines[start:end]
            self.path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        except OSError as e:
            self.notes.append(f"The setting could not be saved: {e}")
        self.reload()
