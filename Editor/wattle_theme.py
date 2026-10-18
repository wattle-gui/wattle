"""The Editor's look.

Dark and light studio colours, orange button hover, one saved choice.
"""

from __future__ import annotations

import json
from pathlib import Path

INK = "#1a2430"
HEADER = "#0c1620"
ACCENT = "#0ea5c9"
ACCENT_HOVER = "#0b8eac"
ACCENT_INK = "#0a6f94"
PAGE = "#c5d8e0"
PANEL = "#f4fbfd"
PAPER = "#ffffff"
LINE = "#8ec5d4"
MUTED = "#3d5a68"
ERR = "#a11"
HELP_BG = "#fff8e8"
FORM_BG = "#f4fbfd"

# Dark studio (Hub + Form Editor)
STUDIO_BG = "#12262d"
STUDIO_TEXT = "#e7f2f6"
STUDIO_MUTED = "#8aa3ad"
STUDIO_FIELD = "#0f2128"
STUDIO_LINE = "#1e4552"
STUDIO_TITLE = "#f0f6f5"
STUDIO_HOVER = "#16343c"
STUDIO_HEADER = "#152c34"
STUDIO_CANVAS = "#0b1a20"
STUDIO_BTN_INK = "#042028"
STUDIO_ERR = "#ff8a8a"
ORANGE = "#f08a24"
ORANGE_INK = "#3a1d00"

_THEME_FILE = Path(__file__).resolve().parent / "ui_theme.json"


def is_dark() -> bool:
    try:
        data = json.loads(_THEME_FILE.read_text(encoding="utf-8"))
        return bool(data.get("dark", True))
    except Exception:
        return True


def set_dark(dark: bool) -> None:
    try:
        _THEME_FILE.write_text(
            json.dumps({"dark": bool(dark)}) + "\n", encoding="utf-8"
        )
    except Exception:
        pass


def studio_colors(*, dark: bool | None = None) -> dict[str, str]:
    if dark is None:
        dark = is_dark()
    if dark:
        return {
            "bg": STUDIO_BG,
            "text": STUDIO_TEXT,
            "muted": STUDIO_MUTED,
            "field": STUDIO_FIELD,
            "line": STUDIO_LINE,
            "title": STUDIO_TITLE,
            "err": STUDIO_ERR,
            "btn_ink": STUDIO_BTN_INK,
            "hover_fill": STUDIO_HOVER,
            "header": STUDIO_HEADER,
            "canvas": STUDIO_CANVAS,
            "dots": "#24505c",
        }
    return {
        "bg": "#e8f2f6",
        "text": INK,
        "muted": MUTED,
        "field": "#ffffff",
        "line": LINE,
        "title": INK,
        "err": ERR,
        "btn_ink": "#042028",
        "hover_fill": "#d4eef6",
        "header": "#f4fbfd",
        "canvas": "#d5e6ec",
        "dots": "#8ec5d4",
    }


def make_theme_toggle(on_changed) -> object:
    """Sun / moon control. *on_changed* receives True for dark."""
    from PyQt6.QtCore import Qt
    from PyQt6.QtWidgets import QFrame, QHBoxLayout, QToolButton

    wrap = QFrame()
    wrap.setObjectName("themeToggle")
    lay = QHBoxLayout(wrap)
    lay.setContentsMargins(4, 3, 4, 3)
    lay.setSpacing(2)
    sun = QToolButton()
    sun.setObjectName("themeSun")
    sun.setText("Light")
    sun.setCheckable(True)
    sun.setCursor(Qt.CursorShape.PointingHandCursor)
    sun.setToolTip("Light look")
    moon = QToolButton()
    moon.setObjectName("themeMoon")
    moon.setText("Dark")
    moon.setCheckable(True)
    moon.setCursor(Qt.CursorShape.PointingHandCursor)
    moon.setToolTip("Dark look")
    wrap._sun = sun
    wrap._moon = moon

    def _apply_checks(dark: bool) -> None:
        sun.blockSignals(True)
        moon.blockSignals(True)
        sun.setChecked(not dark)
        moon.setChecked(dark)
        sun.blockSignals(False)
        moon.blockSignals(False)

    def _set(dark: bool) -> None:
        set_dark(dark)
        _apply_checks(dark)
        on_changed(dark)

    sun.clicked.connect(lambda: _set(False))
    moon.clicked.connect(lambda: _set(True))
    lay.addWidget(sun)
    lay.addWidget(moon)
    _apply_checks(is_dark())
    wrap.sync_from_store = lambda: _apply_checks(is_dark())
    return wrap


