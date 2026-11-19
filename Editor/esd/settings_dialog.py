"""Device > New device...: the window for your devices (one row each) and the QR code that adds a phone or tablet.

When it opens, the Editor looks for running Wattle boards on the Wi-Fi. A board whose phone has the page open tells the Editor the
phone's screen size, and that phone appears in the table; you only type its name. If a board is found but no phone is looking at it,
the window shows its web address as text AND as a QR code to scan with the phone's camera. It reads and writes the same editor.ini
that can still be edited by hand."""
from __future__ import annotations

import re
import secrets
import threading

from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QColor, QImage, QPainter, QPixmap
from PyQt6.QtWidgets import (
    QComboBox, QDialog, QDialogButtonBox, QFileDialog, QGridLayout, QHBoxLayout, QHeaderView, QLabel, QLineEdit, QMessageBox,
    QPushButton, QSpinBox, QTableWidget, QTableWidgetItem, QVBoxLayout,
)

from esd import devices as devs
from esd.qrcode_min import make_qr

SPEEDS = ("Slow", "Normal", "Fast")
TYPES = (("Phone, tablet or computer", devs.BROWSER), ("CYD board (screen on the board)", devs.CYD))
NAME, TYPE, WIDTH, HEIGHT, ADDRESS = range(5)          # table columns


