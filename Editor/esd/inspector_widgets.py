"""Object Inspector controls that avoid native QComboBox popups.

This desktop segfaults when Qt paints some combo/arrow glyphs, and also when a
QComboBox is destroyed while its popup is still open (Screen Orientation).
"""

from __future__ import annotations

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QButtonGroup,
    QDialog,
    QDoubleSpinBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from wattle_theme import ACCENT, ORANGE, ORANGE_INK, studio_colors

ROW_H = 22


def choice_label(raw) -> str:
    text = str(raw or "").replace("_", " ").strip()
    return text[:1].upper() + text[1:] if text else ""


class ChoiceRow(QWidget):
    """Exclusive text buttons: Landscape/Portrait, Left/Center/Right, On/Off."""

    changed = pyqtSignal(object)

    def __init__(self, items: list[tuple[str, object]], value=None, parent=None) -> None:
        super().__init__(parent)
        self.setFixedHeight(ROW_H)
        self._items = list(items)
        self._value = value
        self._suspend = False
        bar = QFrame(self)
        bar.setObjectName("inspChoiceBar")
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.addWidget(bar)
        inner = QHBoxLayout(bar)
        inner.setContentsMargins(0, 0, 0, 0)
        inner.setSpacing(0)
        self._group = QButtonGroup(self)
        self._group.setExclusive(True)
        self._buttons: list[QPushButton] = []
        colors = studio_colors()
        n = len(self._items)
        for i, (label, data) in enumerate(self._items):
            btn = QPushButton(label)
            btn.setObjectName("inspChoice")
            btn.setCheckable(True)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
            btn.setFixedHeight(ROW_H)
            btn.setProperty("choiceData", data)
            left = 8 if i == 0 else 0
            right = 8 if i == n - 1 else 0
            btn.setStyleSheet(
                f"""
                QPushButton#inspChoice {{
                  background: {colors['field']};
                  color: {colors['title']};
                  border: none;
                  border-right: {0 if i == n - 1 else 1}px solid {colors['line']};
                  border-top-left-radius: {left}px;
                  border-bottom-left-radius: {left}px;
                  border-top-right-radius: {right}px;
                  border-bottom-right-radius: {right}px;
                  padding: 0 10px;
                  min-height: {ROW_H - 2}px;
                  max-height: {ROW_H}px;
                  font-size: 12px;
                }}
                QPushButton#inspChoice:checked {{
                  background: {ACCENT};
                  color: #042028;
                  font-weight: 700;
                }}
                QPushButton#inspChoice:hover {{
                  background: {ORANGE};
                  color: {ORANGE_INK};
                }}
                QPushButton#inspChoice:checked:hover {{
                  background: {ACCENT};
                  color: #042028;
                }}
                QPushButton#inspChoice:disabled,
                QPushButton#inspChoice:disabled:checked,
                QPushButton#inspChoice:disabled:hover {{
                  background: {colors['field']};
                  color: {colors['muted']};
                  font-weight: 400;
                }}
                """
            )
            self._group.addButton(btn, i)
            inner.addWidget(btn, 1)
            self._buttons.append(btn)
        bar.setStyleSheet(
            f"QFrame#inspChoiceBar {{ background: {colors['field']}; "
            f"border: 1px solid {colors['line']}; border-radius: 8px; }}"
        )
        self._group.buttonClicked.connect(self._on_btn)
        self.set_value(value)

    def _on_btn(self, btn: QPushButton) -> None:
        if self._suspend:
            return
        try:
            index = self._buttons.index(btn)
        except ValueError:
            return
        _label, data = self._items[index]
        if data == self._value:
            return
        self._value = data
        self.changed.emit(data)

    def value(self):
        return self._value

    def set_value(self, value) -> None:
        self._value = value
        self._suspend = True
        matched = False
        for i, (_label, data) in enumerate(self._items):
            on = data == value
            self._buttons[i].setChecked(on)
            if on:
                matched = True
        if not matched and self._buttons:
            self._buttons[0].setChecked(True)
            self._value = self._items[0][1]
        self._suspend = False


