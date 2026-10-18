"""Font type, size, and style from design["target"]["fonts"].

The Font box lists those names only, with default first. System faces are not added.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

_REGISTERED: set[str] = set()
_ROOT = Path(__file__).resolve().parent.parent

# Designer faces (HTML-Creator set plus faces common on this Linux desktop).
_PREFERRED_FACES = [
    "Ubuntu",
    "Noto Sans",
    "DejaVu Sans",
    "Liberation Sans",
    "FreeSans",
    "Segoe UI",
    "Arial",
    "Tahoma",
    "Verdana",
    "Courier New",
    "DejaVu Sans Mono",
    "Liberation Mono",
    "Ubuntu Mono",
    "Noto Sans Mono",
    "Times New Roman",
    "Georgia",
    "Trebuchet MS",
    "Comic Sans MS",
    "DejaVu Serif",
    "Liberation Serif",
    "FreeSerif",
    "Noto Serif",
]


def _is_ascii_family(name: Any) -> bool:
    text = str(name or "").strip()
    if not text or text.lower() == "default":
        return False
    return all(32 <= ord(ch) < 127 for ch in text)


def _norm_type(value: Any) -> str:
    text = str(value or "").strip()
    return text or "default"


def _norm_size(value: Any):
    if value is None:
        return "default"
    text = str(value).strip()
    if not text or text.lower() == "default":
        return "default"
    try:
        return int(text)
    except (TypeError, ValueError):
        return text


def _uniq(items: list) -> list:
    seen: set[str] = set()
    out: list = []
    for item in items:
        key = f"{type(item).__name__}:{item}"
        if key in seen:
            continue
        seen.add(key)
        out.append(item)
    return out


class FontCatalog:
    def __init__(self) -> None:
        self.types: list[str] = ["default"]
        self.sizes: list = ["default"]
        self.sizes_by_type: dict[str, list] = {}
        self.styles_by_type: dict[str, list[str]] = {}
        self.files_by_type: dict[str, str] = {}
        self.manifests: dict[str, dict[str, Any]] = {}

    def add_type(self, name: Any, *, sizes=None, styles=None, file: str | None = None) -> None:
        t = _norm_type(name)
        if t not in self.types:
            self.types.append(t)
        if file:
            self.files_by_type[t] = str(file)
        if styles:
            self.styles_by_type[t] = [str(s) for s in styles]
        if sizes is None:
            return
        bucket = self.sizes_by_type.setdefault(t, ["default"])
        for raw in sizes:
            sz = _norm_size(raw)
            if sz not in bucket:
                bucket.append(sz)
            if sz not in self.sizes:
                self.sizes.append(sz)

    def sizes_for(self, font_type: Any) -> list:
        """Sizes for one face: Default, then that face's sizes. No other face's sizes."""
        t = _norm_type(font_type)
        bucket = self.sizes_by_type.get(t)
        if bucket:
            return _uniq(["default", *[s for s in bucket if s != "default"]])
        if t == "default":
            return ["default", 8, 16, 24]
        return ["default"]

    def size_allowed(self, font_type: Any, font_size: Any) -> bool:
        return _norm_size(font_size) in self.sizes_for(font_type)

    def styles_for(self, font_type: Any) -> list[str]:
        """Style names this face may use. default always has bold and italic."""
        t = _norm_type(font_type)
        if t == "default":
            return ["bold", "italic"]
        found: list[str] = []
        for raw in self.styles_by_type.get(t) or []:
            name = str(raw).strip().lower()
            if name in ("bold", "italic") and name not in found:
                found.append(name)
        return found

    def has_type(self, font_type: Any) -> bool:
        return _norm_type(font_type) in self.types

    def preview_size(self, font_type: Any, font_size: Any) -> int | None:
        sz = _norm_size(font_size)
        if sz != "default":
            try:
                return max(6, int(sz))
            except (TypeError, ValueError):
                return None
        for item in self.sizes_for(font_type):
            if item != "default":
                try:
                    return max(6, int(item))
                except (TypeError, ValueError):
                    continue
        return None

    def merge(self, other: "FontCatalog") -> None:
        for t in other.types:
            self.add_type(
                t,
                sizes=other.sizes_by_type.get(t),
                styles=other.styles_by_type.get(t),
                file=other.files_by_type.get(t),
            )
            if t in other.manifests and t not in self.manifests:
                self.manifests[t] = other.manifests[t]

    def target_entry(self, font_type: Any) -> dict[str, Any]:
        t = _norm_type(font_type)
        if t in self.manifests:
            return dict(self.manifests[t])
        sizes = [s for s in self.sizes_for(t) if s != "default"]
        entry: dict[str, Any] = {"name": t, "sizes": sizes}
        styles = self.styles_by_type.get(t)
        if styles:
            entry["styles"] = list(styles)
        if t in self.files_by_type:
            entry["file"] = self.files_by_type[t]
        return entry

    def register_files(self) -> None:
        try:
            from PyQt6.QtGui import QFontDatabase
        except Exception:
            return
        for _name, path in self.files_by_type.items():
            if path in _REGISTERED:
                continue
            p = Path(path)
            if not p.is_file():
                cand = _ROOT / path
                if cand.is_file():
                    p = cand
            if not p.is_file():
                continue
            QFontDatabase.addApplicationFont(str(p))
            _REGISTERED.add(path)
            _REGISTERED.add(str(p))


def _remember_manifest(cat: FontCatalog, name: Any, spec: dict[str, Any]) -> None:
    t = _norm_type(name)
    cat.manifests[t] = {
        "name": t,
        "sizes": list(spec.get("sizes") or spec.get("size") or []),
        "styles": list(spec.get("styles") or []),
    }


def _ingest_font_list(cat: FontCatalog, fonts: Any) -> None:
    if isinstance(fonts, dict):
        for name, spec in fonts.items():
            if isinstance(spec, dict):
                cat.add_type(
                    spec.get("name") or name,
                    sizes=spec.get("sizes") or spec.get("size"),
                    styles=spec.get("styles"),
                    file=spec.get("file") or spec.get("path") or spec.get("source"),
                )
                _remember_manifest(cat, spec.get("name") or name, spec)
            elif isinstance(spec, (list, tuple)):
                cat.add_type(name, sizes=spec)
            else:
                cat.add_type(name)
        return
    if not isinstance(fonts, list):
        return
    for item in fonts:
        if isinstance(item, dict):
            name = item.get("name") or item.get("type") or item.get("id")
            cat.add_type(
                name,
                sizes=item.get("sizes") or item.get("size"),
                styles=item.get("styles"),
                file=item.get("file") or item.get("path") or item.get("source"),
            )
            _remember_manifest(cat, name, item)
        else:
            cat.add_type(item)


def catalog_from_target(target: dict[str, Any] | None) -> FontCatalog:
    cat = FontCatalog()
    _ingest_font_list(cat, (target or {}).get("fonts"))
    cat.types = _uniq(["default", *[t for t in cat.types if t != "default"]])
    cat.sizes = _uniq(["default", *[s for s in cat.sizes if s != "default"]])
    return cat


def _font_families() -> list[str]:
    try:
        from PyQt6.QtGui import QFontDatabase
    except Exception:
        return []
    names = []
    try:
        names = list(QFontDatabase.families(QFontDatabase.WritingSystem.Latin))
    except Exception:
        try:
            names = list(QFontDatabase.families())
        except Exception:
            try:
                names = list(QFontDatabase().families())
            except Exception:
                return []
    out: list[str] = []
    seen: set[str] = set()
    for raw in names:
        text = str(raw or "").strip()
        if not _is_ascii_family(text):
            continue
        key = text.lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(text)
    return out


def catalog_from_system() -> FontCatalog:
    """Installed faces. The designer Font box does not use this list."""
    cat = FontCatalog()
    installed = {n.lower(): n for n in _font_families()}
    for name in _PREFERRED_FACES:
        cat.add_type(installed.get(name.lower(), name))
    cat.types = _uniq([t for t in cat.types if t != "default"])
    return cat


def catalog_from_hardware() -> FontCatalog:
    cat = FontCatalog()
    folder = _ROOT / "hardware"
    if not folder.is_dir():
        return cat
    for path in sorted(folder.glob("*.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError, TypeError):
            continue
        items = data if isinstance(data, list) else [data]
        for m in items:
            if not isinstance(m, dict):
                continue
            kind = str(m.get("kind") or "").lower()
            if kind == "font":
                name = m.get("name") or path.stem
                cat.add_type(
                    name,
                    sizes=m.get("sizes") or m.get("size"),
                    styles=m.get("styles"),
                    file=m.get("file") or m.get("path") or m.get("source"),
                )
                _remember_manifest(cat, name, m)
            elif kind == "board":
                for n in m.get("fonts") or []:
                    cat.add_type(n)
    cat.types = _uniq(["default", *[t for t in cat.types if t != "default"]])
    cat.sizes = _uniq(["default", *[s for s in cat.sizes if s != "default"]])
    return cat


def type_items(cat: FontCatalog, current: Any) -> list[tuple[str, str]]:
    """Font box rows. Names from the catalog only; a saved unknown name is marked missing."""
    current_name = _norm_type(current)
    items = [("Default" if name == "default" else str(name), name) for name in cat.types]
    if current_name not in cat.types:
        items.append((f"{current_name} (missing)", current_name))
    return items


def size_items(cat: FontCatalog, font_type: Any) -> list[tuple[str, object]]:
    """Font size box rows for the chosen face."""
    return [
        ("Default" if size == "default" else str(size), size)
        for size in cat.sizes_for(font_type)
    ]


def missing_font_names(design_data: dict[str, Any] | None) -> list[str]:
    """Font names saved on widgets that are not in target.fonts."""
    data = design_data if isinstance(design_data, dict) else {}
    cat = load_font_catalog(data)
    found: list[str] = []
    seen: set[str] = set()
    for screen in data.get("screens") or []:
        if not isinstance(screen, dict):
            continue
        for widget in screen.get("widgets") or []:
            if not isinstance(widget, dict) or "font_type" not in widget:
                continue
            name = _norm_type(widget.get("font_type"))
            if cat.has_type(name) or name in seen:
                continue
            seen.add(name)
            found.append(name)
    return found


def load_font_catalog(design_data: dict[str, Any] | None = None) -> FontCatalog:
    """Names, sizes, and styles from design["target"]["fonts"]. Default stays first."""
    target = (design_data or {}).get("target") if isinstance(design_data, dict) else None
    cat = catalog_from_target(target if isinstance(target, dict) else None)
    if "default" not in cat.styles_by_type:
        cat.styles_by_type["default"] = ["bold", "italic"]
    cat.types = _uniq(["default", *[t for t in cat.types if t != "default"]])
    cat.sizes = _uniq(["default", *[s for s in cat.sizes if s != "default"]])
    cat.register_files()
    return cat
