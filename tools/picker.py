#!/usr/bin/env python3
# picker.py -- DESKTOP tool (not for the board).
# (Qt window: PyQt6.) Lets a developer choose the target hardware from the catalogue in
# hardware/*.json and writes the matching "target" block into a design JSON.
#
#   python3 picker.py                          window
#   python3 picker.py --list                   boards in the catalogue
#   python3 picker.py --board board_cyd --write 999.json    no window
import json, glob, os, shutil, sys

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))     # the Wattle folder (this file is in tools/)
CATALOGUE = os.path.join(HERE, "hardware")


def load_catalogue(folder=CATALOGUE):
    """{kind: {name: manifest}} from every hardware/*.json (a file holds
    one manifest or a list of them). Drop a new file in to extend it."""
    cat = {}
    for path in sorted(glob.glob(os.path.join(folder, "*.json"))):
        data = json.load(open(path))
        for m in (data if isinstance(data, list) else [data]):
            m["_id"] = os.path.splitext(os.path.basename(path))[0]
            cat.setdefault(m["kind"], {})[m["name"]] = m
    return cat


def boards(cat):
    return {m["_id"]: m for m in cat.get("board", {}).values()}


def build_target(cat, processor, display, size, touch, fonts, board="", model=""):
    """The "target" block. size = "WxH" string; fonts = list of names."""
    d = cat["display"].get(display, {})
    t = cat["touch"].get(touch, {})
    w, h = (int(v) for v in size.split("x"))
    return {
        "model": model or "Custom",
        "processor": processor,
        "board": board,
        "display": {"model": display, "width": w, "height": h,
                    "interface": d.get("interface", ""), "driver": d.get("file", "")},
        "touch": {"model": touch, "type": t.get("type", ""),
                  "interface": t.get("interface", ""), "driver": t.get("file", "")},
        "fonts": [{"name": n, "sizes": cat["font"][n].get("sizes", []),
                   "styles": cat["font"][n].get("styles", [])} for n in fonts],
    }


def preset_target(cat, board):
    """Target block for a ready-made board manifest."""
    return build_target(cat, board["processor"], board["display"],
                        "%dx%d" % (board["width"], board["height"]), board["touch"],
                        board.get("fonts", []), board["_id"], board["name"])


def write_target(design_path, target):
    """Replaces only the "target" block; keeps a .bak copy of the file."""
    design = json.load(open(design_path))
    shutil.copyfile(design_path, design_path + ".bak")
    design["target"] = target
    with open(design_path, "w") as f:
        json.dump(design, f, indent=2)
        f.write("\n")


def write_design_txt(design_path, board_id=""):
    """design.txt next to the design: line 1 = design file, line 2 = board (optional).
    Copy it to the board with the design (mpremote fs cp design.txt :)."""
    path = os.path.join(os.path.dirname(os.path.abspath(design_path)), "design.txt")
    with open(path, "w") as f:
        f.write(os.path.basename(design_path) + "\n" + (board_id or "") + "\n")
    return path


def notes(cat, target):
    """Warnings for a chosen combination (what is not written yet)."""
    out = []
    if not target["display"]["driver"]:
        out.append("No display driver written yet for " + target["display"]["model"])
    if not target["touch"]["driver"]:
        out.append("No touch driver written yet for " + target["touch"]["model"])
    if not target["board"]:
        out.append("No board profile (pins) for this combination -- needs a board_*.py")
    return out


