"""Design / Screen / Widget instances (Option B on disk)."""

from __future__ import annotations

import copy
import re
from typing import Any

from esd.catalogue import is_interactive_kind, make_widget_defaults

_IDENT = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def is_python_id(name: str) -> bool:
    return bool(_IDENT.match(str(name or "")))


def get_path(data: dict, path: str, default=None):
    cur: Any = data
    for part in path.split("."):
        if not isinstance(cur, dict) or part not in cur:
            return default
        cur = cur[part]
    return cur


def set_path(data: dict, path: str, value) -> None:
    parts = path.split(".")
    cur = data
    for part in parts[:-1]:
        nxt = cur.get(part)
        if not isinstance(nxt, dict):
            nxt = {}
            cur[part] = nxt
        cur = nxt
    cur[parts[-1]] = value


class Design:
    def __init__(self, data: dict[str, Any] | None = None) -> None:
        self.data: dict[str, Any] = data if data is not None else empty_design()
        self.path: str | None = None

    @property
    def name(self) -> str:
        return str(get_path(self.data, "app.name") or "Design")

    def screen_size(self, screen_id: str | None = None) -> tuple[int, int]:
        sc = self.screen_by_id(screen_id) if screen_id else None
        if sc is None:
            sc = self.first_screen()
        if sc is not None:
            w = int(sc.get("width") or 0)
            h = int(sc.get("height") or 0)
            if w > 0 and h > 0:
                return max(1, w), max(1, h)
        w = int(get_path(self.data, "target.display.width") or 320)
        h = int(get_path(self.data, "target.display.height") or 240)
        return max(1, w), max(1, h)

    def screens(self) -> list[dict[str, Any]]:
        items = self.data.get("screens")
        return items if isinstance(items, list) else []

    def screen_by_id(self, screen_id: str) -> dict[str, Any] | None:
        for sc in self.screens():
            if str(sc.get("id") or "") == screen_id:
                return sc
        return None

    def first_screen(self) -> dict[str, Any] | None:
        items = self.screens()
        return items[0] if items else None

    def widgets_on(self, screen_id: str) -> list[dict[str, Any]]:
        sc = self.screen_by_id(screen_id)
        if sc is None:
            return []
        items = sc.get("widgets")
        return items if isinstance(items, list) else []

    def find_widget(self, widget_id: str) -> tuple[dict[str, Any], dict[str, Any]] | None:
        for sc in self.screens():
            for w in sc.get("widgets") or []:
                if str(w.get("id") or "") == widget_id:
                    return sc, w
        return None

    def all_ids(self) -> set[str]:
        ids: set[str] = set()
        for sc in self.screens():
            sid = str(sc.get("id") or "")
            if sid:
                ids.add(sid)
            for w in sc.get("widgets") or []:
                wid = str(w.get("id") or "")
                if wid:
                    ids.add(wid)
        return ids

    def unique_id(self, base: str) -> str:
        root = re.sub(r"[^A-Za-z0-9_]", "", base) or "widget"
        if root[0].isdigit():
            root = "w_" + root
        used = self.all_ids()
        n = 1
        while True:
            name = f"{root}{n}"
            if name not in used:
                return name
            n += 1

    def add_widget(self, screen_id: str, kind: str, x: int, y: int) -> dict[str, Any]:
        sc = self.screen_by_id(screen_id)
        if sc is None:
            raise ValueError(f"Unknown screen: {screen_id}")
        inst = make_widget_defaults(kind)
        inst["id"] = self.unique_id(kind)
        sw, sh = self.screen_size(screen_id)
        w = int(inst["w"]) if inst.get("w") is not None else 40
        h = int(inst["h"]) if inst.get("h") is not None else 24
        asked_x, asked_y = int(x), int(y)
        inst["x"] = max(0, min(asked_x, max(0, sw - w)))
        inst["y"] = max(0, min(asked_y, max(0, sh - h)))
        clamp_widget(inst, sw, sh)
        other = overlapping_interactive(self, screen_id, inst)
        if other is not None:
            shifted = int(inst["x"]) != asked_x or int(inst["y"]) != asked_y
            raise ValueError(overlap_text(other, shifted=shifted))
        widgets = sc.setdefault("widgets", [])
        widgets.append(inst)
        return inst

    def add_screen(self, *, like: dict[str, Any] | None = None) -> dict[str, Any]:
        src = like if isinstance(like, dict) else self.first_screen()
        sc = {
            "id": self.unique_id("screen"),
            "orientation": str((src or {}).get("orientation") or "landscape"),
            "width": int((src or {}).get("width") or self.screen_size()[0]),
            "height": int((src or {}).get("height") or self.screen_size()[1]),
            "background": str((src or {}).get("background") or "black"),
            "widgets": [],
        }
        screens = self.data.setdefault("screens", [])
        if not isinstance(screens, list):
            screens = []
            self.data["screens"] = screens
        screens.append(sc)
        return sc

    def delete_widget(self, widget_id: str) -> None:
        for sc in self.screens():
            widgets = sc.get("widgets")
            if not isinstance(widgets, list):
                continue
            sc["widgets"] = [w for w in widgets if str(w.get("id") or "") != widget_id]

    def delete_screen(self, screen_id: str) -> None:
        items = self.screens()
        if len(items) <= 1:
            raise ValueError("A Design must have at least one Screen.")
        self.data["screens"] = [s for s in items if str(s.get("id") or "") != screen_id]

    def reorder_widget(self, widget_id: str, *, to_front: bool) -> None:
        found = self.find_widget(widget_id)
        if found is None:
            return
        sc, inst = found
        widgets = list(sc.get("widgets") or [])
        widgets = [w for w in widgets if w is not inst]
        if to_front:
            widgets.append(inst)
        else:
            widgets.insert(0, inst)
        sc["widgets"] = widgets

    def apply_orientation(self, sc: dict[str, Any]) -> None:
        w = max(1, int(sc.get("width") or 320))
        h = max(1, int(sc.get("height") or 240))
        ori = str(sc.get("orientation") or "").lower()
        if ori == "landscape" and w < h:
            w, h = h, w
        elif ori == "portrait" and h < w:
            w, h = h, w
        sc["width"] = w
        sc["height"] = h
        for inst in sc.get("widgets") or []:
            clamp_widget(inst, w, h)

    def sync_orientation_from_size(self, sc: dict[str, Any]) -> None:
        w = int(sc.get("width") or 0)
        h = int(sc.get("height") or 0)
        if w > h:
            sc["orientation"] = "landscape"
        elif h > w:
            sc["orientation"] = "portrait"
        for inst in sc.get("widgets") or []:
            clamp_widget(inst, max(1, w), max(1, h))

    def copy(self) -> dict[str, Any]:
        return copy.deepcopy(self.data)


