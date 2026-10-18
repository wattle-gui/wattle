"""Records the Editor's own actions for the "record then replay" tutorial-video idea
(see IDEAS.md). Off by default and zero-overhead unless WATTLE_RECORD is set.

Logs *decisions*, not mouse movement: which widget type was dropped where, which
property was set to what, which widget/screen was selected. A separate replay tool
(not written yet) turns this sequence back into real, humanly-paced input -- the
recording itself holds no pauses, so there is nothing to speed up or trim later.

    WATTLE_RECORD=/path/to/actions.jsonl ./ESP32_Editor.sh

Each line is one JSON object: {"t": <ms since recording started>, "kind": ..., ...}.
JSON-lines (one action per line, flushed immediately) rather than one JSON array, so a
recording already has everything in it even if the Editor is closed or crashes before
a deliberate "stop".
"""

from __future__ import annotations

import json
import os
import time
from typing import Any


class ActionRecorder:
    def __init__(self, path: str | None) -> None:
        self.path = path
        self._f = None
        self._t0 = time.monotonic()
        if path:
            try:
                # "w" (not "a"): each launch is a fresh recording session, not a continuation
                # of whatever an earlier launch left in this file. Still flushed after every
                # write below, so a crash mid-session loses nothing from *this* session.
                self._f = open(path, "w", encoding="utf-8")
            except OSError as e:
                print("recorder: could not open", path, "--", e)

    @property
    def active(self) -> bool:
        return self._f is not None

    def log(self, kind: str, **fields: Any) -> None:
        if self._f is None:
            return
        row = {"t": int((time.monotonic() - self._t0) * 1000), "kind": kind}
        row.update(fields)
        try:
            self._f.write(json.dumps(row) + "\n")
            self._f.flush()
        except OSError as e:
            print("recorder: write failed --", e)


def make_recorder() -> ActionRecorder:
    return ActionRecorder(os.environ.get("WATTLE_RECORD") or None)
