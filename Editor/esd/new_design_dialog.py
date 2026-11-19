"""File > New Design: which board is the design for? One of your boards (recorded by the set-up), a ready-made size, or a size you type.

The choice only fills in the size of the screen (and the header's board); the screen can be changed later in the Inspector."""
from __future__ import annotations

from typing import Any

from PyQt6.QtWidgets import QDialog, QDialogButtonBox, QFormLayout, QLabel, QListWidget, QSpinBox, QVBoxLayout

MIN_SIZE, MAX_SIZE = 16, 8000


class NewDesignDialog(QDialog):
    def __init__(self, parent, boards: list[dict[str, Any]], presets: list[dict[str, Any]], wanted_id: str = "") -> None:
        super().__init__(parent)
        self.setWindowTitle("New Design")
        self._entries: list[tuple[str, dict[str, Any] | None]] = []
        for b in boards:
            dev = {"id": b["name"], "name": b["name"], "board": b["kind"], "width": int(b["width"]), "height": int(b["height"])}
            self._entries.append((f"{b['name']}   (your board, {dev['width']} x {dev['height']})", dev))
        for p in presets:
            self._entries.append((f"{p['name']}   ({p['width']} x {p['height']})", dict(p)))
        self._entries.append(("Another screen: I type its size", None))

        lay = QVBoxLayout(self)
        lay.addWidget(QLabel("Which board is this design for?"))
        self.list = QListWidget()                       # a list that stays open: the chosen row stays highlighted until OK or Cancel
        for label, _dev in self._entries:
            self.list.addItem(label)
        self.list.setMinimumWidth(420)
        self.list.setFixedHeight(self.list.sizeHintForRow(0) * len(self._entries) + 12)     # every choice visible, no scrolling
        self.list.itemDoubleClicked.connect(lambda _item: self.accept())
        lay.addWidget(self.list)
        form = QFormLayout()
        self.width = QSpinBox()
        self.height = QSpinBox()
        for sb in (self.width, self.height):
            sb.setRange(MIN_SIZE, MAX_SIZE)
        form.addRow("Width (pixels)", self.width)
        form.addRow("Height (pixels)", self.height)
        lay.addLayout(form)
        self.hint = hint = QLabel("")
        hint.setWordWrap(True)
        lay.addWidget(hint)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        lay.addWidget(buttons)

        start = next((i for i, (_l, d) in enumerate(self._entries) if d and d["id"] == wanted_id), 0)
        self.list.currentRowChanged.connect(self._changed)
        self.list.setCurrentRow(start)
        self._changed(start)

    def _changed(self, index: int) -> None:
        dev = self._entries[index][1]
        custom = dev is None
        if not custom:
            self.width.setValue(int(dev["width"]))
            self.height.setValue(int(dev["height"]))
        self.width.setEnabled(custom)
        self.height.setEnabled(custom)
        self.hint.setText("Type the size of your screen. Later, the Inspector can only turn it (Orientation)." if custom else
                          "The size of this board's screen is fixed. Later, the Inspector can turn it (Orientation).")

    def device(self) -> dict[str, Any]:
        """The chosen device as the Editor's device dict (id, name, board, width, height)."""
        dev = self._entries[max(0, self.list.currentRow())][1]
        if dev is not None:
            return dev
        return {"id": "custom", "name": "Screen", "board": "board_cyd", "width": self.width.value(), "height": self.height.value()}