class PickRow(QWidget):
    """Current value plus a list dialog. Avoids QComboBox on this desktop."""

    changed = pyqtSignal(object)

    def __init__(self, items: list[tuple[str, object]], value=None, parent=None) -> None:
        super().__init__(parent)
        self.setFixedHeight(ROW_H)
        self._items = list(items) or [("Default", "default")]
        self._value = value
        self._btn = QPushButton(self._label_for(value))
        self._btn.setObjectName("inspChoice")
        self._btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self._btn.setFixedHeight(ROW_H)
        colors = studio_colors()
        self._btn.setStyleSheet(
            f"""
            QPushButton#inspChoice {{
              background: {colors['field']};
              color: {colors['title']};
              border: 1px solid {colors['line']};
              border-radius: 8px;
              padding: 0 10px;
              min-height: {ROW_H - 2}px;
              max-height: {ROW_H}px;
              font-size: 12px;
              text-align: left;
            }}
            QPushButton#inspChoice:hover {{
              background: {ORANGE};
              color: {ORANGE_INK};
            }}
            """
        )
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.addWidget(self._btn)
        self._btn.clicked.connect(self._open)
        self.set_value(value)

    def _label_for(self, value) -> str:
        for label, data in self._items:
            if data == value or str(data) == str(value):
                return label
        if value is None or str(value).strip() == "":
            return self._items[0][0]
        return str(value)

    def value(self):
        return self._value

    def set_value(self, value) -> None:
        self._value = value
        self._btn.setText(self._label_for(value))

    def _open(self) -> None:
        dlg = QDialog(self.window())
        dlg.setWindowTitle("Choose")
        dlg.setModal(True)
        longest = max((len(str(label)) for label, _ in self._items), default=8)
        dlg.resize(
            min(420, max(240, longest * 8 + 48)),
            min(420, 28 * max(3, min(len(self._items), 14)) + 24),
        )
        outer = QVBoxLayout(dlg)
        outer.setContentsMargins(8, 8, 8, 8)
        outer.setSpacing(4)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        host = QWidget()
        col = QVBoxLayout(host)
        col.setContentsMargins(0, 0, 0, 0)
        col.setSpacing(2)
        colors = studio_colors()
        for label, data in self._items:
            btn = QPushButton(label)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
            btn.setFixedHeight(ROW_H)
            on = data == self._value or str(data) == str(self._value)
            bg = ACCENT if on else colors["field"]
            fg = "#042028" if on else colors["title"]
            btn.setStyleSheet(
                f"background:{bg}; color:{fg}; border:1px solid {colors['line']};"
                f" border-radius:6px; padding:0 8px; font-size:12px;"
            )
            btn.clicked.connect(lambda _=False, v=data: self._pick(dlg, v))
            col.addWidget(btn)
        col.addStretch(1)
        scroll.setWidget(host)
        outer.addWidget(scroll, 1)
        dlg.exec()

    def _pick(self, dlg: QDialog, value) -> None:
        dlg.accept()
        if value == self._value:
            return
        self.set_value(value)
        self.changed.emit(value)


def parse_json_number(text: str) -> int | float | None:
    """Read a number the way JSON would. 640 stays an int; 3.5 stays a float."""
    raw = str(text or "").strip()
    if not raw:
        return None
    try:
        if any(ch in raw for ch in ".eE"):
            value = float(raw)
        else:
            value = int(raw, 10)
    except ValueError:
        return None
    if isinstance(value, float) and (value != value or value in (float("inf"), float("-inf"))):
        return None
    return value


def format_json_number(value: object) -> str:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return "" if value is None else str(value)
    if isinstance(value, float):
        if value.is_integer() and abs(value) < 1e12:
            return str(int(value))
        return f"{value:.6f}".rstrip("0").rstrip(".")
    return str(value)