def clamp_widget(inst: dict[str, Any], sw: int, sh: int) -> None:
    kind = str(inst.get("widget") or "")
    w = int(inst.get("w") or 0)
    h = int(inst.get("h") or 0)
    if kind == "line":
        w = max(0, w)
        h = max(0, h)
    else:
        w = max(0, w)
        h = max(0, h)
    inst["w"] = min(w, sw)
    inst["h"] = min(h, sh)
    inst["x"] = max(0, min(int(inst.get("x") or 0), max(0, sw - int(inst["w"]))))
    inst["y"] = max(0, min(int(inst.get("y") or 0), max(0, sh - int(inst["h"]))))


def geometry_allowed(inst: dict[str, Any]) -> bool:
    """False when type rules forbid this width/height pair."""
    kind = str(inst.get("widget") or "")
    w = int(inst.get("w") or 0)
    h = int(inst.get("h") or 0)
    if kind == "line":
        return w > 0 or h > 0
    if kind in ("slider", "progressbar"):
        return w > 0 and h > 0 and w != h
    return w > 0 and h > 0


TREE_INDENT = 2


def lines_to_items(text: str) -> list[str]:
    """Choice items: one per line, blank lines dropped."""
    return [line.strip() for line in str(text or "").splitlines() if line.strip()]


def items_to_lines(items: Any) -> str:
    return "\n".join(str(item) for item in (items or []))


