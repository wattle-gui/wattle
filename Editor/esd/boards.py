"""My boards: the boards that the set-up has recorded (~/.config/wattle/boards.json, written by tools/myboards.py).

A missing or damaged file is a normal case (nothing has been set up yet): the list is empty and the Editor still works."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

PATH = Path.home() / ".config" / "wattle" / "boards.json"


def load(path: Path | None = None) -> list[dict[str, Any]]:
    try:
        data = json.loads(Path(path or PATH).read_text(encoding="utf-8"))
        return [b for b in data if isinstance(b, dict) and b.get("name") and b.get("kind") and b.get("width") and b.get("height")]
    except (OSError, ValueError, TypeError):
        return []