def make_studio_tool_strip(
    parent,
    *,
    current: str,
    on_form,
    on_code,
    on_this,
    on_other,
):
    """Four tool buttons that replace the Tools menu (active one is highlighted)."""
    from PyQt6.QtCore import Qt
    from PyQt6.QtWidgets import QButtonGroup, QHBoxLayout, QPushButton, QSizePolicy, QWidget

    host = QWidget(parent)
    host.setObjectName("toolStrip")
    host.setSizePolicy(QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Fixed)
    lay = QHBoxLayout(host)
    lay.setContentsMargins(6, 4, 6, 4)
    lay.setSpacing(6)

    specs = (
        ("form", "Form Editor", "Design the Form", on_form),
        ("code", "Code Editor", "Write CODE.py", on_code),
        ("this_device", "This Device", "Run on this device", on_this),
        ("other_device", "Other Device", "Run on a phone or tablet", on_other),
    )
    buttons: dict = {}
    editors = QButtonGroup(host)
    editors.setExclusive(True)
    for key, label, tip, slot in specs:
        btn = QPushButton(label, host)
        btn.setObjectName("toolTab")
        btn.setCheckable(True)
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        btn.setToolTip(tip)
        btn.clicked.connect(slot)
        lay.addWidget(btn)
        buttons[key] = btn
        if key in ("form", "code"):
            editors.addButton(btn)
    host.buttons = buttons
    set_studio_tool_active(host, editor=current)
    return host


def set_studio_tool_active(
    strip,
    *,
    editor: str | None = None,
    this_device: bool | None = None,
    other_device: bool | None = None,
) -> None:
    buttons = getattr(strip, "buttons", None) or {}
    if editor in buttons:
        for key in ("form", "code"):
            btn = buttons.get(key)
            if btn is not None:
                btn.blockSignals(True)
                btn.setChecked(key == editor)
                btn.blockSignals(False)
    if this_device is not None and "this_device" in buttons:
        buttons["this_device"].blockSignals(True)
        buttons["this_device"].setChecked(bool(this_device))
        buttons["this_device"].blockSignals(False)
    if other_device is not None and "other_device" in buttons:
        buttons["other_device"].blockSignals(True)
        buttons["other_device"].setChecked(bool(other_device))
        buttons["other_device"].blockSignals(False)