def text_to_tree(text: str) -> list[dict[str, Any]]:
    """Tree items from indented lines. Two spaces (or a tab) per level."""
    roots: list[dict[str, Any]] = []
    stack: list[tuple[int, dict[str, Any]]] = []
    for raw in str(text or "").splitlines():
        if not raw.strip():
            continue
        lead = raw[: len(raw) - len(raw.lstrip())].replace("\t", " " * TREE_INDENT)
        depth = len(lead) // TREE_INDENT
        depth = min(depth, len(stack))
        node: dict[str, Any] = {"text": raw.strip()}
        del stack[depth:]
        if stack:
            stack[-1][1].setdefault("items", []).append(node)
        else:
            roots.append(node)
        stack.append((depth, node))
    return roots


def _tree_children(node: dict[str, Any]) -> list:
    kids = node.get("items")
    if kids is None:
        kids = node.get("children")
    return kids if isinstance(kids, list) else []


def tree_to_text(items: Any, depth: int = 0) -> str:
    lines: list[str] = []
    for node in items or []:
        if not isinstance(node, dict):
            lines.append(" " * (TREE_INDENT * depth) + str(node))
            continue
        lines.append(" " * (TREE_INDENT * depth) + str(node.get("text") or ""))
        child_text = tree_to_text(_tree_children(node), depth + 1)
        if child_text:
            lines.append(child_text)
    return "\n".join(lines)


def tree_leaf_paths(items: Any, prefix: str = "") -> list[str]:
    """Paths of end items, joined with '/', for example Network/WiFi."""
    paths: list[str] = []
    for node in items or []:
        if not isinstance(node, dict):
            text = str(node)
            paths.append(f"{prefix}/{text}" if prefix else text)
            continue
        text = str(node.get("text") or "")
        path = f"{prefix}/{text}" if prefix else text
        kids = _tree_children(node)
        if kids:
            paths.extend(tree_leaf_paths(kids, path))
        else:
            paths.append(path)
    return paths


def _as_number(raw: Any) -> int | float | None:
    """JSON number, keeping int and float distinct. Booleans are not numbers."""
    if isinstance(raw, bool) or not isinstance(raw, (int, float)):
        return None
    if isinstance(raw, float) and (raw != raw or raw in (float("inf"), float("-inf"))):
        return None
    return raw


def _as_int(raw: Any) -> int | None:
    if isinstance(raw, bool):
        return None
    if isinstance(raw, int):
        return raw
    if isinstance(raw, float) and raw.is_integer() and abs(raw) < 1e15:
        return int(raw)
    return None


def cross_check_warning(inst: dict[str, Any]) -> str:
    """Soft checks. The values are kept; the caller shows this text."""
    kind = str(inst.get("widget") or "")
    notes: list[str] = []
    if kind in ("gauge", "stepper", "waveform", "barchart"):
        mn = _as_number(inst.get("min"))
        mx = _as_number(inst.get("max"))
        if mn is not None and mx is not None and mn >= mx:
            notes.append("Lowest value must be smaller than Highest value.")
        if kind == "gauge" and mn is not None and mx is not None and mn < mx:
            val = _as_number(inst.get("value"))
            if val is not None and (val < mn or val > mx):
                notes.append("Value should be between Lowest value and Highest value.")
    if kind == "barchart":
        bars = _as_int(inst.get("bars"))
        if bars is not None:
            labels = inst.get("labels")
            values = inst.get("values")
            if isinstance(labels, list) and len(labels) > bars:
                notes.append(
                    "Text under the bars is longer than the number of bars. The extra entries are kept."
                )
            if isinstance(values, list) and len(values) > bars:
                notes.append(
                    "Bar heights are longer than the number of bars. The extra entries are kept."
                )
    return " ".join(notes)


def _normalize_gauge(inst: dict[str, Any]) -> str | None:
    mn = _as_number(inst.get("min"))
    mx = _as_number(inst.get("max"))
    val = _as_number(inst.get("value"))
    if mn is None or mx is None or val is None:
        return "Lowest value, Highest value, and Value must be numbers."
    ticks = _as_int(inst.get("ticks"))
    if ticks is None or ticks < 1 or ticks > 50:
        return "Number of marks must be from 1 to 50."
    diameter = _as_int(inst.get("diameter"))
    if diameter is None or not (diameter == 0 or 20 <= diameter <= 240):
        return "Circle size must be 0, or from 20 to 240."
    sweep = _as_int(inst.get("sweep"))
    if sweep is None or sweep < 90 or sweep > 340:
        return "Angle of the scale must be from 90 to 340."
    inst["min"], inst["max"], inst["value"] = mn, mx, val
    inst["ticks"] = ticks
    inst["diameter"] = diameter
    inst["sweep"] = sweep
    if inst.get("text") is None:
        inst["text"] = ""
    else:
        inst["text"] = str(inst.get("text"))
    return None