# Look copied from the ESD designer (dark theme; colours sampled from its
# screenshot). Edit here to restyle -- nothing else depends on it.
STYLE = """
QWidget { background: #152c34; color: #d5e6ea; font-size: 13px; }
QLabel { background: transparent; }
QComboBox, QLineEdit, QPlainTextEdit, QListWidget {
    background: #0f2128; border: 1px solid #1f4450; border-radius: 6px; padding: 4px 6px;
    selection-background-color: #0ea5c5; selection-color: #04161b; }
QComboBox QAbstractItemView { background: #0f2128; selection-background-color: #0ea5c5;
    selection-color: #04161b; border: 1px solid #1f4450; }
QListWidget::item { padding: 3px 6px; }
QListWidget::item:selected { background: #0ea5c5; color: #04161b; }
QPlainTextEdit { background: #0b1a20; }
QPushButton { background: #12262d; border: 1px solid #1f4450; border-radius: 8px; padding: 6px 12px; }
QPushButton:hover { border-color: #0ea5c5; }
QPushButton:pressed { background: #0ea5c5; color: #04161b; }
QMessageBox { background: #152c34; }
QScrollBar:vertical { background: #0f2128; width: 10px; margin: 0; }
QScrollBar::handle:vertical { background: #1f4450; border-radius: 5px; min-height: 20px; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical { background: transparent; }
"""