APP_QSS = f"""
QMainWindow, QDialog, QWidget {{
  background: {PAGE};
  color: {INK};
}}
QMenuBar {{
  background: {HEADER};
  color: #fff;
  border-bottom: 3px solid {ACCENT};
  padding: 2px;
}}
QMenuBar::item {{
  color: #fff;
  padding: 4px 10px;
}}
QMenuBar::item:selected {{
  background: {ACCENT};
  color: #fff;
}}
QMenu {{
  background: {PAPER};
  color: {INK};
  border: 1px solid {LINE};
  padding: 4px 0px;
}}
QMenu::item {{
  background: transparent;
  padding: 6px 18px;
}}
QMenu::item:selected {{
  background: {ACCENT};
  color: #fff;
}}
QMenu::separator {{
  height: 1px;
  margin: 6px 10px;
  background: {MUTED};
  border: none;
}}
QToolBar {{
  background: {PANEL};
  border-bottom: 1px solid {LINE};
  spacing: 4px;
  padding: 3px;
}}
QStatusBar {{
  background: {PANEL};
  color: {MUTED};
  border-top: 1px solid {LINE};
}}
QLineEdit, QPlainTextEdit, QSpinBox, QComboBox,
QListWidget, QTreeWidget, QTableWidget {{
  background: {PAPER};
  color: {INK};
  border: 2px solid {INK};
  padding: 3px 6px;
  selection-background-color: {ACCENT};
  selection-color: #fff;
}}
QComboBox::drop-down {{
  border: none;
  width: 22px;
}}
QPushButton {{
  background: {PAPER};
  color: {INK};
  border: 2px solid {INK};
  padding: 4px 12px;
  min-height: 24px;
}}
QPushButton:hover {{
  background: {ORANGE};
  color: {ORANGE_INK};
}}
QToolButton:hover {{
  background: {ORANGE};
  color: {ORANGE_INK};
}}
QPushButton:pressed {{
  background: #d4eef6;
}}
QPushButton#primary, QPushButton#menuBtn {{
  background: {ACCENT};
  color: #fff;
  border: 2px solid {ACCENT_INK};
  font-weight: 700;
  min-height: 28px;
}}
QPushButton#primary:hover, QPushButton#menuBtn:hover {{
  background: {ORANGE};
  color: {ORANGE_INK};
}}
QPushButton#primary:pressed, QPushButton#menuBtn:pressed {{
  background: {ACCENT_INK};
}}
QLabel#title {{
  background: {HEADER};
  color: #fff;
  font-weight: 700;
  font-size: 14px;
  padding: 10px 12px 8px;
  border-bottom: 3px solid {ACCENT};
}}
QLabel#panelCaption {{
  background: {HEADER};
  color: #fff;
  font-weight: 700;
  padding: 6px 10px;
  border-bottom: 3px solid {ACCENT};
}}
QLabel#hint {{
  color: {MUTED};
}}
QLabel#err {{
  color: {ERR};
}}
QLabel#sectionBold {{
  font-weight: 700;
  color: {ACCENT_INK};
}}
QGroupBox {{
  font-weight: 700;
  color: {ACCENT_INK};
  border: 1px solid {LINE};
  background: {PANEL};
  margin-top: 10px;
  padding: 8px 8px 6px;
}}
QGroupBox::title {{
  subcontrol-origin: margin;
  left: 8px;
  padding: 0 4px;
}}
QHeaderView::section {{
  background: {PANEL};
  color: {ACCENT_INK};
  border: 1px solid {LINE};
  padding: 4px 6px;
  font-weight: 700;
}}
QTabWidget::pane {{
  border: 1px solid {LINE};
  background: {PANEL};
}}
QTabBar::tab {{
  background: {PANEL};
  color: {INK};
  border: 1px solid {LINE};
  padding: 6px 12px;
  margin-right: 2px;
}}
QTabBar::tab:selected {{
  background: {PAPER};
  color: {ACCENT_INK};
  font-weight: 700;
}}
QFrame#paletteFrame, QFrame#inspFrame {{
  border: 1px solid {LINE};
  background: {PANEL};
}}
QCheckBox {{
  spacing: 6px;
}}
QTreeWidget#paletteTree::item {{
  padding: 2px 2px;
  min-height: 20px;
}}
QTreeWidget#paletteTree::item:hover,
QTreeView#paletteTree::item:hover {{
  background: {ACCENT};
  color: #fff;
}}
"""