def _normalize_stepper(inst: dict[str, Any]) -> str | None:
    mn = _as_number(inst.get("min"))
    mx = _as_number(inst.get("max"))
    val = _as_number(inst.get("value"))
    step = _as_number(inst.get("step"))
    if mn is None or mx is None or val is None or step is None:
        return "Lowest value, Highest value, Value, and Step must be numbers."
    if step <= 0:
        return "Step must be greater than 0."
    if mn < mx and (val < mn or val > mx):
        return "Value must be between Lowest value and Highest value."
    inst["min"], inst["max"], inst["value"], inst["step"] = mn, mx, val, step
    return None


def _normalize_waveform(inst: dict[str, Any]) -> str | None:
    mn = _as_number(inst.get("min"))
    mx = _as_number(inst.get("max"))
    if mn is None or mx is None:
        return "Lowest value and Highest value must be numbers."
    points = _as_int(inst.get("points"))
    if points is None or points < 2 or points > 300:
        return "Waveform Points must be from 2 to 300."
    style = str(inst.get("style") or "").lower()
    if style not in ("line", "bars"):
        return "Waveform Style must be line or bars."
    update = _as_int(inst.get("update_ms"))
    if update is None or update < 0 or update > 5000:
        return "Redraw time must be from 0 to 5000 ms."
    inst["min"], inst["max"] = mn, mx
    inst["points"] = points
    inst["style"] = style
    inst["update_ms"] = update
    if inst.get("title") is None:
        inst["title"] = ""
    else:
        inst["title"] = str(inst.get("title"))
    return None


def _normalize_barchart(inst: dict[str, Any]) -> str | None:
    mn = _as_number(inst.get("min"))
    mx = _as_number(inst.get("max"))
    if mn is None or mx is None:
        return "Lowest value and Highest value must be numbers."
    bars = _as_int(inst.get("bars"))
    if bars is None or bars < 1 or bars > 64:
        return "Number of bars must be from 1 to 64."
    update = _as_int(inst.get("update_ms"))
    if update is None or update < 0 or update > 5000:
        return "Redraw time must be from 0 to 5000 ms."
    labels = inst.get("labels")
    values = inst.get("values")
    if not isinstance(labels, list):
        return "Text under the bars must be a list of text."
    if not isinstance(values, list):
        return "Bar heights must be a list of numbers."
    clean_values: list[int | float] = []
    for item in values:
        num = _as_number(item)
        if num is None:
            return "Bar heights must be a list of numbers."
        clean_values.append(num)
    inst["min"], inst["max"] = mn, mx
    inst["bars"] = bars
    inst["update_ms"] = update
    inst["labels"] = ["" if item is None else str(item) for item in labels]
    inst["values"] = clean_values
    if inst.get("title") is None:
        inst["title"] = ""
    else:
        inst["title"] = str(inst.get("title"))
    return None


