#!/usr/bin/env python3
# myboards.py -- "My boards": the boards you have set up, written by the set-up and read by the Editor (File > New Design).
#
#   python3 tools/myboards.py add NAME KIND [--address HOST]     remember a board (KIND: board_cyd or board_browser)
#   python3 tools/myboards.py list                               print them
#
# The file is  ~/.config/wattle/boards.json  (Windows: the same folder under the user's home), next to the Editor's editor.ini. It is outside the
# Wattle folder on purpose: installing again or removing Wattle never touches it. A board is one entry: its name, its kind, and the size of its
# screen, taken from the hardware catalogue (hardware/<kind>.json). A browser board's screen is the phone's or tablet's, so its size here is only
# the usual shape; the Editor can ask the board for the size the last phone reported (the address is kept for that).
import json
import os
import sys
import time
from pathlib import Path

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PATH = Path.home() / ".config" / "wattle" / "boards.json"


def load(path=None):
    """The boards, as a list of dicts. A missing or damaged file is a normal case: the list is empty."""
    try:
        data = json.loads(Path(path or PATH).read_text(encoding="utf-8"))
        return [b for b in data if isinstance(b, dict) and b.get("name") and b.get("kind") and b.get("width") and b.get("height")]
    except (OSError, ValueError, TypeError):
        return []


def catalogue_size(kind):
    """(width, height) of a kind of board, from hardware/<kind>.json."""
    try:
        with open(os.path.join(HERE, "hardware", kind + ".json"), encoding="utf-8") as f:
            d = json.load(f)
        return int(d["width"]), int(d["height"])
    except (OSError, ValueError, KeyError, TypeError):
        return (320, 240) if kind == "board_cyd" else (360, 640)


def add(name, kind, address="", path=None):
    """Remember a board (a board with the same name is replaced). Returns the entry."""
    path = Path(path or PATH)
    w, h = catalogue_size(kind)
    entry = {"name": str(name).strip(), "kind": kind, "width": w, "height": h, "address": address or "", "added": time.strftime("%Y-%m-%d %H:%M")}
    boards = [b for b in load(path) if b["name"] != entry["name"]]
    boards.append(entry)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(boards, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    return entry


def main(argv):
    if argv and argv[0] == "add" and len(argv) >= 3:
        address = argv[argv.index("--address") + 1] if "--address" in argv else ""
        e = add(argv[1], argv[2], address)
        print("remembered: %s (%s, %d x %d)" % (e["name"], e["kind"], e["width"], e["height"]))
        return 0
    if argv and argv[0] == "list":
        for b in load():
            print("%-20s %-14s %4d x %-4d %s" % (b["name"], b["kind"], b["width"], b["height"], b.get("address", "")))
        return 0
    print(__doc__)
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