def _slug(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_") or "device"


def qr_pixmap(text: str, module: int = 5) -> QPixmap:
    """The QR code of text as a picture: black on white with the 4-module quiet border that scanners need."""
    m = make_qr(text)
    n = len(m) + 8
    img = QImage(n * module, n * module, QImage.Format.Format_RGB32)
    img.fill(QColor("white"))
    p = QPainter(img)
    for r, row in enumerate(m):
        for c, dark in enumerate(row):
            if dark:
                p.fillRect((c + 4) * module, (r + 4) * module, module, module, QColor("black"))
    p.end()
    return QPixmap.fromImage(img)


class SettingsDialog(QDialog):
    scanned = pyqtSignal(list)

    def __init__(self, parent, settings, devices: list[dict], projects_start: str, scan: bool = True) -> None:
        super().__init__(parent)
        self.setWindowTitle("New device")
        self.setMinimumWidth(720)
        self._settings = settings
        own = {s[len("device."):] for s in settings.sections("device.")}
        self._ready_names = [d["name"] for d in devices if d["id"] not in own]
        self._own_ids: list[str] = []              # the id of each row in the table ("" for a new row)
        self._removed: list[str] = []
        self._projects_start = projects_start
        self._known: set[str] = set()              # addresses of boards that have answered
        self._searching = False
        self._adding = False                       # "Add a device" was pressed: waiting for the device that scans our code
        self._token = ""                           # the one-time code (in the QR address, or offered to the open pages): only that device is added
        self._got = ""                              # what to tell the user once a device has been added
        self._offered_to = ""                      # the address of the ESP32 that was asked to offer the code

        lay = QVBoxLayout(self)
        lay.addSpacing(8)
        lay.addWidget(QLabel("Your devices:"))
        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(["Name", "Type", "Width", "Height", "Address"])
        self.table.horizontalHeader().setSectionResizeMode(NAME, QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(TYPE, QHeaderView.ResizeMode.Fixed)
        self.table.setColumnWidth(TYPE, 215)
        self.table.verticalHeader().hide()
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setMinimumHeight(130)
        lay.addWidget(self.table)

        box = QHBoxLayout()
        self.status = QLabel("")
        self.status.setTextFormat(Qt.TextFormat.RichText)
        self.status.setWordWrap(True)
        self.status.setMinimumHeight(70)
        self.status.setStyleSheet("QLabel { border: 1px solid #888; border-radius: 4px; padding: 6px; }")
        box.addWidget(self.status, 1)
        self.qr = QLabel()
        self.qr.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.qr.hide()
        box.addWidget(self.qr)
        lay.addLayout(box)

        addr_row = QHBoxLayout()
        addr_row.addWidget(QLabel("ESP32 address (only if the search does not find it):"))
        self.addr_edit = QLineEdit(settings.get("editor", "board_address"))
        self.addr_edit.setPlaceholderText("for example 192.168.1.107")
        self.addr_edit.returnPressed.connect(self.search)
        addr_row.addWidget(self.addr_edit, 1)
        lay.addLayout(addr_row)

        row = QHBoxLayout()
        rem = QPushButton("Remove selected")
        rem.clicked.connect(self._remove_rows)
        row.addWidget(rem)
        row.addStretch(1)
        lay.addLayout(row)

        for sec in settings.sections("device."):
            dev = next((d for d in devices if d["id"] == sec[len("device."):]), None)
            if dev:
                self._add_row(dev["id"], dev["name"], dev["board"], dev["width"], dev["height"],
                              settings.get(sec, "address"), settings.get(sec, "board_name"), settings.get(sec, "viewer"))

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        self._ok = buttons.button(QDialogButtonBox.StandardButton.Ok)
        buttons.accepted.connect(self._accept)
        buttons.rejected.connect(self.reject)
        lay.addWidget(buttons)

        self.scanned.connect(self._show_found)
        if scan:
            self.add_device()                      # always straight to "scan this code with your phone or tablet"

    # ---- looking for boards
    def search(self) -> None:
        if self._searching:
            return
        self._searching = True
        if not self._known:
            self.status.setText("<b>Looking for your ESP32 on the Wi-Fi ...</b>")
        typed = self.addr_edit.text().strip().removeprefix("http://").strip("/")
        addresses = (self._known | {self.table.item(i, ADDRESS).text() for i in range(self.table.rowCount())}
                     | {self._settings.get("editor", "board_address"), typed})
        names = {self._board_name(i) for i in range(self.table.rowCount())} | {self._settings.get("editor", "board_name")}

        def work() -> None:
            self.scanned.emit(devs.look_for_boards(sorted(a for a in addresses if a), sorted(n for n in names if n)))
        threading.Thread(target=work, daemon=True).start()

    def _board_name(self, row: int) -> str:
        item = self.table.item(row, ADDRESS)
        return str(item.data(Qt.ItemDataRole.UserRole) or "") if item else ""

    def _viewer(self, row: int) -> str:
        item = self.table.item(row, ADDRESS)
        return str(item.data(Qt.ItemDataRole.UserRole + 1) or "") if item else ""

    def _row_for(self, b: dict, dv: dict, answered: set[str], taken: set[int]) -> int | None:
        """The table row of one browser that has the page open: by its own id; else a device saved before the ids existed that has this
        board and this size (it then takes the id over)."""
        r = next((i for i in range(self.table.rowCount()) if dv["id"] and self._viewer(i) == dv["id"]), None)
        if r is None:
            r = next((i for i in range(self.table.rowCount())
                      if i not in taken and not self._viewer(i)
                      and (self.table.item(i, ADDRESS).text() == b["address"]
                           or (b["name"] and self._board_name(i) == b["name"] and self.table.item(i, ADDRESS).text() not in answered))
                      and (self.table.cellWidget(i, WIDTH).value(), self.table.cellWidget(i, HEIGHT).value()) == (dv["width"], dv["height"])), None)
        if r is not None:
            self.table.item(r, ADDRESS).setText(b["address"])
            self.table.item(r, ADDRESS).setData(Qt.ItemDataRole.UserRole, b["name"] or self._board_name(r))
            if dv["id"]:
                self.table.item(r, ADDRESS).setData(Qt.ItemDataRole.UserRole + 1, dv["id"])
        return r

    def add_device(self) -> None:
        """Show a QR code that belongs to THIS registration and wait for the device that scans it (and nobody else): so the row that
        appears is certainly the device in your hand."""
        self._adding = True
        self._token = secrets.token_hex(3)
        address = (self.addr_edit.text().strip().removeprefix("http://").strip("/") or next(iter(sorted(self._known)), "")
                   or self._settings.get("editor", "board_address")
                   or next((self.table.item(i, ADDRESS).text() for i in range(self.table.rowCount()) if self.table.item(i, ADDRESS).text()), ""))
        if address:
            self._show_scan_hint(address)
        else:
            self.status.setText("<b>I do not know where your ESP32 is yet.</b> I am looking for it now. If it is not found, type its address "
                                "in the box below and press Enter.")
            self.qr.hide()
        self.search()

    def _show_scan_hint(self, address: str) -> None:
        self._offered_to = address
        self.status.setText("<b>Scan this code with the phone or tablet you want to add, then tap the address it shows.</b>" + self._got)
        self.qr.setPixmap(qr_pixmap(f"http://{address}/?join={self._token}"))
        self.qr.show()
        threading.Thread(target=devs.offer_join, args=(address, self._token), daemon=True).start()   # the bar on every open page

    def done(self, result: int) -> None:
        if self._offered_to:                                   # take the offer back from the open pages
            threading.Thread(target=devs.offer_join, args=(self._offered_to, ""), daemon=True).start()
        super().done(result)

    def _show_found(self, boards: list) -> None:
        self._searching = False
        self._known |= {b["address"] for b in boards}
        added, updated = [], []
        answered = {b["address"] for b in boards}
        taken: set[int] = set()
        for b in boards:
            for dv in b["devices"]:
                r = self._row_for(b, dv, answered, taken)
                if r is None:
                    if not (self._adding and self._token and dv["join"] == self._token):
                        continue                  # a device we did not ask for: never guess whose it is
                    n = self.table.rowCount()
                    names = {self.table.item(i, NAME).text() for i in range(n)}
                    self._add_row("", "My phone" if "My phone" not in names else f"My phone {n + 1}", devs.BROWSER,
                                  dv["width"], dv["height"], b["address"], b["name"], dv["id"])
                    added.append((b, dv))
                    self.table.setCurrentCell(n, NAME)
                    self.table.editItem(self.table.item(n, NAME))                     # ready to type the name
                    taken.add(n)
                    self._token = secrets.token_hex(3)       # that code is used up: the next device gets a new one
                else:
                    taken.add(r)
                    if (self.table.cellWidget(r, WIDTH).value(), self.table.cellWidget(r, HEIGHT).value()) != (dv["width"], dv["height"]):
                        updated.append((r, dv))
                    self.table.cellWidget(r, WIDTH).setValue(dv["width"])
                    self.table.cellWidget(r, HEIGHT).setValue(dv["height"])
        lines = []
        for b, dv in added:
            self._ok.setText("Save")                       # a new device is only kept when this is pressed: make it hard to miss
            self._ok.setStyleSheet("QPushButton { background: #c62828; color: #fff; font-weight: bold; }")
            self._got = ("<br><br><b>Got it: a device was added (screen %d x %d). Type its name in the list above. "
                         "To add another one, scan the code again. When all are added, press Save.</b>" % (dv["width"], dv["height"]))
        for r, dv in updated:
            lines.append(f"Updated from the device: {self.table.item(r, NAME).text()} is now {dv['width']} x {dv['height']}.")
        if not boards:
            lines.append("<b>No ESP32 with Wattle answered.</b> Check that it is plugged in, that this computer and the ESP32 are on the "
                         "same Wi-Fi, and that it runs the browser flavour of Wattle. If you know its address, type it in the box "
                         "below and press Enter. This window keeps looking while it is open.")
        elif not self._adding and not added and not updated:
            lines.append("Your ESP32 was found. To add another phone, tablet or computer, press <b>Add a device</b>.")
        if self._adding and boards:                  # keep the code in view until the device that scans it has shown up
            self._show_scan_hint(boards[0]["address"])
            if lines:
                self.status.setText(self.status.text() + "<br>" + "<br>".join(lines))
        else:
            self.status.setText("<br>".join(lines))
            self.qr.hide()
        if not boards or self._adding:                 # keep looking, and keep the code fresh, while this window is open
            QTimer.singleShot(4000, self._again)

    def _again(self) -> None:
        if self.isVisible():
            self.search()

    # ---- the table
    def _spin(self, value: int) -> QSpinBox:
        sp = QSpinBox()
        sp.setRange(40, 8000)
        sp.setValue(int(value))
        return sp

    def _add_row(self, dev_id: str, name: str, board: str, width: int, height: int, address: str, board_name: str = "",
                 viewer: str = "") -> None:
        r = self.table.rowCount()
        self._own_ids.append(dev_id)
        self.table.insertRow(r)
        self.table.setItem(r, NAME, QTableWidgetItem(name))
        kind = QComboBox()
        for label, value in TYPES:
            kind.addItem(label, value)
        kind.setCurrentIndex(max(kind.findData(board), 0))
        kind.currentIndexChanged.connect(lambda _i, box=kind: self._type_changed(box))
        self.table.setCellWidget(r, TYPE, kind)
        self.table.setCellWidget(r, WIDTH, self._spin(width))
        self.table.setCellWidget(r, HEIGHT, self._spin(height))
        addr = QTableWidgetItem(address)
        addr.setFlags(addr.flags() & ~Qt.ItemFlag.ItemIsEditable)
        addr.setData(Qt.ItemDataRole.UserRole, board_name)
        addr.setData(Qt.ItemDataRole.UserRole + 1, viewer)        # the id of the browser on that device
        self.table.setItem(r, ADDRESS, addr)
        self._lock_size(r)
        self.table.setCurrentCell(r, 0)
        if not dev_id and address == "":
            self.table.editItem(self.table.item(r, NAME))

    def _lock_size(self, r: int) -> None:
        """A CYD board has a screen of its own size (320 x 240): the numbers are fixed. A phone, tablet or computer: free."""
        cyd = self.table.cellWidget(r, TYPE).currentData() == devs.CYD
        if cyd:
            self.table.cellWidget(r, WIDTH).setValue(320)
            self.table.cellWidget(r, HEIGHT).setValue(240)
        self.table.cellWidget(r, WIDTH).setEnabled(not cyd)
        self.table.cellWidget(r, HEIGHT).setEnabled(not cyd)

    def _type_changed(self, box: QComboBox) -> None:
        for r in range(self.table.rowCount()):
            if self.table.cellWidget(r, TYPE) is box:
                self._lock_size(r)

    def _remove_rows(self) -> None:
        for r in sorted({i.row() for i in self.table.selectedIndexes()}, reverse=True):
            if self._own_ids[r]:
                self._removed.append(self._own_ids[r])
            self.table.removeRow(r)
            del self._own_ids[r]

    def reject(self) -> None:
        if self._ok.text() == "Save" and QMessageBox.question(
                self, "New device", "A new device was added but not saved. Close without saving it?") != QMessageBox.StandardButton.Yes:
            return
        super().reject()

    def _accept(self) -> None:
        names = [self.table.item(r, NAME).text().strip() for r in range(self.table.rowCount())]
        if any(not n for n in names):
            QMessageBox.warning(self, "New device", "Every device needs a name.")
            return
        if len({n.lower() for n in names}) != len(names) or any(n.lower() == r.lower() for n in names for r in self._ready_names):
            QMessageBox.warning(self, "New device", "Two devices have the same name. Please make each name different.")
            return
        s = self._settings
        taken = {i for i in self._own_ids if i}
        for dev_id in self._removed:
            s.remove_section(f"device.{dev_id}")
        for r, name in enumerate(names):
            dev_id = self._own_ids[r]
            if not dev_id:
                base = _slug(name)
                dev_id, n = base, 2
                while dev_id in taken:
                    dev_id, n = f"{base}_{n}", n + 1
                taken.add(dev_id)
            sec = f"device.{dev_id}"
            s.set(sec, "name", name)
            s.set(sec, "width", str(self.table.cellWidget(r, WIDTH).value()))
            s.set(sec, "height", str(self.table.cellWidget(r, HEIGHT).value()))
            s.set(sec, "board", str(self.table.cellWidget(r, TYPE).currentData()))
            if self.table.item(r, ADDRESS).text():
                s.set(sec, "address", self.table.item(r, ADDRESS).text())
                if self._board_name(r):
                    s.set(sec, "board_name", self._board_name(r))
                if self._viewer(r):
                    s.set(sec, "viewer", self._viewer(r))
        typed = self.addr_edit.text().strip().removeprefix("http://").strip("/")
        if typed and typed in self._known:
            s.set("editor", "board_address", typed)                    # only an address that has really answered is kept
        self.accept()