def normalize_typed_values(inst: dict[str, Any]) -> str | None:
    """Clamp type-specific values. Return an error string if the edit is illegal."""
    kind = str(inst.get("widget") or "")
    if kind == "choice":
        items = inst.get("items")
        if not isinstance(items, list):
            items = lines_to_items(str(items or ""))
        items = [str(item) for item in items]
        style = str(inst.get("style") or "radio").lower()
        if style not in ("radio", "dropdown"):
            return "Choice Style must be radio or dropdown."
        orientation = str(inst.get("orientation") or "vertical").lower()
        if orientation not in ("vertical", "horizontal"):
            return "Choice Orientation must be vertical or horizontal."
        raw_sel = inst.get("selected")
        if raw_sel is None and "value" in inst:
            raw_sel = inst.get("value")
        try:
            val = int(0 if raw_sel is None else raw_sel)
        except (TypeError, ValueError):
            return "Choice Selected must be an integer."
        last = len(items) - 1
        if val < -1 or val > last:
            return f"Choice Selected must be between -1 (none) and {last}."
        inst["items"] = items
        inst["style"] = style
        inst["orientation"] = orientation
        inst["selected"] = val
        inst.pop("value", None)
        return None
    if kind == "tree":
        items = inst.get("items")
        if not isinstance(items, list):
            items = text_to_tree(str(items or ""))
        inst["items"] = items
        selected = "" if inst.get("selected") is None else str(inst.get("selected"))
        paths = set(tree_leaf_paths(items))
        if selected and selected not in paths:
            return "Tree Selected must be an end item, for example Network/WiFi."
        inst["selected"] = selected
        return None
    if kind == "slider":
        try:
            mn = int(inst.get("min") or 0)
            mx = int(inst.get("max") or 0)
            step = int(inst.get("step") or 0)
            val = int(inst.get("value") or 0)
        except (TypeError, ValueError):
            return "Slider Min, Max, Value, and Step must be integers."
        if mn >= mx:
            return "Lowest value must be smaller than Highest value."
        if step <= 0:
            return "Slider Step must be a positive integer."
        if val < mn or val > mx:
            return "Value must be between Lowest value and Highest value."
        inst["min"], inst["max"], inst["step"], inst["value"] = mn, mx, step, val
        return None
    if kind == "progressbar":
        try:
            mx = int(inst.get("max") or 0)
            val = int(inst.get("value") or 0)
        except (TypeError, ValueError):
            return "Highest value and Value must be integers."
        if mx < 0:
            return "Highest value cannot be negative."
        if val < 0 or val > mx:
            return "Value must be between 0 and Highest value."
        inst["max"], inst["value"] = mx, val
        return None
    if kind == "line":
        try:
            thick = int(inst.get("thickness") or 0)
        except (TypeError, ValueError):
            return "Line thickness must be a positive integer."
        if thick <= 0:
            return "Line thickness must be a positive integer."
        inst["thickness"] = thick
        return None
    if kind == "keyboard":
        try:
            mx = int(inst.get("max_length") or 0)
        except (TypeError, ValueError):
            return "Max length must be an integer."
        if mx < 0:
            return "Max length cannot be negative."
        inst["max_length"] = mx
        layout = str(inst.get("layout") or "full").lower()
        if layout not in ("full", "numeric"):
            return "Keyboard layout must be full or numeric."
        inst["layout"] = layout
        return None
    if kind == "image":
        scale = str(inst.get("scale") or "fit").lower()
        if scale == "natural":
            scale = "fit"
        if scale not in ("fit", "fill", "stretch"):
            return "Image Scale must be fit, fill, or stretch."
        inst["scale"] = scale
        return None
    if kind == "gauge":
        return _normalize_gauge(inst)
    if kind == "stepper":
        return _normalize_stepper(inst)
    if kind == "waveform":
        return _normalize_waveform(inst)
    if kind == "barchart":
        return _normalize_barchart(inst)
    return None


def widget_rect(inst: dict[str, Any]) -> tuple[int, int, int, int]:
    return (
        int(inst.get("x") or 0),
        int(inst.get("y") or 0),
        max(0, int(inst.get("w") or 0)),
        max(0, int(inst.get("h") or 0)),
    )


def rects_overlap(a: tuple[int, int, int, int], b: tuple[int, int, int, int]) -> bool:
    ax, ay, aw, ah = a
    bx, by, bw, bh = b
    if aw <= 0 or ah <= 0 or bw <= 0 or bh <= 0:
        return False
    return ax < bx + bw and bx < ax + aw and ay < by + bh and by < ay + ah


def is_interactive_widget(inst: dict[str, Any]) -> bool:
    return is_interactive_kind(str(inst.get("widget") or ""))


def _blocks_overlap(inst: dict[str, Any]) -> bool:
    """Keyboard rectangles are stored but ignored: the keyboard takes the screen."""
    if str(inst.get("widget") or "") == "keyboard":
        return False
    return is_interactive_widget(inst)


def overlap_text(other: dict[str, Any], *, shifted: bool = False) -> str:
    """Why a drop or move was refused. Names the widget already in that spot."""
    name = str(other.get("id") or "another widget")
    kind = str(other.get("widget") or "widget")
    hidden = ""
    if not other.get("visible", True):
        hidden = " It is hidden, so the screen looks empty."
    if shifted:
        return (
            f"That widget does not fit in that spot. "
            f"It would cover {name} ({kind}).{hidden}"
        )
    return f"That spot covers {name} ({kind}).{hidden}"