def hub_qss(*, dark: bool) -> str:
    """Stylesheet for the Hub window only (not Form / Code Editor)."""
    c = studio_colors(dark=dark)
    bg = c["bg"]
    text = c["text"]
    muted = c["muted"]
    field = c["field"]
    line = c["line"]
    title = c["title"]
    err = c["err"]
    btn_ink = c["btn_ink"]
    hover_fill = c["hover_fill"]
    header_bg = c["header"]
    return f"""
QMainWindow, QStackedWidget, QStackedWidget > QWidget {{
  background: {bg};
}}
QWidget {{
  background: {bg};
  color: {text};
}}
QLabel {{
  background: transparent;
}}
QScrollArea {{
  border: none;
  background: {bg};
}}
QScrollArea > QWidget > QWidget {{
  background: {bg};
}}
QLabel#hubEyebrow {{
  color: {ACCENT};
  font-weight: 700;
  font-size: 11px;
}}
QLabel#hubTitle {{
  color: {title};
  font-weight: 700;
  font-size: 22px;
  padding: 0;
  background: transparent;
  border: none;
}}
QLabel#hubSub {{
  color: {muted};
  font-size: 13px;
  background: transparent;
  border: none;
}}
QLabel#fieldLabel {{
  color: {text};
  font-weight: 600;
  font-size: 13px;
}}
QLabel#sectionLabel {{
  color: {ACCENT};
  font-weight: 700;
  font-size: 12px;
}}
QLabel#hint {{
  color: {muted};
}}
QLabel#err {{
  color: {err};
}}
QLabel#sectionBold {{
  font-weight: 700;
  color: {ACCENT};
}}
QFrame#inputWrap {{
  background: {field};
  border: 1px solid {line};
  border-radius: 10px;
}}
QFrame#themeToggle {{
  background: {field};
  border: 1px solid {line};
  border-radius: 18px;
}}
QWidget#cellWrap {{
  background: transparent;
}}
QToolButton {{
  background: transparent;
  color: {muted};
  border: none;
  padding: 4px 8px;
  border-radius: 12px;
}}
QToolButton:hover {{
  background: {ORANGE};
  color: {ORANGE_INK};
}}
QToolButton#themeSun:hover, QToolButton#themeMoon:hover {{
  background: transparent;
  color: {title};
}}
QToolButton#themeSun:checked, QToolButton#themeMoon:checked {{
  background: {ACCENT};
  color: {btn_ink};
}}
QToolButton#themeSun:checked:hover, QToolButton#themeMoon:checked:hover {{
  background: {ACCENT};
  color: {btn_ink};
}}
QToolButton#eyeBtn {{
  color: {muted};
  padding: 4px 6px;
}}
QLineEdit {{
  background: {field};
  color: {title};
  border: 1px solid {line};
  border-radius: 10px;
  padding: 8px 12px;
  min-height: 28px;
  selection-background-color: {ACCENT};
  selection-color: #fff;
}}
QLineEdit:focus {{
  border: 1px solid {ACCENT};
}}
QLineEdit#innerEdit {{
  background: transparent;
  border: none;
  padding: 8px 8px;
  min-height: 28px;
  qproperty-alignment: AlignCenter;
}}
QLineEdit#cellEdit {{
  background: {bg};
  color: {title};
  border: 1px solid {line};
  border-radius: 8px;
  padding: 4px 8px;
  min-height: 22px;
}}
QListWidget, QTableWidget {{
  background: {field};
  color: {title};
  border: 1px solid {line};
  border-radius: 12px;
  gridline-color: {line};
  outline: none;
  selection-background-color: {hover_fill};
  selection-color: {title};
}}
QTableWidget::item {{
  padding: 4px 8px;
  color: {title};
}}
QHeaderView::section {{
  background: {header_bg};
  color: {muted};
  border: none;
  border-bottom: 1px solid {line};
  padding: 8px 8px;
  font-weight: 700;
}}
QTableCornerButton::section {{
  background: {header_bg};
  border: none;
}}
QPushButton {{
  background: transparent;
  color: {muted};
  border: none;
  padding: 8px 14px;
  min-height: 32px;
  border-radius: 16px;
}}
QPushButton:hover {{
  color: {ORANGE_INK};
  background: {ORANGE};
}}
QPushButton:pressed {{
  background: {line};
}}
QPushButton#primary, QPushButton#menuBtn {{
  background: {ACCENT};
  color: {btn_ink};
  border: none;
  font-weight: 700;
  min-height: 34px;
  padding: 8px 18px;
  border-radius: 16px;
}}
QPushButton#primary:hover, QPushButton#menuBtn:hover {{
  background: {ORANGE};
  color: {ORANGE_INK};
}}
QPushButton#primary:pressed, QPushButton#menuBtn:pressed {{
  background: {ACCENT_INK};
  color: #fff;
}}
QPushButton#menuBtn {{
  text-align: left;
  padding-left: 16px;
}}
QListWidget#projectList {{
  background: {field};
  border: 1px solid {line};
  border-radius: 12px;
  outline: none;
}}
QListWidget#projectList::item {{
  background: transparent;
  color: {title};
  border: none;
  padding: 2px 0;
  min-height: 32px;
}}
QCheckBox {{
  color: {text};
  spacing: 6px;
}}
QCheckBox::indicator {{
  width: 16px;
  height: 16px;
  border: 1px solid {line};
  border-radius: 3px;
  background: {field};
}}
QCheckBox::indicator:checked {{
  background: {ACCENT};
  border-color: {ACCENT};
}}
QScrollBar:vertical {{
  background: {bg};
  width: 10px;
  border: none;
}}
QScrollBar::handle:vertical {{
  background: {line};
  border-radius: 4px;
  min-height: 24px;
}}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
  height: 0;
}}
"""