def gui():
    from PyQt6.QtWidgets import (QApplication, QWidget, QGridLayout, QLabel, QComboBox,
                                 QListWidget, QAbstractItemView, QPlainTextEdit, QLineEdit,
                                 QPushButton, QFileDialog, QCheckBox, QMessageBox)
    from PyQt6.QtCore import QTimer, Qt

    cat = load_catalogue()
    bmap = boards(cat)
    names = {m["name"]: bid for bid, m in bmap.items()}

    app = QApplication(sys.argv)
    app.setStyleSheet(STYLE)
    win = QWidget()
    win.setWindowTitle("Wattle Target Picker")
    win.resize(640, 560)
    grid = QGridLayout(win)

    preset = QComboBox()
    preset.addItem("(none -- choose each part below)")
    preset.addItems(list(names))
    proc = QComboBox()
    proc.addItems(list(cat.get("processor", {})))
    disp = QComboBox()
    disp.addItems(list(cat.get("display", {})))
    size = QComboBox()
    touch = QComboBox()
    touch.addItems(list(cat.get("touch", {})))
    fonts = QListWidget()
    fonts.setSelectionMode(QAbstractItemView.SelectionMode.MultiSelection)
    fonts.addItems(list(cat.get("font", {})))
    fonts.setMaximumHeight(80)
    info = QPlainTextEdit()
    info.setReadOnly(True)
    file_edit = QLineEdit()
    browse_btn = QPushButton("Browse...")
    reload_btn = QPushButton("Reload catalogue")
    write_btn = QPushButton("Write target to design file")
    txt_cb = QCheckBox("Also write design.txt (tells the board which design to load)")
    txt_cb.setChecked(True)
    quit_btn = QPushButton("Quit")
    status = QLabel("Choose the hardware, then a design file.")
    status.setWordWrap(True)

    rows = [("Ready-made board", preset), ("Processor", proc), ("Display", disp),
            ("Display size", size), ("Touch", touch), ("Fonts", fonts)]
    for r, (label, w) in enumerate(rows):
        lab = QLabel(label.upper())
        lab.setStyleSheet("color: #0ea5c9; font-weight: bold; font-size: 11px;")
        grid.addWidget(lab, r, 0)
        grid.addWidget(w, r, 1, 1, 2)
    grid.addWidget(info, 6, 0, 1, 3)
    dlab = QLabel("DESIGN FILE")
    dlab.setStyleSheet("color: #0ea5c9; font-weight: bold; font-size: 11px;")
    grid.addWidget(dlab, 7, 0)
    grid.addWidget(file_edit, 7, 1)
    grid.addWidget(browse_btn, 7, 2)
    grid.addWidget(reload_btn, 8, 0)
    grid.addWidget(write_btn, 8, 1)
    grid.addWidget(quit_btn, 8, 2)
    grid.addWidget(txt_cb, 9, 0, 1, 3)
    grid.addWidget(status, 10, 0, 1, 3)
    grid.setRowStretch(6, 1)

    def selected_fonts():
        return [i.text() for i in fonts.selectedItems()]

    def current():
        if not size.currentText():
            return None
        b = bmap.get(names.get(preset.currentText()), None)
        same = b is not None and (b["processor"], b["display"], b["touch"]) == \
            (proc.currentText(), disp.currentText(), touch.currentText())
        return build_target(cat, proc.currentText(), disp.currentText(), size.currentText(),
                            touch.currentText(), selected_fonts(),
                            b["_id"] if same else "", b["name"] if same else "")

    def refresh():
        t = current()
        if t is None:
            info.setPlainText("")
            return
        lines = ["Processor: %s  (%s)" % (t["processor"],
                                            cat.get("processor", {}).get(t["processor"], {}).get("firmware", "")),
                 "Display:   %s  %dx%d  %s" % (t["display"]["model"], t["display"]["width"],
                                                t["display"]["height"], t["display"]["interface"]),
                 "Touch:     %s  %s, %s" % (t["touch"]["model"], t["touch"]["type"], t["touch"]["interface"]),
                 "Fonts:     " + ", ".join(f["name"] for f in t["fonts"])]
        n = notes(cat, t)
        if n:
            lines += ["", "Heads-up:"] + ["  - " + x for x in n]
        info.setPlainText("\n".join(lines))

    def display_changed():
        size.blockSignals(True)
        size.clear()
        size.addItems(cat.get("display", {}).get(disp.currentText(), {}).get("sizes", []))
        size.blockSignals(False)
        refresh()

    def preset_changed():
        b = bmap.get(names.get(preset.currentText()))
        if not b:
            return
        proc.setCurrentText(b["processor"])
        disp.setCurrentText(b["display"])
        size.setCurrentText("%dx%d" % (b["width"], b["height"]))
        touch.setCurrentText(b["touch"])
        fonts.clearSelection()
        for k in range(fonts.count()):
            if fonts.item(k).text() in b.get("fonts", []):
                fonts.item(k).setSelected(True)
        refresh()

    def browse():
        path, _ = QFileDialog.getOpenFileName(win, "Design file", HERE, "Design JSON (*.json)")
        if path:
            file_edit.setText(path)

    def write():
        t = current()
        if t is None or not file_edit.text():
            QMessageBox.warning(win, "Picker", "Choose the hardware and a design file first.")
            return
        try:
            write_target(file_edit.text(), t)
        except Exception as e:
            QMessageBox.critical(win, "Picker", str(e))
            return
        msg = "Written: target block of %s (backup: .bak)" % os.path.basename(file_edit.text())
        if txt_cb.isChecked():
            msg += "; " + write_design_txt(file_edit.text(), t["board"])
        status.setText(msg)

    def reload():
        QMessageBox.information(win, "Picker", "Close and reopen the picker to re-read hardware/*.json.")

    disp.currentIndexChanged.connect(display_changed)
    for w in (proc, size, touch):
        w.currentIndexChanged.connect(refresh)
    fonts.itemSelectionChanged.connect(refresh)
    preset.currentIndexChanged.connect(preset_changed)
    browse_btn.clicked.connect(browse)
    reload_btn.clicked.connect(reload)
    write_btn.clicked.connect(write)
    quit_btn.clicked.connect(win.close)

    if fonts.count():
        fonts.item(0).setSelected(True)     # start with the first font chosen
    display_changed()
    win.show()
    if "--selftest" in sys.argv:
        QTimer.singleShot(800, win.close)
    app.exec()


if __name__ == "__main__":
    a = sys.argv
    if "--list" in a:
        cat = load_catalogue()
        for kind in ("board", "processor", "display", "touch", "font"):
            print(kind + ":", ", ".join(cat.get(kind, {})))
    elif "--board" in a:
        cat = load_catalogue()
        t = preset_target(cat, boards(cat)[a[a.index("--board") + 1]])
        print(json.dumps(t, indent=1))
        for n in notes(cat, t):
            print("note:", n)
        if "--write" in a:
            write_target(a[a.index("--write") + 1], t)
            print("target written")
            if "--design-txt" in a:
                print("wrote", write_design_txt(a[a.index("--write") + 1], t["board"]))
    else:
        gui()