def overlapping_interactive(
    design: Design, screen_id: str, inst: dict[str, Any], *, ignore_id: str | None = None
) -> dict[str, Any] | None:
    """Other interactive widget whose rect intersects *inst*, else None.

    Decorative widgets are ignored, so they may overlap anything.
    Keyboards are ignored too: their x, y, w, and h are not a touch rectangle.
    """
    if not _blocks_overlap(inst):
        return None
    self_id = str(inst.get("id") or "") if ignore_id is None else str(ignore_id)
    r = widget_rect(inst)
    for other in design.widgets_on(screen_id):
        if other is inst:
            continue
        if str(other.get("id") or "") == self_id:
            continue
        if not _blocks_overlap(other):
            continue
        if rects_overlap(r, widget_rect(other)):
            return other
    return None


def find_free_position(
    design: Design,
    screen_id: str,
    inst: dict[str, Any],
    start_x: int,
    start_y: int,
    step: int = 8,
) -> tuple[int, int] | None:
    """First origin where *inst* does not overlap another interactive widget."""
    if not is_interactive_widget(inst):
        return int(start_x), int(start_y)
    sw, sh = design.screen_size(screen_id)
    trial = {
        "widget": inst.get("widget"),
        "id": inst.get("id") or "",
        "x": int(start_x),
        "y": int(start_y),
        "w": int(inst.get("w") or 0),
        "h": int(inst.get("h") or 0),
    }
    clamp_widget(trial, sw, sh)
    ignore = str(trial.get("id") or "")
    w = max(1, int(trial["w"]))
    h = max(1, int(trial["h"]))
    max_x = max(0, sw - w)
    max_y = max(0, sh - h)
    step = max(1, int(step))
    seen: set[tuple[int, int]] = set()
    points: list[tuple[int, int]] = []
    first = (int(trial["x"]), int(trial["y"]))
    points.append(first)
    seen.add(first)
    for y in range(0, max_y + 1, step):
        for x in range(0, max_x + 1, step):
            if (x, y) not in seen:
                points.append((x, y))
                seen.add((x, y))
    for x, y in points:
        trial["x"], trial["y"] = x, y
        clamp_widget(trial, sw, sh)
        if overlapping_interactive(design, screen_id, trial, ignore_id=ignore) is None:
            return int(trial["x"]), int(trial["y"])
    return None


def empty_design() -> dict[str, Any]:
    return {
        "app": {
            "name": "Design",
            "purpose": "",
            "version": "1.0",
            "version_date": "",
        },
        "target": {
            "model": "",
            "processor": "",
            "board": "",
            "display": {
                "model": "",
                "width": 320,
                "height": 240,
                "interface": "",
                "driver": "",
            },
            "touch": {
                "model": "",
                "type": "",
                "interface": "",
                "driver": "",
            },
            "fonts": [
                {
                    "name": "default",
                    "sizes": [8, 16, 24],
                    "styles": ["bold", "italic"],
                }
            ],
        },
        "screens": [
            {
                "id": "main",
                "orientation": "landscape",
                "width": 320,
                "height": 240,
                "background": "black",
                "widgets": [],
            }
        ],
    }


def test_design() -> dict[str, Any]:
    """Suggested minimal TEST JSON, with Screen width/height as Design authority."""
    data = empty_design()
    data["app"]["name"] = "ESD TEST"
    data["app"]["purpose"] = "Test of the ESD JSON-driven Button implementation"
    data["screens"][0]["widgets"] = [
        {
            "widget": "button",
            "id": "test_button",
            "x": 100,
            "y": 90,
            "w": 120,
            "h": 50,
            "visible": True,
            "enabled": True,
            "background": "green",
            "color": "white",
            "border": {"color": "black", "width": 1},
            "text": "TEST",
            "font_type": "default",
            "font_size": "default",
            "alignment": "center",
            "bold": False,
            "italic": False,
            "accepts_input": True,
            "events": ["click"],
        }
    ]
    return data


def orientation_matches(width: int, height: int, orientation: str) -> bool:
    ori = str(orientation or "").lower()
    if ori == "landscape":
        return int(width) > int(height)
    if ori == "portrait":
        return int(height) > int(width)
    return True