class JsonNumberBox(QDoubleSpinBox):
    """Number box that shows whole numbers without a decimal point."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setDecimals(6)
        self.setRange(-1_000_000, 1_000_000)
        self.setSingleStep(1)

    def textFromValue(self, value: float) -> str:  # noqa: N802
        return format_json_number(value)

    def valueFromText(self, text: str) -> float:  # noqa: N802
        parsed = parse_json_number(text)
        if parsed is None:
            return 0.0
        return float(parsed)

    def json_value(self) -> int | float:
        parsed = parse_json_number(self.text())
        if parsed is not None:
            return parsed
        value = float(self.value())
        nearest = round(value)
        if abs(value - nearest) < 1e-7:
            return int(nearest)
        return value


class EntryListEditor(QWidget):
    """Add, delete, and edit a short list of strings or numbers."""

    changed = pyqtSignal(list)
    refused = pyqtSignal(str)

    def __init__(self, entries: list, *, numeric: bool, parent=None) -> None:
        super().__init__(parent)
        self._numeric = bool(numeric)
        self._items: list = list(entries or [])
        self._limit_fn = None
        self._block = False
        self._dirty = False
        self._adding = False
        colors = studio_colors()
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(4)
        self._edit = QLineEdit()
        self._edit.setFixedHeight(ROW_H)
        self._edit.setPlaceholderText(
            "Type a number, then Add" if self._numeric else "Type the text, then Add"
        )
        self._edit.setStyleSheet(
            f"QLineEdit {{ background:{colors['field']}; color:{colors['title']}; "
            f"border:1px solid {colors['line']}; min-height:{ROW_H - 4}px; "
            f"max-height:{ROW_H}px; padding:0 4px; }}"
        )
        self._list = QListWidget()
        self._list.setObjectName("entryList")
        self._list.setFixedHeight(64)
        self._list.setStyleSheet(
            f"QFrame#esdPanel QListWidget#entryList {{ background:{colors['field']}; color:{colors['title']}; "
            f"border:1px solid {colors['line']}; padding:0px; }}"
        )
        self._add_btn = QPushButton("Add entry")
        self._del_btn = QPushButton("Delete selected")
        for btn in (self._add_btn, self._del_btn):
            btn.setFixedHeight(ROW_H)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
            btn.setStyleSheet(
                f"QPushButton {{ background:{colors['field']}; color:{colors['title']}; "
                f"border:1px solid {colors['line']}; border-radius:8px; padding:0 8px; "
                f"min-height:{ROW_H - 4}px; max-height:{ROW_H}px; }}"
                f"QPushButton:hover {{ background:{ORANGE}; color:{ORANGE_INK}; }}"
            )
        entry_row = QHBoxLayout()
        entry_row.setContentsMargins(0, 0, 0, 0)
        entry_row.setSpacing(4)
        entry_row.addWidget(self._edit, 1)
        entry_row.addWidget(self._add_btn)
        lay.addLayout(entry_row)
        lay.addWidget(self._list)
        lay.addWidget(self._del_btn)
        self._reload()
        self._list.currentRowChanged.connect(self._show_row)
        self._edit.textChanged.connect(self._mark_dirty)
        self._edit.returnPressed.connect(self._add_from_return)
        self._edit.editingFinished.connect(self._commit_edit)
        self._add_btn.clicked.connect(self._add)
        self._del_btn.clicked.connect(self._delete)

    def set_limit(self, limit_fn) -> None:
        """limit_fn() is the most entries Add will allow."""
        self._limit_fn = limit_fn

    def _display(self, item: object) -> str:
        if self._numeric:
            return format_json_number(item)
        text = "" if item is None else str(item)
        return text if text else "(empty)"

    def _raw_text(self, item: object) -> str:
        if self._numeric:
            return format_json_number(item)
        return "" if item is None else str(item)

    def _reload(self) -> None:
        self._block = True
        row = self._list.currentRow()
        self._list.clear()
        for item in self._items:
            self._list.addItem(self._display(item))
        if 0 <= row < len(self._items):
            self._list.setCurrentRow(row)
        self._block = False

    def _mark_dirty(self, _text: str) -> None:
        if not self._block:
            self._dirty = True

    def _add_from_return(self) -> None:
        """Enter adds a new entry. editingFinished follows on the same keypress."""
        self._adding = True
        self._add()

    def _parsed_field(self):
        text = self._edit.text()
        if self._numeric:
            return parse_json_number(text)
        return text

    def _show_row(self, row: int) -> None:
        if self._block:
            return
        self._block = True
        if row < 0 or row >= len(self._items):
            self._edit.clear()
        else:
            self._edit.setText(self._raw_text(self._items[row]))
        self._dirty = False
        self._block = False

    def _commit_edit(self) -> None:
        if self._adding:
            self._adding = False
            return
        # A click on Add moves focus here first. That click is a new entry, not an edit.
        if self._add_btn.underMouse():
            return
        if self._block or not self._dirty:
            return
        row = self._list.currentRow()
        if row < 0 or row >= len(self._items):
            return
        if self._numeric:
            parsed = parse_json_number(self._edit.text())
            if parsed is None:
                self.refused.emit("That entry must be a number.")
                self._show_row(row)
                return
            new = parsed
        else:
            new = self._edit.text()
        if self._items[row] == new:
            self._dirty = False
            return
        self._items[row] = new
        self._dirty = False
        self._block = True
        shown = self._list.item(row)
        if shown is not None:
            shown.setText(self._display(new))
        self._block = False
        self.changed.emit(list(self._items))

    def _at_limit(self) -> int | None:
        if self._limit_fn is None:
            return None
        try:
            return int(self._limit_fn())
        except (TypeError, ValueError):
            return None

    def _add(self) -> None:
        text = self._edit.text()
        if self._numeric:
            parsed = parse_json_number(text)
            if parsed is None:
                self.refused.emit("Type a number, then press Add.")
                return
            new = parsed
        else:
            new = text
        limit = self._at_limit()
        if limit is not None and len(self._items) >= limit:
            self.refused.emit(
                f"This chart has {limit} bars. Extra entries are not added."
            )
            return
        self._items.append(new)
        self._reload()
        self._block = True
        self._list.setCurrentRow(-1)
        self._edit.clear()
        self._dirty = False
        self._block = False
        self._edit.setFocus()
        self.changed.emit(list(self._items))

    def _delete(self) -> None:
        row = self._list.currentRow()
        if row < 0 or row >= len(self._items):
            self.refused.emit("Select an entry to delete.")
            return
        del self._items[row]
        self._reload()
        self._block = True
        self._edit.clear()
        self._dirty = False
        self._block = False
        if self._items:
            self._list.setCurrentRow(min(row, len(self._items) - 1))
        self.changed.emit(list(self._items))


class BarRowsEditor(QWidget):
    """One directly-editable row per bar -- type straight into a bar's own field, no
    separate Add/Delete step.

    Always shows exactly `count_fn()` rows (the barchart's current "Number of bars"), in
    order. If the stored list is longer than that -- usually because the bar count was just
    lowered -- the extra entries are kept, not discarded, and a line says how many are
    waiting out of view.
    """

    changed = pyqtSignal(list)
    refused = pyqtSignal(str)

    def __init__(self, entries: list, *, numeric: bool, count_fn, parent=None) -> None:
        super().__init__(parent)
        self._numeric = bool(numeric)
        self._items: list = list(entries or [])
        self._count_fn = count_fn
        self._block = False
        colors = studio_colors()
        self._field_style = (
            f"QLineEdit {{ background:{colors['field']}; color:{colors['title']}; "
            f"border:1px solid {colors['line']}; min-height:{ROW_H - 4}px; "
            f"max-height:{ROW_H}px; padding:0 4px; }}"
        )
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(2)
        self._rows_box = QVBoxLayout()
        self._rows_box.setSpacing(2)
        lay.addLayout(self._rows_box)
        self._extra_label = QLabel("")
        self._extra_label.setWordWrap(True)
        self._extra_label.setStyleSheet(f"color:{colors['title']}; font-style: italic;")
        lay.addWidget(self._extra_label)
        self._edits: list[QLineEdit] = []
        self._rebuild_rows()

    def _display(self, item: object) -> str:
        if self._numeric:
            return format_json_number(item)
        return "" if item is None else str(item)

    def _count(self) -> int:
        try:
            return max(0, int(self._count_fn()))
        except (TypeError, ValueError):
            return 0

    def _rebuild_rows(self) -> None:
        while self._rows_box.count():
            item = self._rows_box.takeAt(0)
            w = item.widget()
            if w is not None:
                w.setParent(None)
        self._edits = []
        n = self._count()
        for i in range(n):
            value = self._items[i] if i < len(self._items) else (0 if self._numeric else "")
            row = QHBoxLayout()
            row.setSpacing(4)
            num = QLabel(str(i + 1))
            num.setFixedWidth(18)
            num.setStyleSheet(f"color:{studio_colors()['title']};")
            ed = QLineEdit(self._display(value))
            ed.setStyleSheet(self._field_style)
            ed.setFixedHeight(ROW_H)
            ed.editingFinished.connect(lambda i=i, ed=ed: self._commit(i, ed))
            row.addWidget(num)
            row.addWidget(ed, 1)
            self._rows_box.addLayout(row)
            self._edits.append(ed)
        extra = len(self._items) - n
        if extra > 0:
            self._extra_label.setText(
                f"{extra} more {'entry' if extra == 1 else 'entries'} kept but not shown here -- "
                'raise "Number of bars" to see them again.'
            )
        else:
            self._extra_label.setText("")

    def _commit(self, i: int, ed: QLineEdit) -> None:
        if self._block:
            return
        text = ed.text()
        if self._numeric:
            parsed = parse_json_number(text)
            if parsed is None:
                self.refused.emit("That entry must be a number.")
                old = self._items[i] if i < len(self._items) else 0
                self._block = True
                ed.setText(self._display(old))
                self._block = False
                return
            new = parsed
        else:
            new = text
        while len(self._items) <= i:
            self._items.append(0 if self._numeric else "")
        if self._items[i] == new:
            return
        self._items[i] = new
        self.changed.emit(list(self._items))


class FinishPlainText(QPlainTextEdit):
    """Multiline text; commit when the field loses focus (like QLineEdit)."""

    editingFinished = pyqtSignal()

    def focusOutEvent(self, event) -> None:  # noqa: N802
        super().focusOutEvent(event)
        self.editingFinished.emit()
