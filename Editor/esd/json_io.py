"""Load and save application JSON. Catalogue is never written."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from esd.catalogue import TRANSPARENT_BACKGROUNDS, WIDGET_KEY_ORDER, canonical_color, spec_for


def _order_map(data: dict[str, Any], keys: list[str]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for key in keys:
        if key in data:
            out[key] = data[key]
    for key, value in data.items():
        if key not in out:
            out[key] = value
    return out


def _order_border(border: Any) -> Any:
    if not isinstance(border, dict):
        return border
    return _order_map(border, ["color", "width"])


def _order_tree_nodes(nodes: Any) -> list:
    out: list = []
    for node in nodes or []:
        if not isinstance(node, dict):
            out.append({"text": str(node)})
            continue
        item: dict[str, Any] = {"text": node.get("text")}
        kids = node.get("items")
        if kids is None:
            kids = node.get("children")
        if isinstance(kids, list) and kids:
            item["items"] = _order_tree_nodes(kids)
        out.append(item)
    return out


def _order_widget(inst: dict[str, Any]) -> dict[str, Any]:
    kind = str(inst.get("widget") or "")
    ordered = _order_map(inst, WIDGET_KEY_ORDER.get(kind, ["widget", "id"]))
    if isinstance(ordered.get("border"), dict):
        ordered["border"] = _order_border(ordered["border"])
    if kind == "tree":
        ordered["items"] = _order_tree_nodes(ordered.get("items"))
    return ordered


def canonical_design(data: dict[str, Any]) -> dict[str, Any]:
    """Copy *data* with keys in the MASTER_blank.json order."""
    app = data.get("app") if isinstance(data.get("app"), dict) else {}
    target = data.get("target") if isinstance(data.get("target"), dict) else {}
    display = target.get("display") if isinstance(target.get("display"), dict) else {}
    touch = target.get("touch") if isinstance(target.get("touch"), dict) else {}
    fonts_out = []
    for font in target.get("fonts") or []:
        if isinstance(font, dict):
            fonts_out.append(_order_map(font, ["name", "sizes", "styles"]))
        else:
            fonts_out.append(font)
    screens_out = []
    for sc in data.get("screens") or []:
        if not isinstance(sc, dict):
            screens_out.append(sc)
            continue
        widgets = []
        for inst in sc.get("widgets") or []:
            if isinstance(inst, dict):
                widgets.append(_order_widget(inst))
            else:
                widgets.append(inst)
        screen = _order_map(sc, ["id", "orientation", "width", "height", "background", "widgets"])
        screen["widgets"] = widgets
        screens_out.append(screen)
    target_out = _order_map(
        {
            **target,
            "display": _order_map(display, ["model", "width", "height", "interface", "driver"]),
            "touch": _order_map(touch, ["model", "type", "interface", "driver"]),
            "fonts": fonts_out,
        },
        ["model", "processor", "board", "display", "touch", "fonts"],
    )
    ordered = _order_map(
        {
            **data,
            "app": _order_map(app, ["name", "purpose", "version", "version_date"]),
            "target": target_out,
            "screens": screens_out,
        },
        ["app", "target", "screens"],
    )
    return ordered


def _color_field(value: Any, *, allow_transparent: bool) -> Any:
    if not isinstance(value, str):
        return value
    canon = canonical_color(value, allow_transparent=allow_transparent)
    return canon if canon is not None else value


def _migrate_tree_nodes(nodes: Any) -> list:
    out: list = []
    for node in nodes or []:
        if not isinstance(node, dict):
            out.append({"text": str(node)})
            continue
        kids = node.get("items")
        if kids is None:
            kids = node.get("children")
        item: dict[str, Any] = {"text": node.get("text")}
        if isinstance(kids, list) and kids:
            item["items"] = _migrate_tree_nodes(kids)
        out.append(item)
    return out


def _filter_events(inst: dict[str, Any], renames: dict[str, str] | None = None) -> None:
    events = inst.get("events")
    if not isinstance(events, list):
        return
    spec = spec_for(str(inst.get("widget") or ""))
    allowed = {name for name, _desc in (spec.get("events") or [])}
    out: list[str] = []
    for name in events:
        mapped = (renames or {}).get(str(name), str(name))
        if mapped in allowed and mapped not in out:
            out.append(mapped)
    inst["events"] = out


def _migrate_widget(inst: dict[str, Any]) -> None:
    kind = str(inst.get("widget") or "")
    if kind == "label" and str(inst.get("background") or "").lower() == "transparent":
        inst["background"] = "black"
    if kind == "memo":
        _filter_events(inst, {"change": "click"})
    elif kind == "keyboard":
        _filter_events(inst, {"input": ""})
    elif kind == "image":
        if str(inst.get("scale") or "").lower() == "natural":
            inst["scale"] = "fit"
        _filter_events(inst)
    elif kind == "choice":
        if "selected" not in inst and "value" in inst:
            inst["selected"] = inst.get("value")
        inst.pop("value", None)
        inst.setdefault("style", "dropdown")
        inst.setdefault("orientation", "vertical")
        _filter_events(inst)
    elif kind == "tree":
        inst["items"] = _migrate_tree_nodes(inst.get("items"))
        if "selected" not in inst or inst.get("selected") is None:
            inst["selected"] = ""
        else:
            inst["selected"] = str(inst.get("selected"))
        _filter_events(inst, {"select": "selected"})
    elif kind in WIDGET_KEY_ORDER:
        _filter_events(inst)
    if kind not in TRANSPARENT_BACKGROUNDS and str(inst.get("background") or "").lower() == "transparent":
        inst["background"] = "black"
    allow_bg = kind in TRANSPARENT_BACKGROUNDS
    if "background" in inst:
        inst["background"] = _color_field(inst.get("background"), allow_transparent=allow_bg)
    if "color" in inst:
        inst["color"] = _color_field(inst.get("color"), allow_transparent=False)
    border = inst.get("border")
    if isinstance(border, dict) and "color" in border:
        border["color"] = _color_field(border.get("color"), allow_transparent=False)


def _migrate_design(data: dict[str, Any]) -> dict[str, Any]:
    """Bring older files onto the MASTER field names."""
    target = data.get("target")
    if not isinstance(target, dict):
        target = {}
        data["target"] = target
    target.setdefault("board", "")
    display = target.get("display")
    if not isinstance(display, dict):
        display = {}
        target["display"] = display
    display.setdefault("interface", "")
    touch = target.get("touch")
    if not isinstance(touch, dict):
        touch = {}
        target["touch"] = touch
    touch.setdefault("type", "")
    touch.setdefault("interface", "")
    for sc in data.get("screens") or []:
        if not isinstance(sc, dict):
            continue
        if "background" in sc:
            sc["background"] = _color_field(sc.get("background"), allow_transparent=False)
        for inst in sc.get("widgets") or []:
            if isinstance(inst, dict):
                _migrate_widget(inst)
    return data


def _ensure_screen_size(data: dict[str, Any]) -> dict[str, Any]:
    """Older files stored size only under target.display. Screen size is authoritative."""
    display = (data.get("target") or {}).get("display") or {}
    tw = int(display.get("width") or 320) or 320
    th = int(display.get("height") or 240) or 240
    for sc in data.get("screens") or []:
        if not isinstance(sc, dict):
            continue
        if not int(sc.get("width") or 0):
            sc["width"] = tw
        if not int(sc.get("height") or 0):
            sc["height"] = th
    return data


def _ensure_target_fonts(data: dict[str, Any]) -> dict[str, Any]:
    """Older files had no target.fonts. Picker writes that list."""
    target = data.get("target")
    if not isinstance(target, dict):
        target = {}
        data["target"] = target
    if not isinstance(target.get("fonts"), list):
        target["fonts"] = [
            {"name": "default", "sizes": [8, 16, 24], "styles": ["bold", "italic"]}
        ]
    return data


def load_design(path: str | Path) -> dict[str, Any]:
    raw = Path(path).read_text(encoding="utf-8")
    data = json.loads(raw)
    if not isinstance(data, dict):
        raise ValueError("Design JSON must be an object.")
    if "app" not in data or "screens" not in data:
        raise ValueError("Design JSON must contain app and screens.")
    return _migrate_design(_ensure_target_fonts(_ensure_screen_size(data)))


def save_design(path: str | Path, data: dict[str, Any]) -> None:
    text = json.dumps(canonical_design(data), indent=2) + "\n"
    Path(path).write_text(text, encoding="utf-8")
