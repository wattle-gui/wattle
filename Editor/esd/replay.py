"""Replays a recording made by recorder.py (WATTLE_RECORD) with a human-looking cursor.

Runs as a special mode of the Editor itself (WATTLE_REPLAY=path/to/actions.jsonl), not a
separate program, because it needs the Editor's own live widget positions (the Palette
entries, the canvas) to know where on screen to actually move the cursor -- hardcoded pixel
coordinates would break the moment the window was a different size or position.

SECOND APPROACH, after the first (ydotool, injecting real OS-level input) proved unreliable
on this desktop -- see IDEAS.md for the full story. In short: this is a Wayland session, and
real cursor movement goes through a chain of things outside this process (a root daemon, the
kernel's uinput device, the GNOME/Mutter compositor's own interpretation of that device) --
three different live tests each failed in a different way (wrong landing position, a crashed
subprocess, and finally Qt itself reporting zero actual cursor movement despite "successful"
ydotool calls). None of that was fixable by inspecting code alone without seeing the screen.

This version draws its OWN small cursor icon as a floating window and moves *that* instead --
entirely within this one process, using the exact same mapToGlobal() coordinates the rest of
the Editor already trusts internally, so there is no cross-process/cross-protocol coordinate
translation left to go wrong. The actual "drop" is performed by calling the same signal the
real drag-and-drop machinery already uses (canvas.widgetDropped), not by trying to fake a real
OS-level drag -- the cursor's visible movement and the actual effect are deliberately kept
independent, so a visual hiccup can never silently fail to add the widget, and vice versa.

What it covers now: "drop" (cursor from the Palette to the canvas), "set" (the cursor visits the real Object
Inspector control for a yes/no choice, a number or a plain text field -- see _queue_set), and "geometry" (moving and
resizing a widget on the canvas). Not yet visible: anything that opens its own popup (font choice, the colour
dialog, tree paths) or a multi-row list -- those are still applied directly, with no cursor movement (see IDEAS.md).

Every step runs through QTimer.singleShot chaining, one short step at a time, instead of a
Python loop with time.sleep() -- time.sleep() on the Qt main thread stops the Editor's own
event loop from running, which is what caused the first version's "Wattle not responding".
"""

from __future__ import annotations

import json
import math
import os
import random
from typing import Any, Callable

from PyQt6.QtCore import QPoint, Qt, QTimer
from PyQt6.QtGui import QColor, QCursor, QPainter, QPolygon
from PyQt6.QtWidgets import QWidget

# WATTLE_REPLAY_SLOW=2 makes every cursor move twice as slow (1.5 = a bit slower, 1 = the default).
try:
    _SLOW = max(0.25, float(os.environ.get("WATTLE_REPLAY_SLOW", "1")))
except ValueError:
    _SLOW = 1.0

_CURSOR_POINTS = [
    QPoint(1, 1), QPoint(1, 18), QPoint(6, 14), QPoint(9, 21),
    QPoint(12, 20), QPoint(9, 13), QPoint(16, 13),
]


