"""Wattle Editor main window: Design / Screen / widgets, JSON save."""

from __future__ import annotations

import copy
import os
from pathlib import Path

from PyQt6.QtCore import QEvent, QMimeData, QPoint, QRectF, QSize, QTimer, Qt
from PyQt6.QtGui import (
    QAction,
    QActionGroup,
    QColor,
    QDrag,
    QFont,
    QKeySequence,
    QPainter,
    QPainterPath,
    QPixmap,
)
from PyQt6.QtWidgets import (
    QCheckBox,
    QColorDialog,
    QDialog,
    QFileDialog,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMenu,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QSizePolicy,
    QSplitter,
    QStyle,
    QStyledItemDelegate,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from esd import APP_TITLE, JSON_FILTER
from esd.canvas import WIDGET_MIME, DesignCanvas
from esd.catalogue import (
    DESIGN_PROPS,
    SCHEMA_COLORS,
    SCREEN_PROPS,
    TRANSPARENT_BACKGROUNDS,
    canonical_color,
    make_widget_defaults,
    palette_widgets,
    resolve_color,
    spec_for,
)
from esd.fonts import (
    FontCatalog,
    catalog_from_hardware,
    load_font_catalog,
    missing_font_names,
    size_items,
    type_items,
)
from esd.inspector_widgets import (
    ROW_H,
    BarRowsEditor,
    ChoiceRow,
    EntryListEditor,
    FinishPlainText,
    JsonNumberBox,
    PickRow,
    choice_label,
    format_json_number,
    parse_json_number,
)
from esd.json_io import load_design, save_design
from esd.notes import component_note, property_note
from esd.recorder import make_recorder
from esd.model import (
    Design,
    clamp_widget,
    cross_check_warning,
    empty_design,
    find_free_position,
    geometry_allowed,
    get_path,
    is_python_id,
    items_to_lines,
    lines_to_items,
    normalize_typed_values,
    overlap_text,
    text_to_tree,
    tree_leaf_paths,
    tree_to_text,
    overlapping_interactive,
    set_path,
)
from wattle_theme import (
    ACCENT,
    INK,
    ORANGE,
    ORANGE_INK,
    apply_theme,
    editor_qss,
    is_dark,
    make_theme_toggle,
    studio_colors,
)


class PaletteItemDelegate(QStyledItemDelegate):
    """Draw each palette component in a Hub-style rounded box."""

    def paint(self, painter, option, index) -> None:  # noqa: N802
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        c = studio_colors()
        is_leaf = bool(index.data(Qt.ItemDataRole.UserRole))
        selected = bool(option.state & QStyle.StateFlag.State_Selected)
        tree = self.parent()
        hover_item = getattr(tree, "_hover_item", None) if tree is not None else None
        hover = hover_item is not None and tree.itemFromIndex(index) is hover_item
        text = str(index.data() or "")
        if not is_leaf:
            painter.restore()
            return
        widget = option.widget
        right = option.rect.right()
        if widget is not None:
            vw = widget.width()
            vp = getattr(widget, "viewport", None)
            if callable(vp) and vp() is not None:
                vw = vp().width()
            right = max(right, vw - 4)
        rect = QRectF(
            option.rect.left() + 6,
            option.rect.top() + 1,
            max(40, right - option.rect.left() - 10),
            option.rect.height() - 2,
        )
        path = QPainterPath()
        path.addRoundedRect(rect, 6, 6)
        if selected:
            painter.fillPath(path, QColor(ACCENT))
            painter.setPen(QColor(ACCENT))
            painter.drawPath(path)
            painter.setPen(QColor(c["btn_ink"]))
        else:
            painter.fillPath(path, QColor(c["field"]))
            painter.setPen(QColor(ORANGE if hover else c["line"]))
            painter.drawPath(path)
            painter.setPen(QColor(ORANGE_INK if hover else c["title"]))
        painter.drawText(
            rect.adjusted(10, 0, -8, 0),
            int(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft),
            text,
        )
        painter.restore()

    def sizeHint(self, option, index):  # noqa: N802
        if index.data(Qt.ItemDataRole.UserRole):
            return QSize(option.rect.width(), 22)
        return QSize(option.rect.width(), 14)


class PaletteTree(QTreeWidget):
    """Drag widget types onto the design canvas (palette look)."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("paletteTree")
        self.setHeaderHidden(True)
        self.setIndentation(0)
        self.setRootIsDecorated(False)
        self.setItemsExpandable(False)
        self.setExpandsOnDoubleClick(False)
        self.setDragEnabled(True)
        self.setDefaultDropAction(Qt.DropAction.CopyAction)
        self.setMouseTracking(True)
        self.setAttribute(Qt.WidgetAttribute.WA_Hover, True)
        self.viewport().setMouseTracking(True)
        self.viewport().setAttribute(Qt.WidgetAttribute.WA_Hover, True)
        self.setUniformRowHeights(False)
        self.setItemDelegate(PaletteItemDelegate(self))
        self._hover_item = None
        self.viewport().installEventFilter(self)
        f = QFont()
        f.setPixelSize(13)
        self.setFont(f)

    # Hover highlight is tracked here explicitly, in self._hover_item, instead of trusting Qt's
    # own State_MouseOver -- that turned out to blank the hovered row's text in this app (a Qt
    # delegate/view quirk, not chased further). It is also kept separate from selection/
    # currentItem() on purpose: an earlier version used setCurrentItem() for the hover look, but
    # currentItem() is also what startDrag() below picks up -- so if the mouse drifted onto the
    # next row before Qt recognised the drag gesture, the wrong widget got dragged. A full
    # viewport repaint on every hover change is cheap for a palette this short.
    def eventFilter(self, obj, event):  # noqa: N802
        if obj is self.viewport():
            if event.type() == QEvent.Type.MouseMove:
                item = self.itemAt(event.position().toPoint())
                if item is not self._hover_item:
                    self._hover_item = item
                    self.viewport().update()
            elif event.type() == QEvent.Type.Leave:
                if self._hover_item is not None:
                    self._hover_item = None
                    self.viewport().update()
        return super().eventFilter(obj, event)

    def startDrag(self, _supportedActions) -> None:  # noqa: N802
        item = self.currentItem()
        if item is None:
            return
        wtype = item.data(0, Qt.ItemDataRole.UserRole)
        if not wtype:
            return
        label = item.text(0)
        mime = QMimeData()
        mime.setData(WIDGET_MIME, str(wtype).encode("utf-8"))
        mime.setText(str(wtype))
        drag = QDrag(self)
        drag.setMimeData(mime)
        if str(wtype) == "screen":
            pw, ph = 130, 30
        else:
            spec = make_widget_defaults(str(wtype))
            pw = max(24, int(spec.get("w") or 80))
            ph = max(16, int(spec.get("h") or 24))
        pix = QPixmap(pw, ph)
        pix.fill(QColor(ACCENT))
        painter = QPainter(pix)
        painter.setPen(QColor(INK))
        painter.drawRect(0, 0, pw - 1, ph - 1)
        painter.setPen(QColor("#ffffff"))
        painter.setFont(QFont(self.font().family(), 11))
        painter.drawText(pix.rect(), Qt.AlignmentFlag.AlignCenter, label)
        painter.end()
        drag.setPixmap(pix)
        drag.setHotSpot(QPoint(0, 0))
        drag.exec(Qt.DropAction.CopyAction)


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self._recorder = make_recorder()
        self.resize(1280, 800)
        self._dark = is_dark()
        self.setStyleSheet(self._full_qss())
        self.design = Design(empty_design())
        self._suspend = False
        self._dirty = False
        self._clean = copy.deepcopy(self.design.data)
        self._undo: list[dict] = []
        self._redo: list[dict] = []
        self._clip = None
        self._geom: dict[str, QSpinBox] = {}
        self._choices: dict[str, QWidget] = {}  # every property's live editor widget, by key
        self._event_boxes: dict[str, QCheckBox] = {}  # the current widget's event checkboxes, by event name
        self._note_kind: str | None = None
        self._file_dir = self._default_file_dir()
        self._build_menus()
        self._build_ui()
        self._refresh_tree()
        self.canvas.set_design(self.design)
        sc = self.design.first_screen()
        if sc:
            self.canvas.active_screen_id = str(sc.get("id") or "")
            self.canvas.select(f"screen:{sc.get('id')}")
        self._set_status("Empty Design. File -> Open, or drag a Button from the Palette.")
        self._refresh_title()

    def _act(self, menu, text, slot, shortcut=None) -> QAction:
        a = QAction(text, self)
        if shortcut is not None:
            a.setShortcut(shortcut)
        a.triggered.connect(slot)
        menu.addAction(a)
        return a

    def _build_menus(self) -> None:
        mb = self.menuBar()
        m_file = mb.addMenu("&File")
        self._act(m_file, "&New Design", self.file_new, QKeySequence.StandardKey.New)
        self._act(m_file, "&Open...", self.file_open, QKeySequence.StandardKey.Open)
        m_file.addSeparator()
        self._act(m_file, "&Save", self.file_save, QKeySequence.StandardKey.Save)
        self._act(m_file, "Save &As...", self.file_save_as, QKeySequence.StandardKey.SaveAs)
        self._act(m_file, "Save and Exit", self.file_save_and_exit)
        m_file.addSeparator()
        self._act(m_file, "New &Screen", self.add_screen)
        m_file.addSeparator()
        self._act(m_file, "Add &Font...", self.add_font)
        m_file.addSeparator()
        self._act(m_file, "Projects F&older...", self.set_projects_folder)
        m_file.addSeparator()
        self._act(m_file, "E&xit", self.close)

        m_edit = mb.addMenu("&Edit")
        self._act(m_edit, "&Undo", self.undo, QKeySequence.StandardKey.Undo)
        self._act(m_edit, "&Redo", self.redo, QKeySequence.StandardKey.Redo)
        m_edit.addSeparator()
        self._act(m_edit, "&Copy", self.copy_selected, QKeySequence.StandardKey.Copy)
        self._act(m_edit, "&Paste", self.paste_widgets, QKeySequence.StandardKey.Paste)
        self._act(m_edit, "&Delete", self.delete_selected, QKeySequence.StandardKey.Delete)
        m_edit.addSeparator()
        self._act(m_edit, "Select &All", self.select_all, QKeySequence.StandardKey.SelectAll)

        m_view = mb.addMenu("&View")
        self._act_show_grid = QAction("Show Grid", self)
        self._act_show_grid.setCheckable(True)
        self._act_show_grid.setChecked(True)
        self._act_show_grid.toggled.connect(self._set_grid)
        m_view.addAction(self._act_show_grid)
        self._act_snap = QAction("Snap to Grid", self)
        self._act_snap.setCheckable(True)
        self._act_snap.setChecked(True)
        self._act_snap.toggled.connect(self._set_snap)
        m_view.addAction(self._act_snap)
        self._act_show_hidden = QAction("Show Hidden Widgets", self)
        self._act_show_hidden.setCheckable(True)
        self._act_show_hidden.setChecked(True)
        self._act_show_hidden.toggled.connect(self._set_show_hidden)
        m_view.addAction(self._act_show_hidden)
        m_view.addSeparator()
        g_grp = QActionGroup(self)
        g_grp.setExclusive(True)
        for n in (4, 8, 16, 32):
            a = QAction(f"Grid Spacing - {n}px", self)
            a.setCheckable(True)
            a.setChecked(n == 8)
            a.toggled.connect(lambda on, v=n: on and self._set_grid_spacing(v))
            g_grp.addAction(a)
            m_view.addAction(a)

        m_help = mb.addMenu("&Help")
        self._act(m_help, "&About", self._about)

        host = QWidget()
        hl = QHBoxLayout(host)
        hl.setContentsMargins(4, 2, 8, 2)
        hl.addWidget(make_theme_toggle(self._apply_theme))
        mb.setCornerWidget(host, Qt.Corner.TopRightCorner)

    def _full_qss(self) -> str:
        c = studio_colors(dark=self._dark)
        return editor_qss(dark=self._dark) + f"""
QFrame#esdPanel {{
  background: {c['header']};
  border: 1px solid {c['line']};
  border-radius: 12px;
}}
QFrame#esdPanel QLabel#panelCaption {{
  background: transparent;
}}
QFrame#esdPanel QListWidget,
QFrame#esdPanel QTreeWidget,
QFrame#esdPanel QScrollArea,
QFrame#esdPanel QScrollArea > QWidget {{
  background: transparent;
  border: none;
}}
"""

    def _esd_panel(self, title: str) -> tuple[QFrame, QVBoxLayout]:
        box = QFrame()
        box.setObjectName("esdPanel")
        lay = QVBoxLayout(box)
        lay.setContentsMargins(8, 4, 8, 8)
        lay.setSpacing(4)
        cap = QLabel(title)
        cap.setObjectName("panelCaption")
        lay.addWidget(cap)
        return box, lay

    def _apply_theme(self, dark: bool) -> None:
        self._dark = bool(dark)
        self.setStyleSheet(self._full_qss())
        from PyQt6.QtWidgets import QApplication

        inst = QApplication.instance()
        if inst is not None:
            apply_theme(inst)
        self.canvas.update()
        self._rebuild_inspector()

    def _build_ui(self) -> None:
        split = QSplitter(Qt.Orientation.Horizontal)
        self.setCentralWidget(split)

        pal_wrap = QWidget()
        pal_wrap.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Expanding)
        pal_outer = QVBoxLayout(pal_wrap)
        pal_outer.setContentsMargins(8, 8, 4, 8)
        pal_outer.setSpacing(0)
        pal_frame = QFrame()
        pal_frame.setObjectName("paletteFrame")
        pal_frame.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Expanding)
        pl = QVBoxLayout(pal_frame)
        pl.setContentsMargins(8, 4, 8, 8)
        pl.setSpacing(4)
        cap = QLabel("PALETTE")
        cap.setObjectName("panelCaption")
        pl.addWidget(cap)
        self.palette = PaletteTree()
        self.palette.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Expanding)
        screen_item = QTreeWidgetItem(["SCREEN"])
        screen_item.setData(0, Qt.ItemDataRole.UserRole, "screen")
        sf = screen_item.font(0)
        sf.setPixelSize(13)
        screen_item.setFont(0, sf)
        screen_item.setFlags(
            Qt.ItemFlag.ItemIsEnabled
            | Qt.ItemFlag.ItemIsSelectable
            | Qt.ItemFlag.ItemIsDragEnabled
        )
        self.palette.addTopLevelItem(screen_item)
        for kind, label in palette_widgets():
            child = QTreeWidgetItem([label])
            child.setData(0, Qt.ItemDataRole.UserRole, kind)
            cf = child.font(0)
            cf.setPixelSize(13)
            child.setFont(0, cf)
            child.setFlags(
                Qt.ItemFlag.ItemIsEnabled
                | Qt.ItemFlag.ItemIsSelectable
                | Qt.ItemFlag.ItemIsDragEnabled
            )
            self.palette.addTopLevelItem(child)
        pl.addWidget(self.palette, 1)
        self.palette.currentItemChanged.connect(self._on_palette_notes)
        self.palette.itemDoubleClicked.connect(self._palette_add)
        notes_cap = QLabel("Notes")
        notes_cap.setObjectName("sectionLabel")
        pl.addWidget(notes_cap)
        self.palette_notes = self._make_notes_box(component_note(None))
        pl.addWidget(self.palette_notes)
        pal_frame.setMinimumWidth(210)
        pal_outer.addWidget(pal_frame, 1)
        split.addWidget(pal_wrap)

        tree_wrap = QWidget()
        tree_wrap.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Expanding)
        tree_outer = QVBoxLayout(tree_wrap)
        tree_outer.setContentsMargins(4, 8, 4, 8)
        tree_outer.setSpacing(0)
        tree_box, tl = self._esd_panel("APPLICATION TREE")
        tree_box.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Expanding)
        self.tree = QTreeWidget()
        self.tree.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Expanding)
        self.tree.setHeaderHidden(True)
        self.tree.setIndentation(14)
        self.tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.tree.customContextMenuRequested.connect(self._tree_context_menu)
        self.tree.currentItemChanged.connect(self._on_tree_select)
        tl.addWidget(self.tree, 1)
        tree_outer.addWidget(tree_box, 1)
        split.addWidget(tree_wrap)

        mid = QFrame()
        mid.setObjectName("canvasBoard")
        ml = QVBoxLayout(mid)
        ml.setContentsMargins(8, 6, 8, 8)
        self.canvas = DesignCanvas()
        self.canvas.selectionChanged.connect(self._on_canvas_select)
        self.canvas.selectionChanged.connect(self._record_selection)
        self.canvas.widgetsChanged.connect(self._on_widgets_changed)
        self.canvas.widgetDropped.connect(self._on_drop)
        self.canvas.widgetDropped.connect(self._record_drop)
        self.canvas.dragAboutToStart.connect(self._push_undo)
        self.canvas.dragFinished.connect(self._on_drag_finished)
        self.canvas.dragFinished.connect(self._record_drag_finished)
        self.canvas.overlapBlocked.connect(self._on_overlap_blocked)
        self.canvas.imageDropped.connect(self._on_image_dropped)
        self.canvas.keyboardFinished.connect(self._on_keyboard_finished)
        self.canvas.customContextMenuRequested.connect(self._canvas_context_menu)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setAlignment(Qt.AlignmentFlag.AlignCenter)
        scroll.setWidget(self.canvas)
        scroll.setObjectName("formBoard")
        ml.addWidget(scroll, 1)
        split.addWidget(mid)

        insp_wrap = QWidget()
        insp_outer = QVBoxLayout(insp_wrap)
        insp_outer.setContentsMargins(4, 8, 8, 8)
        insp, il = self._esd_panel("OBJECT INSPECTOR")
        self.insp_form_host = QWidget()
        self.insp_form = QFormLayout(self.insp_form_host)
        self.insp_form.setContentsMargins(6, 2, 6, 4)
        self.insp_form.setVerticalSpacing(2)
        self.insp_form.setHorizontalSpacing(4)
        self.insp_scroll = QScrollArea()
        self.insp_scroll.setWidgetResizable(True)
        self.insp_scroll.setWidget(self.insp_form_host)
        self.insp_scroll.viewport().installEventFilter(self)
        il.addWidget(self.insp_scroll, 1)
        insp_notes_cap = QLabel("Notes")
        insp_notes_cap.setObjectName("sectionLabel")
        il.addWidget(insp_notes_cap)
        self.inspector_notes = self._make_notes_box(component_note(None))
        il.addWidget(self.inspector_notes)
        insp_outer.addWidget(insp)
        split.addWidget(insp_wrap)
        split.setSizes([220, 210, 560, 320])
        split.setStretchFactor(0, 0)
        split.setStretchFactor(1, 0)
        split.setStretchFactor(2, 1)
        split.setStretchFactor(3, 0)

    def _set_status(self, msg: str) -> None:
        self.statusBar().showMessage(msg, 8000)

    def _make_notes_box(self, initial: str) -> QPlainTextEdit:
        box = QPlainTextEdit()
        box.setReadOnly(True)
        box.setPlainText(initial)
        box.setFixedHeight(84)
        box.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        box.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        box.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        box.setObjectName("helpBox")
        return box

    def _show_component_notes(self, kind: str | None) -> None:
        self._note_kind = kind
        text = component_note(kind)
        self.palette_notes.setPlainText(text)
        self.inspector_notes.setPlainText(text)

    def _on_palette_notes(self, current: QTreeWidgetItem | None, _previous=None) -> None:
        if current is None:
            return
        kind = current.data(0, Qt.ItemDataRole.UserRole)
        if not kind:
            return
        self._show_component_notes(str(kind))

    def _notes_for_token(self, token: str) -> None:
        if token == "design":
            self._show_component_notes("design")
            return
        if token.startswith("screen:"):
            self._show_component_notes("screen")
            return
        if token.startswith("widget:"):
            found = self.design.find_widget(token.split(":", 1)[1])
            if found is not None:
                self._show_component_notes(str(found[1].get("widget") or ""))
                return
        self._show_component_notes(None)

    def _wire_notes(self, widget: QWidget, key: str) -> None:
        if widget is None or not key:
            return

        def attach(w: QWidget) -> None:
            w.setProperty("helpKey", key)
            if not w.property("_esdNotes"):
                w.installEventFilter(self)
                w.setProperty("_esdNotes", True)

        attach(widget)
        for child in widget.findChildren(QWidget):
            attach(child)

    def eventFilter(self, obj, event):  # noqa: N802
        if event.type() in (QEvent.Type.MouseButtonPress, QEvent.Type.FocusIn):
            key = obj.property("helpKey") if obj is not None else None
            if key:
                self.inspector_notes.setPlainText(property_note(str(key), self._note_kind))
        scroll = getattr(self, "insp_scroll", None)
        if scroll is not None and obj is scroll.viewport() and event.type() == QEvent.Type.Resize:
            self._fit_inspector_height()
        return super().eventFilter(obj, event)

    def _fit_inspector_height(self) -> None:
        """Keep every inspector row fully above the next one, and scroll the rest."""
        host = self.insp_form_host
        width = host.width()
        if width < 20:
            return
        lay = self.insp_form
        height = lay.heightForWidth(width) if lay.hasHeightForWidth() else -1
        if height < 1:
            height = lay.totalMinimumSize().height()
        if height < 1:
            return
        # heightForWidth()/totalMinimumSize() only know about each row's own allocated
        # box, not whether something inside it (e.g. a button a stylesheet grew taller
        # than its row, as the Keyboard's "Call" button once did) overflows that box.
        # Measure the real bottom edge of every row's descendants instead of trusting
        # the hint, so a future oversized row can never be left unreachable by scrolling.
        last_bottom = 0
        for i in range(lay.count()):
            item = lay.itemAt(i)
            row_widget = item.widget() if item else None
            if row_widget is None:
                continue
            last_bottom = max(last_bottom, row_widget.mapTo(host, row_widget.rect().bottomLeft()).y())
            for child in row_widget.findChildren(QWidget):
                last_bottom = max(last_bottom, child.mapTo(host, child.rect().bottomLeft()).y())
        if last_bottom > 0:
            height = max(height, last_bottom + lay.contentsMargins().bottom() + 1)
        if host.minimumHeight() == height:
            return
        host.setMinimumHeight(height)

    def _push_undo(self) -> None:
        self._undo.append(copy.deepcopy(self.design.data))
        self._redo.clear()
        if len(self._undo) > 40:
            self._undo.pop(0)

    def _restore(self, data: dict, status: str) -> None:
        self.design.data = data
        sc = self.design.screen_by_id(self.canvas.active_screen_id) or self.design.first_screen()
        token = f"screen:{sc.get('id')}" if sc else "design"
        self._reload_view(token)
        self._mark_dirty()
        self._set_status(status)

    def undo(self) -> None:
        if not self._undo:
            return
        self._redo.append(copy.deepcopy(self.design.data))
        self._restore(self._undo.pop(), "Undo")

    def redo(self) -> None:
        if not self._redo:
            return
        self._undo.append(copy.deepcopy(self.design.data))
        self._restore(self._redo.pop(), "Redo")

    def _set_grid(self, on: bool) -> None:
        self.canvas.show_grid = bool(on)
        self.canvas.update()

    def _set_snap(self, on: bool) -> None:
        self.canvas.snap = bool(on)

    def _set_show_hidden(self, on: bool) -> None:
        self.canvas.show_hidden = bool(on)
        self.canvas.update()

    def _set_grid_spacing(self, n: int) -> None:
        self.canvas.grid_size = int(n)
        self.canvas.update()

    def _mark_dirty(self) -> None:
        self._dirty = True
        self._refresh_title()

    def _mark_clean(self) -> None:
        self._dirty = False
        self._clean = copy.deepcopy(self.design.data)
        self._refresh_title()

    def _refresh_title(self) -> None:
        name = self.design.name
        path = Path(self.design.path).name if self.design.path else ""
        star = " *" if self._dirty else ""
        # Spelled out explicitly rather than relying on Qt to append the application display
        # name to the title -- that only happens on some platforms (macOS), not on Linux.
        self.setWindowTitle((path or name) + star + " — " + APP_TITLE)

    def _confirm_save(self) -> bool:
        if not self._dirty:
            return True
        box = QMessageBox(self)
        box.setWindowTitle("Save")
        box.setText("Save this Design before continuing?")
        save_btn = box.addButton("Save", QMessageBox.ButtonRole.AcceptRole)
        cancel_btn = box.addButton("Cancel", QMessageBox.ButtonRole.RejectRole)
        box.addButton("Close without saving", QMessageBox.ButtonRole.DestructiveRole)
        box.exec()
        clicked = box.clickedButton()
        if clicked is cancel_btn:
            return False
        if clicked is save_btn:
            return self.file_save()
        return True

    def file_new(self) -> None:
        if not self._confirm_save():
            return
        self.design = Design(empty_design())
        self.design.path = None
        self._undo.clear()
        self._redo.clear()
        self._reload_view("screen:main")
        self._mark_clean()
        self._set_status("New empty Design")

    # The user's projects folder: chosen once with File > Projects Folder..., remembered between sessions in the same
    # small settings folder that the installer uses (~/.config/wattle). Open and Save start there.
    _PROJECTS_FILE = Path.home() / ".config" / "wattle" / "projects_folder"

    def _projects_dir(self) -> str:
        try:
            text = self._PROJECTS_FILE.read_text(encoding="utf-8").strip()
        except OSError:
            return ""
        return text if text and Path(text).expanduser().is_dir() else ""

    def set_projects_folder(self) -> None:
        start = self._projects_dir() or self._default_file_dir()
        chosen = QFileDialog.getExistingDirectory(self, "Choose the folder for your projects", start)
        if not chosen:
            return
        try:
            self._PROJECTS_FILE.parent.mkdir(parents=True, exist_ok=True)
            self._PROJECTS_FILE.write_text(chosen + "\n", encoding="utf-8")
        except OSError as e:
            QMessageBox.warning(self, "Projects folder", f"The folder could not be remembered: {e}")
            return
        self._file_dir = chosen
        self._set_status(f"Projects folder: {chosen}")

    def _default_file_dir(self) -> str:
        projects = self._projects_dir()
        if projects:
            return projects
        documents = Path.home() / "Documents"
        if documents.is_dir():
            return str(documents)
        return str(Path.home())

    def _dialog_start_dir(self) -> str:
        if self.design.path:
            parent = str(Path(self.design.path).parent)
            if parent:
                return parent
        return self._file_dir or self._default_file_dir()

    def _remember_file_dir(self, path: str) -> None:
        parent = str(Path(path).parent)
        if parent:
            self._file_dir = parent

    def file_open(self) -> None:
        if not self._confirm_save():
            return
        path, _ = QFileDialog.getOpenFileName(
            self, "Open Design", self._dialog_start_dir(), JSON_FILTER
        )
        if not path:
            return
        try:
            data = load_design(path)
        except (OSError, ValueError) as exc:
            QMessageBox.warning(self, "Open", str(exc))
            return
        self.design = Design(data)
        self.design.path = path
        self._remember_file_dir(path)
        self._undo.clear()
        self._redo.clear()
        sc = self.design.first_screen()
        token = f"screen:{sc.get('id')}" if sc else "design"
        self._reload_view(token)
        self._mark_clean()
        self._set_status(self._opened_status(path))

    def file_save(self) -> bool:
        if not self.design.path:
            return self.file_save_as()
        return self._write(self.design.path)

    def file_save_as(self) -> bool:
        folder = Path(self._dialog_start_dir())
        name = (
            Path(self.design.path).name
            if self.design.path
            else f"{self.design.name.replace(' ', '_')}.json"
        )
        suggested = str(folder / name)
        path, _ = QFileDialog.getSaveFileName(self, "Save Design", suggested, JSON_FILTER)
        if not path:
            return False
        if not path.lower().endswith(".json"):
            path += ".json"
        return self._write(path)

    def file_save_and_exit(self) -> None:
        if self.file_save():
            self.close()

    def _write(self, path: str) -> bool:
        try:
            save_design(path, self.design.data)
        except OSError as exc:
            QMessageBox.warning(self, "Save", str(exc))
            return False
        self.design.path = path
        self._remember_file_dir(path)
        self._mark_clean()
        self._set_status(f"Saved {path}")
        return True

    def closeEvent(self, event) -> None:  # noqa: N802
        if self._confirm_save():
            event.accept()
        else:
            event.ignore()

    def raise_existing_window(self) -> None:
        """Show this window when a second Wattle Editor launch is attempted."""
        if self.isMinimized():
            self.setWindowState(self.windowState() & ~Qt.WindowState.WindowMinimized)
        self.show()
        self.raise_()
        self.activateWindow()

    def _about(self) -> None:
        QMessageBox.information(
            self,
            "About",
            f"{APP_TITLE}\n\n"
            "Design ESP32 screens. Widgets, in alphabetical order:\n"
            "Barchart, Button, Checkbox, Choice, Gauge, Image, Keyboard,\n"
            "Label, Line, Memo, ProgressBar, Slider, Stepper, Switch, Tree, Waveform.\n"
            "Application JSON is the contract. The widget catalogue stays in the Editor.",
        )

    def _reload_view(self, token: str) -> None:
        sid = self._screen_id_for_token(token)
        if self.canvas._kb_session is not None:
            self.canvas.cancel_keyboard_call()
        self.canvas.set_design(self.design, sid)
        self.canvas._apply_board_size()
        self._refresh_tree()
        self.canvas.select(token)
        self._rebuild_inspector()

    def _screen_id_for_token(self, token: str) -> str | None:
        if token.startswith("screen:"):
            sid = token.split(":", 1)[1]
            return sid or None
        if token.startswith("widget:"):
            found = self.design.find_widget(token.split(":", 1)[1])
            if found is not None:
                return str(found[0].get("id") or "") or None
        return self.canvas.active_screen_id or None

    def _refresh_tree(self) -> None:
        self.tree.blockSignals(True)
        self.tree.clear()
        root = QTreeWidgetItem(["Design"])
        root.setData(0, Qt.ItemDataRole.UserRole, "design")
        self.tree.addTopLevelItem(root)
        for sc in self.design.screens():
            sid = str(sc.get("id") or "")
            sitem = QTreeWidgetItem([sid or "screen"])
            sitem.setData(0, Qt.ItemDataRole.UserRole, f"screen:{sid}")
            root.addChild(sitem)
            for w in sc.get("widgets") or []:
                wid = str(w.get("id") or "")
                witem = QTreeWidgetItem([wid or "widget"])
                witem.setData(0, Qt.ItemDataRole.UserRole, f"widget:{wid}")
                sitem.addChild(witem)
        self.tree.expandAll()
        self.tree.blockSignals(False)
        self._sync_tree_selection(self.canvas.selected())

    def _sync_tree_selection(self, token: str) -> None:
        self.tree.blockSignals(True)
        it = self._find_tree_item(self.tree.invisibleRootItem(), token)
        if it is not None:
            self.tree.setCurrentItem(it)
        self.tree.blockSignals(False)

    def _find_tree_item(self, parent: QTreeWidgetItem, token: str) -> QTreeWidgetItem | None:
        for i in range(parent.childCount()):
            child = parent.child(i)
            if child.data(0, Qt.ItemDataRole.UserRole) == token:
                return child
            found = self._find_tree_item(child, token)
            if found is not None:
                return found
        if parent.data(0, Qt.ItemDataRole.UserRole) == token:
            return parent
        return None

    def _on_tree_select(self, current: QTreeWidgetItem | None, _prev=None) -> None:
        if current is None:
            return
        token = str(current.data(0, Qt.ItemDataRole.UserRole) or "design")
        sid = self._screen_id_for_token(token)
        if sid and sid != self.canvas.active_screen_id:
            if self.canvas._kb_session is not None:
                self.canvas.cancel_keyboard_call()
            self.canvas.set_design(self.design, sid)
        self.canvas.select(token)
        self._rebuild_inspector()

    def _opened_status(self, path: str) -> str:
        missing = missing_font_names(self.design.data)
        if not missing:
            return f"Opened {path}"
        names = ", ".join(missing)
        return f"Opened {path}. Font not in the target list: {names}"

    def _on_canvas_select(self, token: str) -> None:
        if os.environ.get("WATTLE_REPLAY"):
            print("window: selectionChanged ->", token, flush=True)
        self._sync_tree_selection(token)
        self._rebuild_inspector()
        self._notes_for_token(token)
        self._note_missing_font(token)
        self._note_widget_warning(token)

    def _note_missing_font(self, token: str) -> None:
        if not token.startswith("widget:"):
            return
        found = self.design.find_widget(token.split(":", 1)[1])
        if found is None:
            return
        inst = found[1]
        if "font_type" not in inst:
            return
        name = str(inst.get("font_type") or "default").strip() or "default"
        if load_font_catalog(self.design.data).has_type(name):
            message = self.statusBar().currentMessage()
            if "not in the target list" in message:
                self._set_status(
                    f"{inst.get('id')}  X:{inst.get('x')} Y:{inst.get('y')}  "
                    f"{inst.get('w')} x {inst.get('h')}"
                )
            return
        self._set_status(f"Font {name} is not in the target font list.")

    def _note_widget_warning(self, token: str) -> None:
        if not token.startswith("widget:"):
            return
        found = self.design.find_widget(token.split(":", 1)[1])
        if found is None:
            return
        msg = cross_check_warning(found[1])
        if msg:
            self._set_status(msg)

    def _on_widgets_changed(self) -> None:
        self._mark_dirty()
        self._sync_geom_fields()

    def _on_drag_finished(self) -> None:
        self._refresh_tree()
        self._rebuild_inspector()

    def _on_overlap_blocked(self, message: str) -> None:
        self._set_status(message)
        self._sync_geom_fields()

    def _sync_geom_fields(self) -> None:
        token = self.canvas.selected()
        if token.startswith("widget:"):
            found = self.design.find_widget(token.split(":", 1)[1])
            if found is None:
                return
            inst = found[1]
            for key in ("x", "y", "w", "h"):
                ed = self._geom.get(key)
                if ed is None:
                    continue
                ed.blockSignals(True)
                ed.setValue(int(inst.get(key) or 0))
                ed.blockSignals(False)
            return
        if token.startswith("screen:"):
            sc = self.design.screen_by_id(token.split(":", 1)[1])
            if sc is not None:
                self._sync_screen_geom(sc)

    def _sync_screen_geom(self, screen: dict) -> None:
        for key in ("width", "height"):
            ed = self._geom.get(key)
            if ed is None:
                continue
            ed.blockSignals(True)
            ed.setValue(int(screen.get(key) or 0))
            ed.blockSignals(False)
        ch = self._choices.get("orientation")
        if ch is not None:
            ch.set_value(screen.get("orientation"))

    def _palette_add(self, item: QTreeWidgetItem, _col: int = 0) -> None:
        if item is None:
            return
        kind = item.data(0, Qt.ItemDataRole.UserRole)
        if not kind:
            return
        if str(kind) == "screen":
            self.add_screen()
            return
        sid = self.canvas.active_screen_id
        if not sid:
            return
        trial = make_widget_defaults(str(kind))
        trial["id"] = ""
        pos = find_free_position(self.design, sid, trial, 20, 20)
        if pos is None:
            self._set_status("There is no free space left on this screen for that widget.")
            return
        self._on_drop(str(kind), pos[0], pos[1])

    def _on_drop(self, kind: str, x: int, y: int) -> None:
        if str(kind) == "screen":
            self.add_screen()
            return
        sid = self.canvas.active_screen_id
        if not sid:
            return
        before = copy.deepcopy(self.design.data)
        try:
            inst = self.design.add_widget(sid, kind, x, y)
        except (KeyError, ValueError) as exc:
            QMessageBox.warning(self, "Drop", str(exc))
            self._set_status(str(exc))
            return
        self._undo.append(before)
        if len(self._undo) > 40:
            self._undo.pop(0)
        self._redo.clear()
        self._mark_dirty()
        self._refresh_tree()
        self.canvas.update()
        if os.environ.get("WATTLE_REPLAY"):
            print("window: _on_drop selecting widget:", inst.get("id"), flush=True)
        self.canvas.select(f"widget:{inst.get('id')}")

    def add_screen(self) -> None:
        self._push_undo()
        current = self.design.screen_by_id(self.canvas.active_screen_id)
        sc = self.design.add_screen(like=current)
        self._mark_dirty()
        sid = str(sc.get("id") or "")
        self._reload_view(f"screen:{sid}")
        self._set_status(f"Added Screen {sid}")

    def add_font(self) -> None:
        """Register a font family (from hardware/font_*.json) into this design's target.fonts,
        so it, and its sizes, show up in every widget's Font box. The bitmap files themselves
        already exist in fonts/ -- this just tells the design it may use one of them."""
        hw = catalog_from_hardware()
        have = load_font_catalog(self.design.data)
        choices = [t for t in hw.types if t != "default" and not have.has_type(t)]
        if not choices:
            self._set_status(
                "Every available font is already in this design."
                if hw.types != ["default"]
                else "No extra font files found under hardware/."
            )
            return

        dlg = QDialog(self)
        dlg.setWindowTitle("Add Font")
        dlg.setModal(True)
        dlg.resize(320, min(420, 28 * max(3, min(len(choices), 12)) + 60))
        outer = QVBoxLayout(dlg)
        outer.setContentsMargins(8, 8, 8, 8)
        outer.setSpacing(4)
        outer.addWidget(QLabel("Add which font to this design?"))
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        host = QWidget()
        col = QVBoxLayout(host)
        col.setContentsMargins(0, 0, 0, 0)
        col.setSpacing(2)
        colors = studio_colors(dark=self._dark)
        for name in choices:
            sizes = [s for s in hw.sizes_for(name) if s != "default"]
            label = f"{name}  ({', '.join(str(s) for s in sizes)})" if sizes else name
            btn = QPushButton(label)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
            btn.setFixedHeight(ROW_H)
            btn.setStyleSheet(
                f"background:{colors['field']}; color:{colors['title']}; "
                f"border:1px solid {colors['line']}; border-radius:6px; padding:0 8px; font-size:12px;"
            )
            btn.clicked.connect(lambda _=False, n=name: self._do_add_font(dlg, hw, n))
            col.addWidget(btn)
        col.addStretch(1)
        scroll.setWidget(host)
        outer.addWidget(scroll, 1)
        dlg.exec()

    def _do_add_font(self, dlg: QDialog, hw: FontCatalog, name: str) -> None:
        dlg.accept()
        self._push_undo()
        entry = hw.target_entry(name)
        fonts = self.design.data.setdefault("target", {}).setdefault("fonts", [])
        if not isinstance(fonts, list):
            fonts = []
            self.design.data["target"]["fonts"] = fonts
        fonts.append(entry)
        self._mark_dirty()
        self._rebuild_inspector()
        self._set_status(f'Added font "{name}". It now appears in every widget\'s Font box.')

    def _record_drop(self, kind: str, x: int, y: int) -> None:
        self._recorder.log("drop", widget=kind, x=x, y=y)

    def _record_selection(self, token: str) -> None:
        self._recorder.log("select", token=token)

    def _record_drag_finished(self) -> None:
        # A resize-handle or move drag on the canvas never goes through _set_value (it
        # mutates the widget's x/y/w/h directly, continuously, while the mouse moves) -- so
        # unlike every other property change, the recorder has no other hook for it. Only the
        # *final* geometry is logged, not the drag itself; replay re-derives an on-screen
        # path from whatever the widget's geometry happens to be at the moment it replays
        # this (see replay.py), rather than needing every intermediate point here.
        token = self.canvas.selected()
        if not token.startswith("widget:"):
            return
        found = self.design.find_widget(token.split(":", 1)[1])
        if found is None:
            return
        _screen, widget = found
        self._recorder.log(
            "geometry",
            widget=widget.get("id"),
            x=widget.get("x"),
            y=widget.get("y"),
            w=widget.get("w"),
            h=widget.get("h"),
        )

    def _selected_widget_id(self) -> str:
        token = self.canvas.selected()
        if token.startswith("widget:"):
            return token.split(":", 1)[1]
        return ""

    def _selected_screen_id(self) -> str:
        token = self.canvas.selected()
        if token.startswith("screen:"):
            return token.split(":", 1)[1]
        if token.startswith("widget:"):
            found = self.design.find_widget(token.split(":", 1)[1])
            if found is not None:
                return str(found[0].get("id") or "")
        return self.canvas.active_screen_id

    def copy_selected(self) -> None:
        wid = self._selected_widget_id()
        if not wid:
            return
        found = self.design.find_widget(wid)
        if found is None:
            return
        self._clip = copy.deepcopy(found[1])
        self._set_status(f"Copied {wid}")

    def paste_widgets(self) -> None:
        if not self._clip:
            return
        sid = self.canvas.active_screen_id
        if not sid:
            return
        inst = copy.deepcopy(self._clip)
        kind = str(inst.get("widget") or "button")
        inst["id"] = self.design.unique_id(kind)
        inst["x"] = int(inst.get("x") or 0) + 8
        inst["y"] = int(inst.get("y") or 0) + 8
        sw, sh = self.design.screen_size(sid)
        clamp_widget(inst, sw, sh)
        sc = self.design.screen_by_id(sid)
        if sc is None:
            return
        pos = find_free_position(self.design, sid, inst, int(inst["x"]), int(inst["y"]))
        if pos is None:
            self._set_status("There is no free space left on this screen for that widget.")
            return
        inst["x"], inst["y"] = pos
        self._push_undo()
        sc.setdefault("widgets", []).append(inst)
        self._mark_dirty()
        self._refresh_tree()
        self.canvas.update()
        self.canvas.select(f"widget:{inst.get('id')}")

    def delete_selected(self) -> None:
        token = self.canvas.selected()
        if token.startswith("widget:"):
            wid = token.split(":", 1)[1]
            self._push_undo()
            sid = self._selected_screen_id()
            self.design.delete_widget(wid)
            self._mark_dirty()
            self._reload_view(f"screen:{sid}" if sid else "design")
            self._set_status(f"Deleted {wid}")
            return
        if token.startswith("screen:"):
            sid = token.split(":", 1)[1]
            box = QMessageBox(self)
            box.setWindowTitle("Delete Screen")
            box.setText(f"Delete Screen {sid} and all of its widgets?")
            box.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
            if box.exec() != QMessageBox.StandardButton.Yes:
                return
            self._push_undo()
            try:
                self.design.delete_screen(sid)
            except ValueError as exc:
                QMessageBox.information(self, "Delete Screen", str(exc))
                return
            nxt = self.design.first_screen()
            token_n = f"screen:{nxt.get('id')}" if nxt else "design"
            self.canvas.active_screen_id = str((nxt or {}).get("id") or "")
            self._mark_dirty()
            self._reload_view(token_n)
            self._set_status(f"Deleted Screen {sid}")

    def select_all(self) -> None:
        sid = self.canvas.active_screen_id
        widgets = self.design.widgets_on(sid)
        if widgets:
            self.canvas.select(f"widget:{widgets[-1].get('id')}")
        elif sid:
            self.canvas.select(f"screen:{sid}")

    def _tree_context_menu(self, pos) -> None:
        item = self.tree.itemAt(pos)
        if item is not None:
            self.tree.setCurrentItem(item)
        menu = QMenu(self)
        token = self.canvas.selected()
        act_del = menu.addAction("Delete", self.delete_selected)
        act_del.setEnabled(token.startswith("widget:") or token.startswith("screen:"))
        menu.addSeparator()
        menu.addAction("New Screen", self.add_screen)
        menu.exec(self.tree.viewport().mapToGlobal(pos))

    def _canvas_context_menu(self, pos) -> None:
        if self.canvas._kb_session is not None:
            menu = QMenu(self)
            menu.addAction("Cancel Keyboard", self.canvas.cancel_keyboard_call)
            menu.exec(self.canvas.mapToGlobal(pos))
            return
        token, _mode = self.canvas.hit_test(pos)
        self.canvas.select(token)
        menu = QMenu(self)
        has_w = token.startswith("widget:")
        act_copy = menu.addAction("Copy", self.copy_selected)
        act_copy.setEnabled(has_w)
        act_paste = menu.addAction("Paste", self.paste_widgets)
        act_paste.setEnabled(bool(self._clip))
        menu.addAction("Undo", self.undo)
        menu.addAction("Redo", self.redo)
        act_del = menu.addAction("Delete", self.delete_selected)
        act_del.setEnabled(has_w or token.startswith("screen:"))
        if has_w:
            found = self.design.find_widget(token.split(":", 1)[1])
            if found is not None and str(found[1].get("widget") or "") == "keyboard":
                menu.addSeparator()
                menu.addAction("Call Keyboard", lambda w=found[1]: self._call_keyboard(w))
        menu.addSeparator()
        menu.addAction("Show Grid", lambda: self._act_show_grid.setChecked(True))
        menu.addAction("Hide Grid", lambda: self._act_show_grid.setChecked(False))
        menu.addAction("Snap to Grid", lambda: self._act_snap.setChecked(True))
        menu.addAction("Dont Snap", lambda: self._act_snap.setChecked(False))
        menu.addAction("Show Hidden Widgets", lambda: self._act_show_hidden.setChecked(True))
        menu.addAction("Hide Hidden Widgets", lambda: self._act_show_hidden.setChecked(False))
        menu.exec(self.canvas.mapToGlobal(pos))

    def _clear_inspector(self) -> None:
        self._geom = {}
        self._choices = {}
        self._event_boxes = {}
        while self.insp_form.rowCount():
            self.insp_form.removeRow(0)

    def _rebuild_inspector(self) -> None:
        self._suspend = True
        self._clear_inspector()
        token = self.canvas.selected()
        if token == "design":
            self._fill_props(DESIGN_PROPS, self.design.data, design_level=True)
        elif token.startswith("screen:"):
            sc = self.design.screen_by_id(token.split(":", 1)[1])
            if sc is not None:
                self._fill_props(SCREEN_PROPS, sc, screen=sc)
        elif token.startswith("widget:"):
            found = self.design.find_widget(token.split(":", 1)[1])
            if found is not None:
                _sc, inst = found
                spec = spec_for(str(inst.get("widget") or ""))
                self._fill_props(spec.get("props") or [], inst, widget=inst)
                if str(inst.get("widget") or "") == "keyboard":
                    btn = QPushButton("Call")
                    btn.setCursor(Qt.CursorShape.PointingHandCursor)
                    btn.clicked.connect(lambda _=False, w=inst: self._call_keyboard(w))
                    self._compact(btn)
                    self._add_row("Call", btn)
        self._suspend = False
        self._fit_inspector_height()
        QTimer.singleShot(0, self._fit_inspector_height)

    def _field_label(self, label: str, *, accent: bool = False) -> QLabel:
        colors = studio_colors()
        lab = QLabel(label)
        lab.setWordWrap(True)
        if accent:
            lab.setStyleSheet(f"color:{ACCENT}; font-weight:700;")
        else:
            lab.setStyleSheet(f"color:{colors['muted']};")
        return lab

    def _add_row(self, label: str, editor: QWidget, *, accent: bool = False, help_key: str | None = None) -> None:
        row = QWidget()
        lab = self._field_label(label, accent=accent)
        editor.setMinimumHeight(ROW_H)
        editor.setMaximumHeight(ROW_H + 2)
        if len(label) > 20:
            row.setMinimumHeight(ROW_H * 2 + 8)
            vl = QVBoxLayout(row)
            vl.setContentsMargins(0, 2, 0, 2)
            vl.setSpacing(2)
            vl.addWidget(lab)
            vl.addWidget(editor)
        else:
            row.setFixedHeight(ROW_H + 4)
            hl = QHBoxLayout(row)
            hl.setContentsMargins(0, 0, 0, 0)
            hl.setSpacing(6)
            lab.setMinimumWidth(108)
            lab.setFixedHeight(ROW_H)
            hl.addWidget(lab)
            hl.addWidget(editor, 1)
        if help_key:
            self._wire_notes(lab, help_key)
            self._wire_notes(editor, help_key)
        self.insp_form.addRow(row)

    def _add_tall_row(self, label: str, editor: QWidget, height: int, *, help_key: str | None = None) -> None:
        row = QWidget()
        row.setMinimumHeight(height + ROW_H)
        vl = QVBoxLayout(row)
        vl.setContentsMargins(0, 2, 0, 2)
        vl.setSpacing(2)
        lab = self._field_label(label)
        editor.setMinimumHeight(height - 4)
        vl.addWidget(lab)
        vl.addWidget(editor)
        if help_key:
            self._wire_notes(lab, help_key)
            self._wire_notes(editor, help_key)
        self.insp_form.addRow(row)

    def _compact(self, ed: QWidget) -> None:
        ed.setFixedHeight(ROW_H)
        ed.setStyleSheet(
            f"min-height:{ROW_H - 2}px; max-height:{ROW_H}px; padding:0 4px;"
        )

    def _fill_props(self, props, target: dict, *, design_level=False, screen=None, widget=None) -> None:
        for prop in props:
            key, label, kind = prop[0], prop[1], prop[2]
            opts = prop[3] if len(prop) > 3 else None
            if design_level:
                val = get_path(target, key)
            else:
                val = target.get(key)
            if kind == "events":
                spec = spec_for(str((widget or {}).get("widget") or ""))
                self._add_events_row(spec.get("events") or [], widget)
                continue
            if kind == "bool":
                ed = ChoiceRow([("On", True), ("Off", False)], bool(val))
                ed.changed.connect(
                    lambda v, k=key: self._set_value(
                        k, bool(v), design_level, widget, screen
                    )
                )
                if key in ("bold", "italic") and widget is not None:
                    face = str(widget.get("font_type") or "default")
                    allowed = load_font_catalog(self.design.data).styles_for(face)
                    ed.setEnabled(key in allowed)
                    if key not in allowed:
                        ed.setToolTip(f"This font has no {key} style.")
                self._choices[key] = ed
            elif kind == "int":
                ed = QSpinBox()
                lo, hi = 0, 4000
                if isinstance(opts, tuple) and len(opts) == 2 and all(
                    isinstance(n, (int, float)) and not isinstance(n, bool) for n in opts
                ):
                    lo, hi = int(opts[0]), int(opts[1])
                elif key == "selected" and widget is not None and str(widget.get("widget") or "") == "choice":
                    count = len(widget.get("items") or [])
                    lo, hi = -1, max(-1, count - 1)
                elif key in ("min", "max", "value"):
                    lo, hi = -100000, 100000
                elif key == "step":
                    lo, hi = 1, 100000
                elif key == "thickness":
                    lo, hi = 1, 40
                elif key == "max_length":
                    lo, hi = 0, 10000
                ed.setRange(lo, hi)
                if key == "selected" and str((widget or {}).get("widget") or "") == "choice":
                    ed.setToolTip("0 is the first item. -1 means none.")
                elif key == "ticks":
                    ed.setToolTip("Number of intervals between the marks. 10 gives 11 marks.")
                elif key == "diameter":
                    ed.setToolTip("Circle size in pixels. 0 draws the largest circle that fits. 1 to 19 are refused.")
                elif key == "sweep":
                    ed.setToolTip("Angle of the scale in degrees. 270 is three quarters of a circle.")
                elif key == "points":
                    ed.setToolTip("How many values are shown across the width.")
                elif key == "bars":
                    ed.setToolTip("How many bars there are. Lowering this keeps extra entries, with a warning.")
                elif key == "update_ms":
                    ed.setToolTip(
                        "Redraw at most this often, in milliseconds. "
                        "Very small values can make the rest of the program slow."
                    )
                ed.setValue(int(val if val is not None else 0))
                self._compact(ed)
                ed.valueChanged.connect(
                    lambda v, k=key: self._set_value(k, int(v), design_level, widget, screen)
                )
                if key in ("x", "y", "w", "h", "width", "height"):
                    self._geom[key] = ed
                self._choices[key] = ed
            elif kind == "number":
                ed = JsonNumberBox()
                if isinstance(opts, tuple) and len(opts) == 2:
                    ed.setRange(float(opts[0]), float(opts[1]))
                if isinstance(val, (int, float)) and not isinstance(val, bool):
                    ed.setValue(float(val))
                else:
                    ed.setValue(0)
                if key == "step":
                    ed.setToolTip("Amount added or subtracted by one tap. Must be greater than 0.")
                self._compact(ed)

                def commit_number(v: float, k=key) -> None:
                    parsed = parse_json_number(format_json_number(v))
                    self._set_value(k, 0 if parsed is None else parsed, design_level, widget, screen)

                ed.valueChanged.connect(commit_number)
                self._choices[key] = ed
            elif kind == "entries":
                numeric = opts == "number"
                is_bar_list = (
                    widget is not None
                    and str(widget.get("widget") or "") == "barchart"
                    and key in ("labels", "values")
                )
                if is_bar_list:

                    def count_of(w=widget) -> int:
                        try:
                            return int(w.get("bars") or 1)
                        except (TypeError, ValueError):
                            return 1

                    ed = BarRowsEditor(list(val or []), numeric=numeric, count_fn=count_of)
                else:
                    ed = EntryListEditor(list(val or []), numeric=numeric)
                ed.changed.connect(
                    lambda v, k=key: self._set_value(k, v, design_level, widget, screen)
                )
                ed.refused.connect(self._set_status)
                self._add_tall_row(label, ed, 120, help_key=key)
                continue
            elif kind == "image":
                self._add_image_source_row(str(val or ""), widget, screen)
                continue
            elif kind == "color":
                self._add_color_row(label, str(val or ""), key, design_level, widget, screen)
                continue
            elif kind in ("font_type", "font_size"):
                catalog = load_font_catalog(self.design.data)
                if kind == "font_type":
                    current = str(val or "default").strip() or "default"
                    ed = PickRow(type_items(catalog, current), current)
                else:
                    face = str((widget or {}).get("font_type") or "default")
                    current = val if val is not None and str(val) != "" else "default"
                    if str(current).lower() == "default":
                        current = "default"
                    else:
                        try:
                            current = int(current)
                        except (TypeError, ValueError):
                            current = str(current)
                    ed = PickRow(size_items(catalog, face), current)
                ed.changed.connect(
                    lambda v, k=key: self._set_value(k, v, design_level, widget, screen)
                )
                self._choices[key] = ed
            elif kind == "readonly":
                ed = QLineEdit("" if val is None else str(val))
                ed.setReadOnly(True)
                ed.setToolTip("Written by picker.py.")
                self._compact(ed)
            elif kind == "tree_path":
                paths = tree_leaf_paths(val if key == "items" else (widget or {}).get("items"))
                current = "" if val is None else str(val)
                options: list[tuple[str, str]] = [("(none)", "")]
                for path in paths:
                    options.append((path, path))
                if current and current not in paths:
                    options.append((current, current))
                ed = PickRow(options, current)
                ed.setToolTip("Path of the last end item chosen, for example Network/WiFi.")
                ed.changed.connect(
                    lambda v, k=key: self._set_value(k, str(v or ""), design_level, widget, screen)
                )
                self._choices[key] = ed
            elif kind == "select":
                ed = ChoiceRow([(choice_label(o), o) for o in (opts or [])], val)
                ed.changed.connect(
                    lambda v, k=key: self._set_value(k, v, design_level, widget, screen)
                )
                self._choices[key] = ed
            elif kind == "multiline":
                ed = FinishPlainText()
                ed.setPlainText(str(val if val is not None else ""))
                ed.setTabChangesFocus(True)
                ed.editingFinished.connect(
                    lambda e=ed, k=key: self._set_value(
                        k, e.toPlainText(), design_level, widget, screen
                    )
                )
                self._add_tall_row(label, ed, 72, help_key=key)
                continue
            elif kind in ("lines", "tree_items"):
                to_text = items_to_lines if kind == "lines" else tree_to_text
                from_text = lines_to_items if kind == "lines" else text_to_tree
                ed = FinishPlainText()
                ed.setPlainText(to_text(val))
                ed.setTabChangesFocus(True)
                if kind == "lines":
                    ed.setToolTip("One item per line.")
                else:
                    ed.setToolTip("One item per line. Indent two spaces per level.")
                ed.editingFinished.connect(
                    lambda e=ed, k=key, f=from_text: self._set_value(
                        k, f(e.toPlainText()), design_level, widget, screen
                    )
                )
                self._add_tall_row(label, ed, 96, help_key=key)
                continue
            elif kind == "border":
                self._add_border_editor(
                    target if widget is None and screen is None else (widget or screen or target),
                    widget,
                    screen,
                )
                continue
            elif kind == "id":
                ed = QLineEdit(str(val or ""))
                self._compact(ed)
                ed.editingFinished.connect(
                    lambda e=ed, k=key: self._set_id(e.text().strip(), widget, screen)
                )
                self._choices[key] = ed
            else:
                ed = QLineEdit(str(val if val is not None else ""))
                self._compact(ed)
                ed.editingFinished.connect(
                    lambda e=ed, k=key: self._set_value(
                        k, e.text(), design_level, widget, screen
                    )
                )
                self._choices[key] = ed
            self._add_row(label, ed, help_key=key)

    def _add_events_row(self, events, inst) -> None:
        if inst is None:
            return
        if not events:
            lab = QLabel("none")
            lab.setFixedHeight(ROW_H)
            self._add_row("Event", lab, accent=True, help_key="events")
            return
        current = list(inst.get("events") or [])
        host = QWidget()
        hl = QHBoxLayout(host)
        hl.setContentsMargins(0, 0, 0, 0)
        hl.setSpacing(8)
        boxes = []
        for ev, desc in events:
            box = QCheckBox(ev)
            box.setToolTip(desc)
            box.setChecked(ev in current)
            box.setStyleSheet(f"font-weight:700; color:{ACCENT};")
            self._compact(box)
            boxes.append((ev, box))
            self._event_boxes[ev] = box
            hl.addWidget(box)
        hl.addStretch(1)

        def toggled(_checked: bool) -> None:
            if self._suspend:
                return
            chosen = [name for name, box in boxes if box.isChecked()]
            if chosen == list(inst.get("events") or []):
                return
            # Routed through _set_value (rather than mutating inst directly, as before) so
            # events get the same undo/dirty/recording treatment as every other property --
            # this used to be the one property change the recorder could not see at all.
            self._set_value("events", chosen, False, inst, None)

        for _ev, box in boxes:
            box.toggled.connect(toggled)
        self._add_row("Event", host, accent=True, help_key="events")

    def _add_color_row(self, label, value, key, design_level, widget, screen, apply=None) -> None:
        row = QWidget()
        hl = QHBoxLayout(row)
        hl.setContentsMargins(0, 0, 0, 0)
        hl.setSpacing(4)
        le = QLineEdit(str(value or ""))
        self._compact(le)
        self._paint_color_field(le, str(value or ""))
        btn = QPushButton("Pick")
        btn.setFixedSize(48, ROW_H)
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.setStyleSheet(
            f"QPushButton {{ min-height:{ROW_H - 4}px; max-height:{ROW_H}px; padding:0 6px; "
            f"background:{studio_colors()['field']}; color:{studio_colors()['title']}; "
            f"border:1px solid {studio_colors()['line']}; border-radius:8px; }}"
            f"QPushButton:hover {{ background:{ORANGE}; color:{ORANGE_INK}; }}"
        )

        def apply_color(text: str) -> None:
            allow = (
                widget is not None
                and key == "background"
                and str(widget.get("widget") or "") in TRANSPARENT_BACKGROUNDS
            )
            canon = canonical_color(text, allow_transparent=allow)
            if canon is None:
                extra = (
                    " Transparent is also allowed here."
                    if allow
                    else " Transparent is only for Switch, Checkbox, and Stepper."
                )
                named = ", ".join(SCHEMA_COLORS)
                self._set_status(f"Colour must be {named}, or #rrggbb." + extra)
                QTimer.singleShot(0, self._rebuild_inspector)
                return
            self._paint_color_field(le, canon)
            if le.text() != canon:
                le.blockSignals(True)
                le.setText(canon)
                le.blockSignals(False)
            if apply is not None:
                apply(canon)
            else:
                self._set_value(key, canon, design_level, widget, screen)

        def pick(_=False, line=le):
            start = QColor(resolve_color(line.text()))
            if not start.isValid():
                start = QColor("#ffffff")
            c = self._pick_color(start, label or "Colour")
            if c.isValid():
                line.setText(c.name())
                apply_color(c.name())

        def commit(line=le):
            apply_color(line.text().strip())

        btn.clicked.connect(pick)
        le.editingFinished.connect(commit)
        hl.addWidget(le, 1)
        hl.addWidget(btn)
        self._add_row(label, row, help_key=key)

    def _pick_color(self, start: QColor, title: str = "Colour") -> QColor:
        dlg = QColorDialog(start, self)
        dlg.setWindowTitle(title)
        dlg.setOption(QColorDialog.ColorDialogOption.DontUseNativeDialog, True)
        dlg.setWindowModality(Qt.WindowModality.WindowModal)
        if dlg.exec() == QColorDialog.DialogCode.Accepted:
            c = dlg.currentColor()
            return c if c.isValid() else QColor()
        return QColor()

    @staticmethod
    def _color_fg(hex_color: str) -> str:
        c = QColor(hex_color)
        if not c.isValid():
            return "#000000"
        y = 0.299 * c.red() + 0.587 * c.green() + 0.114 * c.blue()
        return "#000000" if y >= 140 else "#ffffff"

    def _paint_color_field(self, line: QLineEdit, color: str) -> None:
        hex_c = resolve_color(color)
        c = QColor(hex_c)
        if c.isValid():
            fg = self._color_fg(c.name())
            line.setStyleSheet(
                f"QLineEdit {{ background-color:{c.name()}; color:{fg}; "
                f"min-height:{ROW_H - 4}px; max-height:{ROW_H}px; padding:0 4px; }}"
            )
        else:
            line.setStyleSheet(
                f"QLineEdit {{ min-height:{ROW_H - 4}px; max-height:{ROW_H}px; padding:0 4px; }}"
            )

    def _add_border_editor(self, target: dict, widget, screen) -> None:
        border = target.get("border")
        if not isinstance(border, dict):
            border = {"color": "black", "width": 1}
            target["border"] = border

        def apply_border_color(text: str) -> None:
            if self._suspend:
                return
            self._push_undo()
            box = target.get("border")
            if not isinstance(box, dict):
                box = {"color": "black", "width": 1}
                target["border"] = box
            box["color"] = text or "black"
            self._after_edit(widget, screen)

        self._add_color_row(
            "Border colour",
            str(border.get("color") or "black"),
            "border",
            False,
            widget,
            screen,
            apply=apply_border_color,
        )
        width = QSpinBox()
        width.setRange(0, 20)
        width.setValue(int(border.get("width") or 0))
        self._compact(width)

        def apply_width(v: int) -> None:
            if self._suspend:
                return
            self._push_undo()
            box = target.get("border")
            if not isinstance(box, dict):
                box = {"color": "black", "width": 1}
                target["border"] = box
            box["width"] = int(v)
            self._after_edit(widget, screen)

        width.valueChanged.connect(apply_width)
        self._add_row("Border width", width, help_key="border")

    def _add_image_source_row(self, value: str, widget, screen) -> None:
        row = QWidget()
        hl = QHBoxLayout(row)
        hl.setContentsMargins(0, 0, 0, 0)
        hl.setSpacing(4)
        le = QLineEdit(str(value or ""))
        self._compact(le)
        btn = QPushButton("Browse")
        btn.setFixedSize(64, ROW_H)
        btn.setCursor(Qt.CursorShape.PointingHandCursor)

        def commit(line=le):
            self._set_value("source", line.text().strip(), False, widget, screen)
            self.canvas._pix_cache.pop(line.text().strip(), None)

        def browse(_=False, line=le):
            path, _filt = QFileDialog.getOpenFileName(
                self,
                "Image",
                str(Path.home()),
                "Images (*.png *.jpg *.jpeg *.bmp *.PNG *.JPG *.JPEG *.BMP);;All files (*)",
            )
            if path:
                line.setText(path)
                commit()

        btn.clicked.connect(browse)
        le.editingFinished.connect(commit)
        hl.addWidget(le, 1)
        hl.addWidget(btn)
        self._add_row("Source", row, help_key="source")

    def _call_keyboard(self, inst: dict) -> None:
        if not inst or str(inst.get("widget") or "") != "keyboard":
            return
        self.canvas.start_keyboard_call(inst)
        self._set_status("Keyboard called. Type, then Enter. Esc cancels.")

    def _on_keyboard_finished(self, target: str, text: str) -> None:
        if target:
            found = self.design.find_widget(target)
            if found is None:
                self._set_status(f"Keyboard target {target} was not found.")
            else:
                self._push_undo()
                found[1]["text"] = text
                self._mark_dirty()
                self._set_status(f"Keyboard sent text to {target}.")
        else:
            self._set_status("Keyboard had no target.")
        self._refresh_tree()
        self.canvas.update()
        self._rebuild_inspector()

    def _on_image_dropped(self, src: str, x: int, y: int) -> None:
        sid = self.canvas.active_screen_id
        if not sid:
            return
        under = None
        for inst in reversed(self.design.widgets_on(sid)):
            if str(inst.get("widget") or "") != "image":
                continue
            if not inst.get("visible", True):
                continue
            ix = int(inst.get("x") or 0)
            iy = int(inst.get("y") or 0)
            iw = int(inst.get("w") or 0)
            ih = int(inst.get("h") or 0)
            if ix <= int(x) < ix + iw and iy <= int(y) < iy + ih:
                under = inst
                break
        if under is not None:
            self._push_undo()
            under["source"] = src
            self.canvas._pix_cache.pop(src, None)
            self._mark_dirty()
            self.canvas.update()
            self._rebuild_inspector()
            self._set_status("Image source updated.")
            return
        before = copy.deepcopy(self.design.data)
        try:
            inst = self.design.add_widget(sid, "image", x, y)
        except (KeyError, ValueError) as exc:
            QMessageBox.warning(self, "Drop", str(exc))
            return
        inst["source"] = src
        self._undo.append(before)
        if len(self._undo) > 40:
            self._undo.pop(0)
        self._redo.clear()
        self._mark_dirty()
        self._refresh_tree()
        self.canvas.update()
        self.canvas.select(f"widget:{inst.get('id')}")
        self._set_status("Image added.")

    def _set_value(self, key, value, design_level, widget, screen) -> None:
        if self._suspend:
            return
        self._recorder.log(
            "set",
            key=key,
            value=value,
            widget=(widget or {}).get("id"),
            screen=(screen or {}).get("id"),
            design_level=design_level,
        )
        if widget is not None and key in ("x", "y", "w", "h"):
            trial = {
                "widget": widget.get("widget"),
                "id": widget.get("id"),
                "x": int(widget.get("x") or 0),
                "y": int(widget.get("y") or 0),
                "w": int(widget.get("w") or 0),
                "h": int(widget.get("h") or 0),
            }
            trial[key] = int(value)
            found = self.design.find_widget(str(widget.get("id") or ""))
            sid = self.canvas.active_screen_id
            if found is not None:
                sid = str(found[0].get("id") or sid)
            sw, sh = self.design.screen_size(sid)
            clamp_widget(trial, sw, sh)
            if not geometry_allowed(trial):
                self._sync_geom_fields()
                kind = str(widget.get("widget") or "")
                if kind == "line":
                    self._set_status("A Line cannot have width 0 and height 0.")
                elif kind in ("slider", "progressbar"):
                    self._set_status("Width and height cannot be equal.")
                else:
                    self._set_status("That size is not allowed.")
                return
            other = overlapping_interactive(self.design, sid, trial)
            if other is not None:
                self._sync_geom_fields()
                self._set_status(overlap_text(other))
                return
            self._push_undo()
            for geom_key in ("x", "y", "w", "h"):
                widget[geom_key] = trial[geom_key]
            self._after_edit(widget, screen)
            return
        if widget is not None and key in (
            "min",
            "max",
            "value",
            "step",
            "thickness",
            "max_length",
            "layout",
            "items",
            "labels",
            "values",
            "selected",
            "style",
            "orientation",
            "scale",
            "ticks",
            "diameter",
            "sweep",
            "points",
            "bars",
            "update_ms",
        ):
            if key in ("items", "labels", "values") and value == widget.get(key):
                return
            trial = copy.deepcopy(widget)
            trial[key] = value
            kind_name = str(widget.get("widget") or "")
            if key == "items" and kind_name == "choice":
                last = len(value) - 1
                try:
                    cur = int(trial.get("selected") if trial.get("selected") is not None else 0)
                except (TypeError, ValueError):
                    cur = 0
                trial["selected"] = max(-1, min(cur, last))
            if key == "items" and kind_name == "tree":
                sel = str(trial.get("selected") or "")
                if sel and sel not in set(tree_leaf_paths(value if isinstance(value, list) else [])):
                    trial["selected"] = ""
            err = normalize_typed_values(trial)
            if err:
                self._set_status(err)
                QTimer.singleShot(0, self._rebuild_inspector)
                return
            self._push_undo()
            for k in list(widget.keys()):
                if k not in trial:
                    widget.pop(k, None)
            for k, v in trial.items():
                widget[k] = v
            self._after_edit(widget, screen)
            self._note_widget_warning(f"widget:{widget.get('id')}")
            if key in ("items", "bars"):
                QTimer.singleShot(0, self._rebuild_inspector)
            return
        self._push_undo()
        if widget is not None and key == "source":
            self.canvas._pix_cache.pop(str(widget.get("source") or ""), None)
            self.canvas._pix_cache.pop(str(value or ""), None)
        if design_level:
            if key.endswith(".width") or key.endswith(".height"):
                value = int(value)
            set_path(self.design.data, key, value)
        elif widget is not None:
            widget[key] = value
            sw, sh = self.design.screen_size(self.canvas.active_screen_id)
            clamp_widget(widget, sw, sh)
            if key == "font_type":
                self._apply_font_choice(widget, str(value or "default"))
                self._after_edit(widget, screen)
                QTimer.singleShot(0, self._rebuild_inspector)
                return
        elif screen is not None:
            screen[key] = value
            if key == "orientation":
                self.design.apply_orientation(screen)
                self.canvas._apply_board_size()
                self._sync_screen_geom(screen)
                self._after_edit(widget, screen)
                return
            if key in ("width", "height"):
                self.design.sync_orientation_from_size(screen)
                self.canvas._apply_board_size()
                ch = self._choices.get("orientation")
                if ch is not None:
                    ch.set_value(screen.get("orientation"))
                self._after_edit(widget, screen)
                return
        self._after_edit(widget, screen)
        if widget is not None:
            self._note_widget_warning(f"widget:{widget.get('id')}")

    def _apply_font_choice(self, widget: dict, name: str) -> None:
        """Keep font_size and bold/italic inside the chosen face. Saved on the widget."""
        catalog = load_font_catalog(self.design.data)
        if not catalog.size_allowed(name, widget.get("font_size")):
            widget["font_size"] = "default"
        allowed = set(catalog.styles_for(name))
        if "bold" not in allowed:
            widget["bold"] = False
        if "italic" not in allowed:
            widget["italic"] = False

    def _id_error(self, msg: str) -> None:
        QMessageBox.warning(self, "ID", msg)
        self._rebuild_inspector()

    def _set_id(self, new_id: str, widget, screen) -> None:
        if self._suspend:
            return
        old = ""
        if widget is not None:
            old = str(widget.get("id") or "")
        elif screen is not None:
            old = str(screen.get("id") or "")
        if new_id == old:
            return
        if not is_python_id(new_id):
            QTimer.singleShot(
                0,
                lambda: self._id_error(
                    "IDs must be valid Python names, for example test_button."
                ),
            )
            return
        if new_id in self.design.all_ids():
            QTimer.singleShot(
                0,
                lambda: self._id_error(f"The ID {new_id} is already used in this Design."),
            )
            return
        # Recorded (for Understudy): without this line a later "set" aimed at the NEW id could not be found when the
        # recording is replayed, because Replay never learned that the widget/screen had been renamed.
        self._recorder.log(
            "set", key="id", value=new_id,
            widget=old if widget is not None else None,
            screen=old if (widget is None and screen is not None) else None,
            design_level=False,
        )
        self._push_undo()
        if widget is not None:
            widget["id"] = new_id
            token = f"widget:{new_id}"
        else:
            screen["id"] = new_id
            if self.canvas.active_screen_id == old:
                self.canvas.active_screen_id = new_id
            token = f"screen:{new_id}"
        self.canvas.select(token, notify=False)
        QTimer.singleShot(0, lambda: self._after_edit(widget, screen))

    def _after_edit(self, widget, screen) -> None:
        self._mark_dirty()
        self._refresh_tree()
        self.canvas._apply_board_size()
        self.canvas.update()
        if widget is None and screen is None:
            self._refresh_title()
        if screen is not None:
            sw, sh = self.design.screen_size(str(screen.get("id") or ""))
            ori = str(screen.get("orientation") or "")
            self._set_status(f"Screen {screen.get('id')}  {sw} x {sh}  {ori}")
        elif widget is not None:
            self._set_status(
                f"{widget.get('id')}  X:{widget.get('x')} Y:{widget.get('y')}  "
                f"{widget.get('w')} x {widget.get('h')}"
            )