def editor_qss(*, dark: bool | None = None) -> str:
    """Form Editor / Code Editor chrome — same colours as the Hub."""
    c = studio_colors(dark=dark)
    bg = c["bg"]
    text = c["text"]
    muted = c["muted"]
    field = c["field"]
    line = c["line"]
    title = c["title"]
    hover = c["hover_fill"]
    header = c["header"]
    canvas = c["canvas"]
    btn_ink = c["btn_ink"]
    return f"""
QMainWindow {{
  background: {bg};
  color: {text};
}}
QWidget {{
  background: {bg};
  color: {text};
}}
QLabel {{
  background: transparent;
  color: {text};
}}
QMenuBar {{
  background: {header};
  color: {title};
  border-bottom: 1px solid {line};
  padding: 4px 6px;
}}
QMenuBar::item {{
  color: {title};
  padding: 6px 10px;
  border-radius: 6px;
}}
QMenuBar::item:selected {{
  background: {ACCENT};
  color: {btn_ink};
}}
QMenu {{
  background: {header};
  color: {title};
  border: 1px solid {line};
  padding: 4px 0px;
}}
QMenu::item {{
  background: transparent;
  padding: 6px 18px;
}}
QMenu::item:selected,
QMenu::item:hover {{
  background: {ACCENT};
  color: {btn_ink};
}}
QMenu::separator {{
  height: 1px;
  margin: 6px 10px;
  background: {muted};
  border: none;
}}
QToolBar {{
  background: {header};
  color: {text};
  border: none;
  border-bottom: 1px solid {line};
  spacing: 6px;
  padding: 4px 8px;
}}
QToolBar#toolsBar {{
  background: {header};
  border-bottom: 1px solid {line};
  spacing: 8px;
  padding: 4px 8px;
  min-height: 36px;
}}
QStatusBar {{
  background: {header};
  color: {muted};
  border-top: 1px solid {line};
}}
QSplitter::handle {{
  background: {bg};
  width: 8px;
}}
QWidget#canvasBoard {{
  background: transparent;
}}
QScrollArea#formBoard, QScrollArea#formBoard > QWidget {{
  background: transparent;
}}
QFrame#paletteFrame, QFrame#inspFrame {{
  background: {header};
  border: none;
  border-right: 1px solid {line};
}}
QFrame#inspFrame {{
  border-right: none;
  border-left: 1px solid {line};
}}
QLabel#panelCaption {{
  background: transparent;
  color: {ACCENT};
  font-weight: 700;
  font-size: 11px;
  padding: 12px 12px 6px;
  border: none;
}}
QLabel#sectionLabel {{
  color: {ACCENT};
  font-weight: 700;
  font-size: 11px;
  padding: 6px 10px 2px;
}}
QLabel#hint, QLabel#zoomLabel {{
  color: {muted};
}}
QLineEdit, QPlainTextEdit, QSpinBox, QComboBox,
QListWidget, QTreeWidget, QTableWidget {{
  background: {field};
  color: {title};
  border: 1px solid {line};
  border-radius: 8px;
  padding: 4px 8px;
  selection-background-color: {ACCENT};
  selection-color: #fff;
}}
QLineEdit:focus, QSpinBox:focus, QComboBox:focus, QPlainTextEdit:focus {{
  border: 1px solid {ACCENT};
}}
QComboBox::drop-down {{
  border: none;
  width: 22px;
}}
QComboBox QAbstractItemView {{
  background: {field};
  color: {title};
  border: 1px solid {line};
  selection-background-color: {ACCENT};
}}
QSpinBox {{
  padding-right: 18px;
}}
QPushButton {{
  background: {hover};
  color: {title};
  border: 1px solid {line};
  padding: 4px 12px;
  min-height: 24px;
  border-radius: 12px;
}}
QPushButton:hover {{
  background: {ORANGE};
  color: {ORANGE_INK};
}}
QPushButton:pressed {{
  background: {ACCENT_INK};
}}
QPushButton#primary, QPushButton#menuBtn {{
  background: {ACCENT};
  color: {btn_ink};
  border: none;
  font-weight: 700;
  min-height: 26px;
  padding: 6px 14px;
  border-radius: 14px;
}}
QPushButton#primary:hover, QPushButton#menuBtn:hover {{
  background: {ORANGE};
  color: {ORANGE_INK};
}}
QWidget#toolStrip {{
  background: transparent;
}}
QPushButton#toolTab {{
  background: {field};
  color: {title};
  border: 1px solid {line};
  border-radius: 8px;
  padding: 4px 12px;
  min-height: 26px;
  min-width: 88px;
  font-weight: 600;
}}
QPushButton#toolTab:hover {{
  background: {ORANGE};
  color: {ORANGE_INK};
  border-color: {ORANGE};
}}
QPushButton#toolTab:checked {{
  background: {ACCENT};
  color: {btn_ink};
  border-color: {ACCENT};
  font-weight: 700;
}}
QPushButton#toolTab:checked:hover {{
  background: {ACCENT};
  color: {btn_ink};
}}
QTabWidget::pane {{
  border: none;
  background: {header};
  top: 0px;
}}
QTabBar {{
  background: {header};
}}
QTabBar::tab {{
  background: {header};
  color: {muted};
  border: none;
  padding: 8px 14px;
  margin-right: 2px;
  min-height: 22px;
}}
QTabBar::tab:hover {{
  color: {title};
}}
QTabBar::tab:selected {{
  color: {ACCENT};
  font-weight: 700;
  border-bottom: 2px solid {ACCENT};
}}
QHeaderView::section {{
  background: {header};
  color: {muted};
  border: none;
  border-bottom: 1px solid {line};
  padding: 4px 6px;
  font-weight: 700;
}}
QTreeWidget, QListWidget {{
  background: {header};
  border: none;
  border-radius: 0;
  outline: none;
}}
QTreeWidget#paletteTree::item {{
  background: transparent;
  border: none;
  padding: 0;
  min-height: 18px;
  color: {text};
}}
QTreeWidget#paletteTree::item:hover,
QTreeView#paletteTree::item:hover,
QTreeWidget#paletteTree::item:selected,
QTreeView#paletteTree::item:selected {{
  background: transparent;
  color: {title};
}}
QFrame#propRow {{
  background: {field};
  border: 1px solid {line};
  border-radius: 10px;
}}
QListWidget#eventList {{
  background: {header};
  border: none;
  padding: 2px;
  outline: none;
}}
QListWidget#eventList::item {{
  background: {field};
  color: {title};
  border: 1px solid {line};
  border-radius: 8px;
  margin: 2px 1px;
  padding: 4px 6px 4px 2px;
  min-height: 22px;
}}
QListWidget#eventList::item:selected {{
  background: {hover};
  border: 1px solid {ACCENT};
}}
QListWidget#eventList::indicator {{
  width: 16px;
  height: 16px;
  margin-left: 4px;
  margin-right: 8px;
  border: 1px solid {line};
  border-radius: 3px;
  background: #ffffff;
}}
QListWidget#eventList::indicator:checked {{
  background: {ACCENT};
  border-color: {ACCENT};
}}
QCheckBox {{
  color: {text};
  spacing: 6px;
}}
QCheckBox::indicator {{
  width: 14px;
  height: 14px;
  border: 1px solid {line};
  border-radius: 3px;
  background: {field};
}}
QCheckBox::indicator:checked {{
  background: {ACCENT};
  border-color: {ACCENT};
}}
QPlainTextEdit#helpBox {{
  background: {field};
  color: {muted};
  border: 1px solid {line};
  border-radius: 10px;
  padding: 8px;
}}
QScrollArea {{
  border: none;
  background: {canvas};
}}
QScrollBar:vertical, QScrollBar:horizontal {{
  background: {bg};
  width: 10px;
  height: 10px;
  border: none;
}}
QScrollBar::handle:vertical, QScrollBar::handle:horizontal {{
  background: {line};
  border-radius: 4px;
  min-height: 24px;
  min-width: 24px;
}}
QScrollBar::add-line, QScrollBar::sub-line {{
  width: 0;
  height: 0;
}}
QFrame#themeToggle {{
  background: {field};
  border: 1px solid {line};
  border-radius: 18px;
}}
QToolButton {{
  background: transparent;
  color: {muted};
  border: none;
}}
QToolButton:hover {{
  background: {ORANGE};
  color: {ORANGE_INK};
  border-radius: 8px;
}}
QToolButton#themeSun:hover, QToolButton#themeMoon:hover {{
  background: transparent;
  color: {title};
}}
QToolButton#themeSun:checked, QToolButton#themeMoon:checked {{
  background: {ACCENT};
  color: {btn_ink};
  border-radius: 12px;
}}
QToolButton#themeSun:checked:hover, QToolButton#themeMoon:checked:hover {{
  background: {ACCENT};
  color: {btn_ink};
}}
"""


def ui_font():
    from PyQt6.QtGui import QFont

    for name in ("Segoe UI", "Ubuntu", "Noto Sans", "DejaVu Sans"):
        font = QFont(name)
        if font.exactMatch():
            font.setPixelSize(13)
            return font
    font = QFont()
    font.setPixelSize(13)
    return font


def apply_theme(app) -> None:
    """Font + stylesheet on the QApplication (covers dialogs too)."""
    app.setFont(ui_font())
    app.setStyleSheet(hub_qss(dark=is_dark()))