class CursorOverlay(QWidget):
    """A small floating window drawn to look like a mouse pointer. Click-through (does not
    intercept real input) and always on top, so it sits visibly over whatever it's "pointing
    at" without being mistaken by the Editor for a real click."""

    def __init__(self) -> None:
        super().__init__(
            None,
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool,
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.resize(24, 28)
        self._pressed = False

    def set_pressed(self, pressed: bool) -> None:
        if pressed != self._pressed:
            self._pressed = pressed
            self.update()

    def move_to(self, point: tuple[int, int]) -> None:
        self.move(point[0], point[1])

    def paintEvent(self, _event) -> None:  # noqa: N802
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        poly = QPolygon(_CURSOR_POINTS)
        p.setBrush(QColor("#ffcc00" if self._pressed else "#ffffff"))
        p.setPen(QColor("#202020"))
        p.drawPolygon(poly)


def _bezier(p0, p1, p2, t: float):
    x = (1 - t) ** 2 * p0[0] + 2 * (1 - t) * t * p1[0] + t**2 * p2[0]
    y = (1 - t) ** 2 * p0[1] + 2 * (1 - t) * t * p1[1] + t**2 * p2[1]
    return x, y


def _ease(t: float) -> float:
    """Slow-fast-slow (cosine ease), like a real hand accelerating then settling."""
    return (1 - math.cos(t * math.pi)) / 2


def human_path(start: tuple[int, int], end: tuple[int, int], *, steps: int = 40) -> list[tuple[int, int]]:
    """Points along a gently curved path from start to end -- not a straight line, and not
    perfectly smooth either (a little randomness in the curve and in each point)."""
    dx, dy = end[0] - start[0], end[1] - start[1]
    dist = math.hypot(dx, dy)
    if dist < 2:
        return [end]
    # A control point off to one side of the straight line, so the path bows out a bit,
    # scaled down for short moves so it doesn't overshoot visibly on a small drag.
    bow = min(60, dist * 0.25) * random.choice((-1, 1))
    mx, my = (start[0] + end[0]) / 2, (start[1] + end[1]) / 2
    perp = (-dy / dist, dx / dist)
    ctrl = (mx + perp[0] * bow, my + perp[1] * bow)
    pts = []
    for i in range(1, steps + 1):
        t = _ease(i / steps)
        x, y = _bezier(start, ctrl, end, t)
        jitter = random.uniform(-1.2, 1.2) if i < steps else 0  # dead steady on arrival
        pts.append((round(x + jitter), round(y + jitter)))
    return pts


class Replayer:
    """Owns the MainWindow and walks a recorded action log against it.

    Builds the whole thing as a flat list of (delay_ms, fn) steps up front, then fires
    them one at a time through QTimer.singleShot -- see the module docstring for why."""

    def __init__(self, win) -> None:
        self.win = win
        self.overlay = CursorOverlay()
        p = QCursor.pos()
        self._cursor = (p.x(), p.y())
        self.overlay.move_to(self._cursor)
        self.overlay.show()
        print("replay: starting cursor position:", self._cursor, flush=True)
        self._queue: list[tuple[int, Callable[[], None]]] = []

    def _schedule(self, delay_ms: int, fn: Callable[[], None]) -> None:
        self._queue.append((max(0, int(delay_ms)), fn))

    def _insert_front(self, steps: list[tuple[int, Callable[[], None]]]) -> None:
        """Like _schedule, but for steps discovered *while a step is already running* (e.g.
        _queue_set deciding, at the moment it actually fires, that it needs to animate a
        click) -- these must run next, before whatever was already queued after this point,
        not get appended to the end behind it."""
        self._queue[0:0] = [(max(0, int(delay_ms)), fn) for delay_ms, fn in steps]

    def _build_move_steps(
        self, end: tuple[int, int], *, duration_s: float = 0.6, lead_ms: int = 0
    ) -> list[tuple[int, Callable[[], None]]]:
        start = self._cursor
        pts = human_path(start, end)
        per_step_ms = (duration_s * _SLOW * 1000) / len(pts)
        steps = [
            (lead_ms if i == 0 else per_step_ms, (lambda x=x, y=y: self.overlay.move_to((x, y))))
            for i, (x, y) in enumerate(pts)
        ]
        self._cursor = end
        return steps

    def _schedule_move(self, end: tuple[int, int], *, duration_s: float = 0.6, lead_ms: int = 0) -> None:
        for delay_ms, fn in self._build_move_steps(end, duration_s=duration_s, lead_ms=lead_ms):
            self._schedule(delay_ms, fn)

    def _palette_item(self, kind: str):
        """The actual Palette QTreeWidgetItem for a widget kind ("button", "slider", ...),
        or None. Returned separately from its on-screen position so the drop can really
        select it (a real highlight), not just draw a cursor near it."""
        tree = getattr(self.win, "palette", None)
        if tree is None:
            return None
        root = tree.invisibleRootItem()
        stack = [root.child(i) for i in range(root.childCount())]
        while stack:
            node = stack.pop(0)
            if node is None:
                continue
            if str(node.data(0, Qt.ItemDataRole.UserRole) or "") == kind:
                return node
            stack.extend(node.child(i) for i in range(node.childCount()))
        return None

    def _palette_item_center(self, kind: str):
        tree = getattr(self.win, "palette", None)
        it = self._palette_item(kind)
        if tree is None or it is None:
            return None
        center = tree.visualItemRect(it).center()
        g = tree.viewport().mapToGlobal(center)
        return g.x(), g.y()

    def _canvas_point(self, local_x: int, local_y: int):
        sr = self.win.canvas.screen_rect()
        g = self.win.canvas.mapToGlobal(QPoint(sr.x() + local_x, sr.y() + local_y))
        return g.x(), g.y()

    def _queue_drop(self, kind: str, x: int, y: int, *, lead_ms: int) -> None:
        item = self._palette_item(kind)
        src = self._palette_item_center(kind)
        dst = self._canvas_point(x, y)
        print("replay: drop", kind, "-> palette@", src, "canvas@", dst, flush=True)
        if src is None or dst is None:
            self._schedule(
                lead_ms,
                lambda: print("replay: could not find on-screen position for drop of", kind, "-- skipped", flush=True),
            )
            return
        self._schedule_move(src, lead_ms=lead_ms)
        self._schedule(150, lambda: self.overlay.set_pressed(True))
        if item is not None:
            # A real selection on the actual Palette row -- its own highlight style does the
            # rest, same as the real click used for bool toggles (see _queue_set). The drawn
            # cursor's own colour change alone was too easy to miss.
            def highlight(item=item) -> None:
                # setCurrentItem() alone moves keyboard focus but does not reliably mark the
                # item State_Selected for painting (current vs. selected are different things
                # in Qt) -- setSelected(True) is what the delegate's paint() actually checks.
                self.win.palette.setCurrentItem(item)
                item.setSelected(True)

            self._schedule(0, highlight)
        self._schedule_move(dst, duration_s=1.4, lead_ms=350)  # a visible pause while "pressed", then a slower drag
        # The visible drag and the actual effect are independent on purpose (see module
        # docstring): this emits the same signal real drag-and-drop already uses, so the
        # widget is really added regardless of anything about the cursor's own animation.
        self._schedule(100, lambda: self.win.canvas.widgetDropped.emit(kind, x, y))
        self._schedule(120, lambda: self.overlay.set_pressed(False))

    def _queue_select(self, token: str, *, lead_ms: int) -> None:
        def do_select() -> None:
            # Real UI usage can never select a widget that doesn't exist yet -- but the
            # recording can log exactly that for a split second, as an artifact of how a
            # real drag gesture gets captured (a "select" logged a moment before the "drop"
            # that actually creates the thing). Replaying that too early leaves the Editor's
            # selection state thinking nothing changed once the real widget shows up a moment
            # later, and the Object Inspector never refreshes for it. Skip it; a real one for
            # the same widget always follows right after the drop anyway.
            if token.startswith("widget:") and self.win.design.find_widget(token.split(":", 1)[1]) is None:
                print("replay: skipping select", token, "-- does not exist yet", flush=True)
                return
            print("replay: selecting", token, flush=True)
            self.win.canvas.select(token)

        self._schedule(lead_ms, do_select)

    def _queue_set(self, a: dict, *, lead_ms: int) -> None:
        """Most property kinds now get real, visible interaction with their actual Object
        Inspector control -- looked up via MainWindow._choices, the same dict the Editor
        itself keeps a live reference in for every property it draws a row for. A bool
        (ChoiceRow) gets its matching On/Off button really clicked; a number (QSpinBox /
        JsonNumberBox) gets setValue() called after the cursor visits it, which fires the
        exact same valueChanged signal a real spin would; a plain text field gets its text
        set then the Editor's own save method called directly (QLineEdit's editingFinished
        does not fire from setText() alone, unlike a real Enter/focus-out).

        Kinds not covered yet -- anything that opens its own popup (PickRow: font type/size,
        tree paths; the colour dialog) or a multi-row list (EntryListEditor/BarRowsEditor,
        multiline text) -- still apply directly with no visible movement. Those each need
        their own bespoke interaction and are more involved; see IDEAS.md."""
        from PyQt6.QtWidgets import QAbstractSpinBox, QLineEdit

        from esd.inspector_widgets import ChoiceRow

        key, value = a["key"], a["value"]
        design_level = bool(a.get("design_level"))

        def resolve():
            wid, sid = a.get("widget"), a.get("screen")
            widget, screen = None, None
            if wid:
                found = self.win.design.find_widget(wid)
                if found:
                    screen, widget = found
            elif sid:
                screen = self.win.design.screen_by_id(sid)
            return widget, screen

        def apply_direct() -> None:
            widget, screen = resolve()
            if key == "id":                      # a rename goes through the Editor's own rename (uniqueness, tree, title)
                self.win._set_id(str(value), widget, screen)
                return
            self.win._set_value(key, value, design_level, widget, screen)
            self.win._rebuild_inspector()

        def do_set() -> None:
            if key == "events":
                # Not in _choices (events bypass the generic property row entirely, one
                # QCheckBox per event rather than a single control) -- its own dict,
                # populated the same way, keyed by event name. The recorded value is the
                # *whole* resulting list, same as a real user ends up with after ticking one
                # box; click whichever boxes actually need to flip to reach it (normally
                # just the one actually ticked in the real session).
                boxes = self.win._event_boxes
                wanted = set(value or [])
                to_click = [ev for ev, box in boxes.items() if box.isChecked() != (ev in wanted)]
                print("replay: set events ->", value, "| clicking:", to_click, flush=True)
                steps: list[tuple[int, Callable[[], None]]] = []
                for ev in to_click:
                    box = boxes[ev]
                    c = box.mapToGlobal(box.rect().center())
                    steps += self._build_move_steps((c.x(), c.y()))
                    steps.append((120, lambda: self.overlay.set_pressed(True)))
                    steps.append((100, box.click))
                    steps.append((120, lambda: self.overlay.set_pressed(False)))
                if steps:
                    self._insert_front(steps)
                else:
                    apply_direct()
                return

            # Looked up HERE, at the moment this step actually runs -- not back when the
            # whole queue was first built. _choices reflects whatever the Inspector is
            # showing *right now*, which depends on the drop/select steps before this one
            # having actually happened first. Doing this lookup eagerly (the first version's
            # bug) always saw the very first, initial state instead.
            ed = self.win._choices.get(key)
            print("replay: set", key, "=", value, "-> control is", type(ed).__name__ if ed else None,
                  flush=True)

            if isinstance(ed, ChoiceRow):
                target = next((b for (_l, d), b in zip(ed._items, ed._buttons) if d == value), None)
                if target is None:
                    apply_direct()
                    return
                c = target.mapToGlobal(target.rect().center())
                steps = self._build_move_steps((c.x(), c.y()))
                steps.append((120, lambda: self.overlay.set_pressed(True)))
                steps.append((100, target.click))  # a real click: fires the Editor's own signal chain
                steps.append((120, lambda: self.overlay.set_pressed(False)))
                self._insert_front(steps)
                return

            if isinstance(ed, QAbstractSpinBox):
                c = ed.mapToGlobal(ed.rect().center())
                steps = self._build_move_steps((c.x(), c.y()))
                steps.append((150, lambda: self.overlay.set_pressed(True)))
                steps.append((200, lambda: ed.setValue(value)))  # fires valueChanged for real
                steps.append((100, lambda: self.overlay.set_pressed(False)))
                self._insert_front(steps)
                return

            if isinstance(ed, QLineEdit):
                c = ed.mapToGlobal(ed.rect().center())
                steps = self._build_move_steps((c.x(), c.y()))
                steps.append((150, lambda: self.overlay.set_pressed(True)))
                steps.append((200, lambda: ed.setText(str(value))))
                steps.append((150, apply_direct))  # setText() alone does not fire editingFinished
                steps.append((100, lambda: self.overlay.set_pressed(False)))
                self._insert_front(steps)
                return

            apply_direct()

        self._schedule(lead_ms, do_set)

    def _queue_geometry(self, a: dict, *, lead_ms: int) -> None:
        """A resize-handle or move drag on the canvas (see window.py's
        _record_drag_finished for why this is its own action kind, not a "set"). Only the
        final x/y/w/h was recorded, not the drag itself -- the visual path here is rebuilt
        from whatever the widget's geometry actually is right now (at replay time, not
        recording time) to the recorded target, same reasoning as the "set" lookups above.
        The actual change is applied through _set_value for each changed field (so it gets
        the same clamping/overlap checks a real edit would), independent of the drag
        animation, same separation used everywhere else in this module."""

        def do_geometry() -> None:
            wid = a.get("widget")
            found = self.win.design.find_widget(wid) if wid else None
            if found is None:
                print("replay: geometry for missing widget", wid, "-- skipped", flush=True)
                return
            screen, widget = found
            before = {k: int(widget.get(k) or 0) for k in ("x", "y", "w", "h")}
            after = {k: int(a.get(k, before[k])) for k in ("x", "y", "w", "h")}
            print("replay: geometry", wid, before, "->", after, flush=True)
            if before == after:
                return

            # Which handle was actually dragged was never recorded -- inferred here instead
            # from which coordinates actually changed, picking the point on the rectangle
            # that edge/corner's handle would be at. Guessing wrong (e.g. always assuming the
            # bottom-right corner, the first version's bug) can pick an anchor that happens
            # not to move at all for a particular drag -- e.g. a top-edge resize leaves the
            # bottom-right corner exactly where it was, collapsing the animation to nothing
            # even though the resize itself is real and large.
            x_changed = before["x"] != after["x"]
            w_changed = before["w"] != after["w"]
            y_changed = before["y"] != after["y"]
            h_changed = before["h"] != after["h"]

            def anchor(state: dict) -> tuple[int, int]:
                ax = state["x"] if x_changed else (state["x"] + state["w"] if w_changed else state["x"] + state["w"] // 2)
                ay = state["y"] if y_changed else (state["y"] + state["h"] if h_changed else state["y"] + state["h"] // 2)
                return self._canvas_point(ax, ay)

            src, dst = anchor(before), anchor(after)

            def apply_live(t: float) -> None:
                # The widget's own size/position grows or moves smoothly alongside the
                # cursor, like a real drag -- set directly here (not through _set_value,
                # which would push a flood of undo entries and overlap checks for every
                # intermediate frame of one drag). The real, validated commit is apply_final.
                for key in ("x", "y", "w", "h"):
                    widget[key] = round(before[key] + (after[key] - before[key]) * t)
                self.win.canvas.update()

            def apply_final() -> None:
                # The Editor checks that the widget stays inside the screen after EVERY single property it is given, but a
                # real drag changes position and size together. So one order of x, y, w, h can fail where another works
                # (e.g. moving a tall widget down before it is made shorter: the Editor pulls it back up). Try a few orders
                # until the widget really has the recorded position and size.
                for order in (("x", "y", "w", "h"), ("w", "h", "x", "y"), ("h", "w", "y", "x"), ("y", "x", "h", "w")):
                    for key in ("x", "y", "w", "h"):
                        widget[key] = before[key]  # apply_live already moved it; _set_value needs the real "before"
                    for key in order:
                        if after[key] != before[key]:
                            self.win._set_value(key, after[key], False, widget, screen)
                    if all(widget.get(k) == after[k] for k in ("x", "y", "w", "h")):
                        break
                self.win._rebuild_inspector()

            def move_and_resize(x: int, y: int, t: float) -> None:
                self.overlay.move_to((x, y))
                apply_live(t)

            steps = self._build_move_steps(src, lead_ms=0)
            steps.append((150, lambda: self.overlay.set_pressed(True)))
            drag_pts = human_path(src, dst)
            per_step_ms = 1000 * _SLOW / len(drag_pts)
            for i, (x, y) in enumerate(drag_pts):
                t = (i + 1) / len(drag_pts)
                steps.append((
                    200 if i == 0 else per_step_ms,
                    lambda x=x, y=y, t=t: move_and_resize(x, y, t),
                ))
            self._cursor = dst
            steps.append((100, apply_final))
            steps.append((120, lambda: self.overlay.set_pressed(False)))
            self._insert_front(steps)

        self._schedule(lead_ms, do_geometry)

    def run(self, path: str) -> None:
        with open(path, encoding="utf-8") as f:
            actions: list[dict[str, Any]] = [json.loads(line) for line in f if line.strip()]
        print("replay: %d actions from %s" % (len(actions), path), flush=True)
        last_t = 0
        for a in actions:
            gap_ms = int(a.get("t", last_t) - last_t)
            last_t = a.get("t", last_t)
            lead_ms = min(max(gap_ms, 0), 1200)  # keep real thinking-gaps, capped so it doesn't drag
            kind = a.get("kind")
            if kind == "drop":
                self._queue_drop(a["widget"], a["x"], a["y"], lead_ms=lead_ms)
            elif kind == "select":
                self._queue_select(a["token"], lead_ms=lead_ms)
            elif kind == "set":
                self._queue_set(a, lead_ms=lead_ms)
            elif kind == "geometry":
                self._queue_geometry(a, lead_ms=lead_ms)
            else:
                self._schedule(lead_ms, lambda k=kind: print("replay: unknown action kind", k, "-- skipped", flush=True))
        self._schedule(0, self._finish)
        self._pump()

    def _finish(self) -> None:
        self.overlay.hide()
        self.overlay.deleteLater()
        print("replay: done", flush=True)

    def _pump(self) -> None:
        if not self._queue:
            return
        delay_ms, fn = self._queue.pop(0)

        def step() -> None:
            try:
                fn()
            except Exception as e:
                # One bad step must not silently end the whole replay here -- keep going.
                print("replay: step failed, continuing --", repr(e), flush=True)
            self._pump()

        QTimer.singleShot(delay_ms, step)
