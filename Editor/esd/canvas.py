"""Canvas: one Screen at a time, widgets inside it. Board is unbounded."""

from __future__ import annotations

import math
import uuid
from pathlib import Path

from PyQt6.QtCore import QPoint, QRect, QRectF, QUrl, Qt, pyqtSignal
from PyQt6.QtGui import (
    QColor,
    QFont,
    QFontMetrics,
    QImage,
    QPainter,
    QPainterPath,
    QPen,
    QPixmap,
)
from PyQt6.QtWidgets import QWidget

from esd.catalogue import keyboard_rows, resolve_color
from esd.fonts import load_font_catalog
from esd.model import Design, clamp_widget, geometry_allowed, overlap_text, overlapping_interactive
from wattle_theme import ACCENT, studio_colors

WIDGET_MIME = "application/x-esd-widget"
HANDLE = 10
MEMO_SB_W = 8
# Four corners plus east and south - move and resize both work.
HANDLE_KEYS = ("nw", "n", "ne", "w", "e", "sw", "s", "se")


class DesignCanvas(QWidget):
    selectionChanged = pyqtSignal(str)  # "design" | "screen:<id>" | "widget:<id>"
    widgetsChanged = pyqtSignal()
    widgetDropped = pyqtSignal(str, int, int)
    dragAboutToStart = pyqtSignal()
    dragFinished = pyqtSignal()
    overlapBlocked = pyqtSignal(str)
    imageDropped = pyqtSignal(str, int, int)
    keyboardFinished = pyqtSignal(str, str)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.design = Design()
        self.active_screen_id = ""
        self._selected = "design"
        self._drag = None
        self._memo_scroll: dict[str, int] = {}
        self._pix_cache: dict[str, QPixmap] = {}
        self._kb_session: dict | None = None
        self.show_grid = True
        self.show_hidden = True
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.snap = True
        self.grid_size = 8
        self.setMouseTracking(True)
        self.setAcceptDrops(True)
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.setMinimumSize(400, 300)
        self._apply_board_size()

    def set_design(self, design: Design, screen_id: str | None = None) -> None:
        self.design = design
        if screen_id:
            sc = design.screen_by_id(screen_id)
        else:
            sc = design.screen_by_id(self.active_screen_id) or design.first_screen()
        self.active_screen_id = str(sc.get("id") or "") if sc else ""
        self._apply_board_size()
        self.update()

    def _apply_board_size(self) -> None:
        sw, sh = self.design.screen_size(self.active_screen_id)
        self.setMinimumSize(max(400, sw + 80), max(300, sh + 80))

    def screen_origin(self) -> QPoint:
        sw, sh = self.design.screen_size(self.active_screen_id)
        x = max(24, (self.width() - sw) // 2)
        y = max(28, (self.height() - sh) // 2)
        return QPoint(x, y)

    def screen_rect(self) -> QRect:
        sw, sh = self.design.screen_size(self.active_screen_id)
        o = self.screen_origin()
        return QRect(o.x(), o.y(), sw, sh)

    def select(self, token: str, *, notify: bool = True) -> None:
        self._selected = token
        if notify:
            self.selectionChanged.emit(token)
        self.update()

    def selected(self) -> str:
        return self._selected

    def _snap(self, v: int) -> int:
        if not self.snap or self.grid_size <= 0:
            return int(v)
        g = int(self.grid_size)
        return int(round(int(v) / g) * g)

    def _widget_canvas_rect(self, inst: dict) -> QRect:
        sr = self.screen_rect()
        return QRect(
            sr.x() + int(inst.get("x") or 0),
            sr.y() + int(inst.get("y") or 0),
            int(inst.get("w") or 0),
            int(inst.get("h") or 0),
        )

    def _interact_rect(self, inst: dict) -> QRect:
        r = self._widget_canvas_rect(inst)
        if str(inst.get("widget") or "") != "line":
            return r
        t = max(8, int(inst.get("thickness") or 1) + 4)
        if r.width() < t:
            extra = t - max(1, r.width())
            r = QRect(r.x() - extra // 2, r.y(), max(1, r.width()) + extra, max(1, r.height()))
        if r.height() < t:
            extra = t - max(1, r.height())
            r = QRect(r.x(), r.y() - extra // 2, max(1, r.width()), max(1, r.height()) + extra)
        return r

    def _handle_rects(self, r: QRect) -> dict[str, QRect]:
        hs = HANDLE
        cx = r.center().x()
        cy = r.center().y()

        def box(x: int, y: int) -> QRect:
            return QRect(x - hs // 2, y - hs // 2, hs, hs)

        return {
            "nw": box(r.left(), r.top()),
            "n": box(cx, r.top()),
            "ne": box(r.right(), r.top()),
            "w": box(r.left(), cy),
            "e": box(r.right(), cy),
            "sw": box(r.left(), r.bottom()),
            "s": box(cx, r.bottom()),
            "se": box(r.right(), r.bottom()),
        }

    def _selected_widget(self) -> dict | None:
        if not self._selected.startswith("widget:"):
            return None
        found = self.design.find_widget(self._selected.split(":", 1)[1])
        return None if found is None else found[1]

    def hit_test(self, pos: QPoint) -> tuple[str, str]:
        """Return (token, mode) where mode is handle key, 'move', 'screen', or 'board'."""
        inst = self._selected_widget()
        if inst is not None and self._editor_visible(inst):
            r = self._interact_rect(inst)
            for key, hr in self._handle_rects(r).items():
                if hr.contains(pos):
                    return f"widget:{inst.get('id')}", key
        widget = self._widget_at(pos)
        if widget is not None:
            return f"widget:{widget.get('id')}", "move"
        if self.screen_rect().contains(pos) and self.active_screen_id:
            return f"screen:{self.active_screen_id}", "screen"
        return "design", "board"

    def _widget_at(self, pos: QPoint) -> dict | None:
        sr = self.screen_rect()
        if not sr.contains(pos):
            return None
        lx = pos.x() - sr.x()
        ly = pos.y() - sr.y()
        for inst in reversed(self.design.widgets_on(self.active_screen_id)):
            if not self._editor_visible(inst):
                continue
            r = QRect(
                int(inst.get("x") or 0),
                int(inst.get("y") or 0),
                int(inst.get("w") or 0),
                int(inst.get("h") or 0),
            )
            if str(inst.get("widget") or "") == "line":
                t = max(8, int(inst.get("thickness") or 1) + 4)
                if r.width() < t:
                    extra = t - max(1, r.width())
                    r = QRect(r.x() - extra // 2, r.y(), max(1, r.width()) + extra, max(1, r.height()))
                if r.height() < t:
                    extra = t - max(1, r.height())
                    r = QRect(r.x(), r.y() - extra // 2, max(1, r.width()), max(1, r.height()) + extra)
            if r.contains(lx, ly):
                return inst
        return None

    def _screen_bg(self) -> QColor:
        sc = self.design.screen_by_id(self.active_screen_id)
        return QColor(resolve_color(str((sc or {}).get("background") or "black")))

    @staticmethod
    def _luma(color: QColor) -> float:
        return 0.299 * color.red() + 0.587 * color.green() + 0.114 * color.blue()

    def _contrast_on_screen(self) -> QColor:
        """Resize handles: yellow on dark Screens, navy on light Screens."""
        if self._luma(self._screen_bg()) < 140:
            return QColor("#ffd400")
        return QColor("#1b2a4a")

    def _grid_pen_color(self) -> QColor:
        if self._luma(self._screen_bg()) < 140:
            return QColor(220, 220, 220, 48)
        return QColor(40, 50, 60, 40)

    def paintEvent(self, _event) -> None:  # noqa: N802
        c = studio_colors()
        p = QPainter(self)
        p.fillRect(self.rect(), QColor(c["canvas"]))

        sr = self.screen_rect()
        bg = self._screen_bg()
        p.fillRect(sr, bg)
        selected_screen = self._selected == f"screen:{self.active_screen_id}"
        p.setPen(QPen(QColor(ACCENT if selected_screen else c["line"]), 2 if selected_screen else 1))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawRect(sr)

        sid = str((self.design.screen_by_id(self.active_screen_id) or {}).get("id") or self.active_screen_id)
        if sid:
            p.setPen(QColor(c["muted"]))
            font = QFont()
            font.setPixelSize(11)
            p.setFont(font)
            p.drawText(
                QRect(sr.x(), sr.y() - 22, sr.width(), 20),
                int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter),
                sid,
            )

        if self.show_grid and sr.width() > 0 and sr.height() > 0:
            p.save()
            p.setClipRect(sr)
            pen = QPen(self._grid_pen_color(), 1, Qt.PenStyle.SolidLine)
            pen.setCosmetic(True)
            p.setPen(pen)
            p.setRenderHint(QPainter.RenderHint.Antialiasing, False)
            g = max(1, int(self.grid_size))
            x = sr.x()
            while x <= sr.right():
                p.drawLine(x, sr.y(), x, sr.bottom())
                x += g
            y = sr.y()
            while y <= sr.bottom():
                p.drawLine(sr.x(), y, sr.right(), y)
                y += g
            p.restore()

        p.setClipRect(sr)
        if self._kb_session is not None:
            self._paint_keyboard_call(p, sr)
        else:
            widgets = self.design.widgets_on(self.active_screen_id)
            for inst in widgets:
                if inst.get("visible", True):
                    self._paint_widget(p, sr, inst)
            if self.show_hidden:
                for inst in widgets:
                    if not inst.get("visible", True):
                        self._paint_hidden_outline(p, sr, inst)
        p.setClipping(False)

        if self._kb_session is None:
            inst = self._selected_widget()
            if inst is not None and self._editor_visible(inst):
                r = self._interact_rect(inst)
                hc = self._contrast_on_screen()
                outline = QColor("#111111") if self._luma(hc) >= 140 else QColor("#ffffff")
                p.setPen(QPen(hc, 2))
                p.setBrush(Qt.BrushStyle.NoBrush)
                p.drawRect(r.adjusted(-2, -2, 2, 2))
                for hr in self._handle_rects(r).values():
                    p.fillRect(hr, hc)
                    p.setPen(QPen(outline, 1))
                    p.setBrush(Qt.BrushStyle.NoBrush)
                    p.drawRect(hr)

    def _widget_font(self, inst: dict) -> QFont:
        cat = load_font_catalog(self.design.data)
        cat.register_files()
        font = QFont()
        face = str(inst.get("font_type") or "default").strip()
        if face and face.lower() != "default":
            font.setFamily(face)
        px = cat.preview_size(face, inst.get("font_size"))
        if px is not None:
            font.setPixelSize(px)
        if inst.get("bold"):
            font.setBold(True)
        if inst.get("italic"):
            font.setItalic(True)
        return font

    @staticmethod
    def _chars_fit(fm: QFontMetrics, text: str, width: int) -> str:
        """Longest prefix of *text* whose advance fits in *width*."""
        raw = str(text or "")
        if width <= 0 or not raw:
            return ""
        if fm.horizontalAdvance(raw) <= width:
            return raw
        lo, hi = 0, len(raw)
        while lo < hi:
            mid = (lo + hi + 1) // 2
            if fm.horizontalAdvance(raw[:mid]) <= width:
                lo = mid
            else:
                hi = mid - 1
        return raw[:lo]

    @staticmethod
    def _wrap_chars(fm: QFontMetrics, text: str, width: int) -> list[str]:
        raw = str(text or "")
        if not raw:
            return [""]
        lines: list[str] = []
        for para in raw.split("\n"):
            if fm.horizontalAdvance(para) <= width:
                lines.append(para)
                continue
            buf = ""
            for ch in para:
                trial = buf + ch
                if buf and fm.horizontalAdvance(trial) > width:
                    lines.append(buf)
                    buf = ch
                else:
                    buf = trial
            lines.append(buf)
        return lines

    def _draw_fitted_text(
        self,
        p: QPainter,
        r: QRect,
        inst: dict,
        text: str,
        *,
        wrap: bool = False,
        flags: int | None = None,
    ) -> None:
        if r.width() <= 0 or r.height() <= 0:
            return
        p.save()
        p.setClipRect(r)
        p.setFont(self._widget_font(inst))
        fm = QFontMetrics(p.font())
        flag = self._text_flags(inst, wrap=False) if flags is None else flags
        if wrap:
            lines = self._wrap_chars(fm, text, r.width())
            shown = "\n".join(lines)
            p.drawText(r, int(Qt.AlignmentFlag.AlignTop | (flag & ~int(Qt.AlignmentFlag.AlignVCenter))), shown)
        else:
            shown = self._chars_fit(fm, str(text).replace("\n", " "), r.width())
            p.drawText(r, flag, shown)
        p.restore()

    def _text_flags(self, inst: dict, *, wrap: bool) -> int:
        kind = str(inst.get("widget") or "")
        default_align = "center" if kind == "button" else "left"
        align = str(inst.get("alignment") or default_align)
        flag = Qt.AlignmentFlag.AlignTop if wrap else Qt.AlignmentFlag.AlignVCenter
        if align == "left":
            flag |= Qt.AlignmentFlag.AlignLeft
        elif align == "right":
            flag |= Qt.AlignmentFlag.AlignRight
        else:
            flag |= Qt.AlignmentFlag.AlignHCenter
        return int(flag)

    def _memo_pad(self, r: QRect, *, with_sb: bool) -> QRect:
        extra = (MEMO_SB_W + 1) if with_sb else 0
        return r.adjusted(4, 2, -4 - extra, -2)

    def _memo_content_h(self, inst: dict, text_w: int) -> int:
        fm = QFontMetrics(self._widget_font(inst))
        lines = self._wrap_chars(fm, str(inst.get("text") or ""), max(1, text_w))
        return max(len(lines), 1) * fm.lineSpacing()

    def _memo_overflows(self, inst: dict, r: QRect) -> bool:
        pad = self._memo_pad(r, with_sb=True)
        return self._memo_content_h(inst, pad.width()) > pad.height()

    def _memo_scroll_max(self, inst: dict, r: QRect) -> int:
        pad = self._memo_pad(r, with_sb=True)
        return max(0, self._memo_content_h(inst, pad.width()) - pad.height())

    def _memo_offset(self, inst: dict, r: QRect) -> int:
        wid = str(inst.get("id") or "")
        mx = self._memo_scroll_max(inst, r)
        v = max(0, min(int(self._memo_scroll.get(wid, 0)), mx))
        self._memo_scroll[wid] = v
        return v

    def _set_memo_scroll(self, inst: dict, value: int, r: QRect) -> None:
        wid = str(inst.get("id") or "")
        mx = self._memo_scroll_max(inst, r)
        self._memo_scroll[wid] = max(0, min(int(value), mx))

    def _memo_scrollbar_rect(self, inst: dict, r: QRect) -> QRect | None:
        if not self._memo_overflows(inst, r):
            return None
        pad = self._memo_pad(r, with_sb=True)
        return QRect(r.right() - MEMO_SB_W - 1, pad.y(), MEMO_SB_W, max(1, pad.height()))

    def _paint_widget(self, p: QPainter, sr: QRect, inst: dict) -> None:
        kind = str(inst.get("widget") or "")
        r = QRect(
            sr.x() + int(inst.get("x") or 0),
            sr.y() + int(inst.get("y") or 0),
            int(inst.get("w") or 0),
            int(inst.get("h") or 0),
        )
        painters = {
            "button": self._paint_button_label_memo,
            "label": self._paint_button_label_memo,
            "memo": self._paint_button_label_memo,
            "switch": self._paint_switch,
            "checkbox": self._paint_checkbox,
            "choice": self._paint_choice,
            "tree": self._paint_tree,
            "slider": self._paint_slider,
            "progressbar": self._paint_progressbar,
            "gauge": self._paint_gauge,
            "stepper": self._paint_stepper,
            "waveform": self._paint_waveform,
            "barchart": self._paint_barchart,
            "image": self._paint_image,
            "line": self._paint_line,
            "keyboard": self._paint_keyboard,
        }
        fn = painters.get(kind)
        if fn is not None:
            fn(p, r, inst)

    def _dim_colors(self, fill: QColor, fg: QColor, enabled: bool) -> tuple[QColor, QColor]:
        if enabled:
            return fill, fg
        if fill.alpha() > 0:
            fill = QColor(
                (fill.red() + 140) // 2,
                (fill.green() + 140) // 2,
                (fill.blue() + 140) // 2,
                fill.alpha(),
            )
        return fill, QColor(170, 170, 170)

    def _paint_button_label_memo(self, p: QPainter, r: QRect, inst: dict) -> None:
        kind = str(inst.get("widget") or "")
        default_bg = {"button": "green", "label": "black", "memo": "white"}[kind]
        default_fg = {"button": "white", "label": "white", "memo": "black"}[kind]
        fill = QColor(resolve_color(str(inst.get("background") or default_bg)))
        fg = QColor(resolve_color(str(inst.get("color") or default_fg)))
        fill, fg = self._dim_colors(fill, fg, bool(inst.get("enabled", True)))
        if fill.alpha() > 0:
            p.fillRect(r, fill)
        border = inst.get("border") or {}
        bw = int(border.get("width") or 0)
        if bw > 0:
            p.setPen(QPen(QColor(resolve_color(str(border.get("color") or "black"))), bw))
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawRect(r.adjusted(bw // 2, bw // 2, -(bw // 2), -(bw // 2)))
        p.setFont(self._widget_font(inst))
        p.setPen(fg)
        inner_bw = max(0, bw)
        if kind != "memo":
            inner = r.adjusted(4 + inner_bw, inner_bw, -4 - inner_bw, -inner_bw)
            self._draw_fitted_text(p, inner, inst, str(inst.get("text") or ""), wrap=False)
            return
        overflows = self._memo_overflows(inst, r)
        pad = self._memo_pad(r, with_sb=overflows)
        offset = self._memo_offset(inst, r) if overflows else 0
        content_h = self._memo_content_h(inst, pad.width())
        fm = QFontMetrics(self._widget_font(inst))
        lines = self._wrap_chars(fm, str(inst.get("text") or ""), max(1, pad.width()))
        p.save()
        p.setClipRect(pad)
        y = pad.y() - offset
        line_h = fm.lineSpacing()
        flag = self._text_flags(inst, wrap=True)
        for line in lines:
            lr = QRect(pad.x(), y, pad.width(), line_h)
            if lr.bottom() >= pad.top() and lr.top() <= pad.bottom():
                p.drawText(lr, flag, line)
            y += line_h
        p.restore()
        if not overflows:
            return
        track = self._memo_scrollbar_rect(inst, r)
        if track is None:
            return
        p.fillRect(track, QColor(210, 210, 210))
        p.setPen(QPen(QColor(150, 150, 150), 1))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawRect(track)
        mx = self._memo_scroll_max(inst, r)
        thumb_h = max(12, int(track.height() * track.height() / max(1, content_h)))
        thumb_h = min(thumb_h, track.height())
        span = max(0, track.height() - thumb_h)
        ty = track.y() + (span * offset // mx if mx else 0)
        p.fillRect(QRect(track.x() + 1, ty, track.width() - 2, thumb_h), QColor(110, 110, 110))

    def _paint_switch(self, p: QPainter, r: QRect, inst: dict) -> None:
        fg = QColor(resolve_color(str(inst.get("color") or "white")))
        fill = QColor(resolve_color(str(inst.get("background") or "transparent")))
        fill, fg = self._dim_colors(fill, fg, bool(inst.get("enabled", True)))
        if fill.alpha() > 0:
            p.fillRect(r, fill)
        text = str(inst.get("text") or "")
        pill_w = min(52, max(36, r.height() * 2 - 4))
        pill_h = min(r.height() - 2, 24)
        if text:
            text_r = QRect(r.x() + 2, r.y(), max(8, r.width() - pill_w - 8), r.height())
            p.setPen(fg)
            self._draw_fitted_text(
                p,
                text_r,
                inst,
                text,
                wrap=False,
                flags=int(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft),
            )
            px = r.right() - pill_w - 2
        else:
            px = r.x() + max(0, (r.width() - pill_w) // 2)
        py = r.y() + max(0, (r.height() - pill_h) // 2)
        on = bool(inst.get("value"))
        track = QColor("#3cb043") if on else QColor("#7a7a7a")
        rf = QRectF(px, py, pill_w, pill_h)
        path = QPainterPath()
        path.addRoundedRect(rf, pill_h / 2.0, pill_h / 2.0)
        p.save()
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        p.fillPath(path, track)
        p.setPen(QPen(QColor("#222222"), 1))
        p.drawPath(path)
        knob = max(8.0, pill_h - 4)
        kx = rf.right() - 2 - knob if on else rf.left() + 2
        ky = rf.top() + (pill_h - knob) / 2.0
        p.setBrush(QColor("#ffffff"))
        p.drawEllipse(QRectF(kx, ky, knob, knob))
        p.restore()

    def _paint_checkbox(self, p: QPainter, r: QRect, inst: dict) -> None:
        fg = QColor(resolve_color(str(inst.get("color") or "white")))
        fill = QColor(resolve_color(str(inst.get("background") or "transparent")))
        fill, fg = self._dim_colors(fill, fg, bool(inst.get("enabled", True)))
        if fill.alpha() > 0:
            p.fillRect(r, fill)
        box_s = min(16, max(12, r.height() - 6))
        by = r.y() + max(0, (r.height() - box_s) // 2)
        box = QRect(r.x() + 2, by, box_s, box_s)
        p.fillRect(box, QColor("#ffffff"))
        p.setPen(QPen(QColor("#222222"), 2))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawRect(box.adjusted(1, 1, -1, -1))
        if inst.get("value"):
            p.setPen(QPen(QColor("#222222"), 2))
            p.drawLine(box.left() + 3, box.center().y(), box.center().x() - 1, box.bottom() - 3)
            p.drawLine(box.center().x() - 1, box.bottom() - 3, box.right() - 3, box.top() + 3)
        text = str(inst.get("text") or "")
        if text:
            p.setPen(fg)
            tr = QRect(box.right() + 6, r.y(), max(8, r.right() - box.right() - 8), r.height())
            self._draw_fitted_text(
                p,
                tr,
                inst,
                text,
                wrap=False,
                flags=int(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft),
            )

    def _paint_boxed(self, p: QPainter, r: QRect, inst: dict) -> tuple[QColor, int]:
        """Fill and border shared by Choice and Tree. Returns text colour and border width."""
        fill = QColor(resolve_color(str(inst.get("background") or "white")))
        fg = QColor(resolve_color(str(inst.get("color") or "black")))
        fill, fg = self._dim_colors(fill, fg, bool(inst.get("enabled", True)))
        if fill.alpha() > 0:
            p.fillRect(r, fill)
        border = inst.get("border") or {}
        bw = int(border.get("width") or 0)
        if bw > 0:
            p.setPen(QPen(QColor(resolve_color(str(border.get("color") or "black"))), bw))
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawRect(r.adjusted(bw // 2, bw // 2, -(bw // 2), -(bw // 2)))
        return fg, bw

    def _paint_choice(self, p: QPainter, r: QRect, inst: dict) -> None:
        style = str(inst.get("style") or "dropdown").lower()
        if style == "radio":
            self._paint_choice_radio(p, r, inst)
        else:
            self._paint_choice_dropdown(p, r, inst)

    def _choice_index(self, inst: dict, count: int) -> int:
        raw = inst.get("selected")
        if raw is None:
            raw = inst.get("value")
        try:
            idx = int(0 if raw is None else raw)
        except (TypeError, ValueError):
            return -1
        if idx < -1 or idx >= count:
            return -1
        return idx

    def _paint_choice_dropdown(self, p: QPainter, r: QRect, inst: dict) -> None:
        fg, bw = self._paint_boxed(p, r, inst)
        items = [str(item) for item in (inst.get("items") or [])]
        idx = self._choice_index(inst, len(items))
        text = items[idx] if 0 <= idx < len(items) else ""
        arrow_w = min(20, max(12, r.height()))
        arrow_r = QRect(r.right() - bw - arrow_w + 1, r.y() + bw, arrow_w, r.height() - 2 * bw)
        p.setPen(QPen(fg, 1))
        p.drawLine(arrow_r.left(), arrow_r.top() + 2, arrow_r.left(), arrow_r.bottom() - 2)
        tri = min(5, max(3, arrow_r.height() // 5))
        cx, cy = arrow_r.center().x() + 1, arrow_r.center().y()
        path = QPainterPath()
        path.moveTo(cx - tri, cy - tri // 2)
        path.lineTo(cx + tri, cy - tri // 2)
        path.lineTo(cx, cy + tri - tri // 2)
        path.closeSubpath()
        p.save()
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        p.fillPath(path, fg)
        p.restore()
        p.setPen(fg)
        text_r = QRect(r.x() + bw + 4, r.y() + bw, arrow_r.left() - r.x() - bw - 6, r.height() - 2 * bw)
        self._draw_fitted_text(
            p,
            text_r,
            inst,
            text,
            wrap=False,
            flags=int(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft),
        )

    def _paint_choice_radio(self, p: QPainter, r: QRect, inst: dict) -> None:
        fg, bw = self._paint_boxed(p, r, inst)
        items = [str(item) for item in (inst.get("items") or [])]
        if not items:
            return
        idx = self._choice_index(inst, len(items))
        inner = r.adjusted(bw, bw, -bw, -bw)
        if inner.width() <= 4 or inner.height() <= 4:
            return
        horizontal = str(inst.get("orientation") or "vertical").lower() == "horizontal"
        n = len(items)
        p.save()
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        p.setFont(self._widget_font(inst))
        fm = QFontMetrics(self._widget_font(inst))
        for i, item in enumerate(items):
            if horizontal:
                x0 = inner.x() + i * inner.width() // n
                x1 = inner.x() + (i + 1) * inner.width() // n
                cell = QRect(x0, inner.y(), max(1, x1 - x0), inner.height())
            else:
                y0 = inner.y() + i * inner.height() // n
                y1 = inner.y() + (i + 1) * inner.height() // n
                cell = QRect(inner.x(), y0, inner.width(), max(1, y1 - y0))
            dot = max(8, min(14, cell.height() - 4))
            cx = cell.x() + 4 + dot // 2
            cy = cell.center().y()
            circle = QRect(cx - dot // 2, cy - dot // 2, dot, dot)
            p.setPen(QPen(fg, 1))
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawEllipse(circle)
            if i == idx:
                inset = max(2, dot // 5)
                p.setBrush(fg)
                p.drawEllipse(circle.adjusted(inset, inset, -inset, -inset))
            text_r = QRect(circle.right() + 4, cell.y(), max(1, cell.right() - circle.right() - 6), cell.height())
            p.setPen(fg)
            p.drawText(
                text_r,
                int(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft),
                self._chars_fit(fm, item, text_r.width()),
            )
        p.restore()

    def _paint_tree(self, p: QPainter, r: QRect, inst: dict) -> None:
        fg, bw = self._paint_boxed(p, r, inst)
        inner = r.adjusted(bw + 2, bw + 2, -bw - 2, -bw - 2)
        if inner.width() <= 0 or inner.height() <= 0:
            return
        font = self._widget_font(inst)
        fm = QFontMetrics(font)
        row_h = max(fm.lineSpacing(), 10)
        step = max(10, fm.horizontalAdvance("M"))
        selected = str(inst.get("selected") or "")
        rows: list[tuple[int, str, bool, str]] = []

        def walk(nodes, depth: int, prefix: str) -> None:
            for node in nodes or []:
                if isinstance(node, dict):
                    text = str(node.get("text") or "")
                    path = f"{prefix}/{text}" if prefix else text
                    kids = node.get("items")
                    if kids is None:
                        kids = node.get("children") or []
                    has_kids = bool(kids)
                    rows.append((depth, text, has_kids, "" if has_kids else path))
                    if has_kids:
                        walk(kids, depth + 1, path)
                else:
                    text = str(node)
                    path = f"{prefix}/{text}" if prefix else text
                    rows.append((depth, text, False, path))

        walk(inst.get("items"), 0, "")
        p.save()
        p.setClipRect(inner)
        p.setFont(font)
        box = max(7, min(9, row_h - 4))
        y = inner.y()
        for depth, text, has_kids, path in rows:
            if y > inner.bottom():
                break
            if path and path == selected:
                p.fillRect(QRect(inner.x(), y, inner.width(), row_h), QColor(fg.red(), fg.green(), fg.blue(), 48))
            x = inner.x() + depth * step
            if has_kids:
                bx = QRect(x, y + (row_h - box) // 2, box, box)
                p.setPen(QPen(fg, 1))
                p.setBrush(Qt.BrushStyle.NoBrush)
                p.drawRect(bx)
                mid_y = bx.center().y()
                p.drawLine(bx.left() + 2, mid_y, bx.right() - 2, mid_y)
            p.setPen(fg)
            tr = QRect(x + box + 4, y, max(1, inner.right() - x - box - 3), row_h)
            p.drawText(
                tr,
                int(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft),
                self._chars_fit(fm, text, tr.width()),
            )
            y += row_h
        p.restore()

    def _paint_slider(self, p: QPainter, r: QRect, inst: dict) -> None:
        # Same look as on the board: a thin track (filled up to the value) and a ROUND knob.
        mn = int(inst.get("min") or 0)
        mx = int(inst.get("max") or 1)
        val = int(inst.get("value") or 0)
        span = max(1, mx - mn)
        frac = max(0.0, min(1.0, (val - mn) / span))
        accent = QColor(resolve_color(str(inst.get("color") or "green")))
        track_c = QColor(resolve_color(str(inst.get("background") or "gray")))
        accent, _fg = self._dim_colors(accent, accent, bool(inst.get("enabled", True)))
        vertical = r.height() > r.width()
        rr = max(5, min(r.width(), r.height()) // 2 - 1)          # knob radius (same rule as the board)
        if vertical:
            cx = r.center().x()
            y_low = r.bottom() - rr
            ky = y_low - int((r.height() - 2 * rr) * frac)
            p.setPen(QPen(track_c, 4))
            p.drawLine(cx, r.top() + rr, cx, y_low)
            p.setPen(QPen(accent, 4))
            p.drawLine(cx, ky, cx, y_low)
            centre = QPoint(cx, ky)
        else:
            cy = r.center().y()
            x_low = r.left() + rr
            kx = x_low + int((r.width() - 2 * rr) * frac)
            p.setPen(QPen(track_c, 4))
            p.drawLine(x_low, cy, r.right() - rr, cy)
            p.setPen(QPen(accent, 4))
            p.drawLine(x_low, cy, kx, cy)
            centre = QPoint(kx, cy)
        p.setBrush(QColor("white"))
        p.setPen(QPen(accent, 3))
        p.drawEllipse(centre, rr - 1, rr - 1)
        p.setBrush(Qt.BrushStyle.NoBrush)

    def _paint_progressbar(self, p: QPainter, r: QRect, inst: dict) -> None:
        mx = max(0, int(inst.get("max") or 0))
        val = max(0, min(mx, int(inst.get("value") or 0)))
        empty = QColor(resolve_color(str(inst.get("background") or "gray")))
        filled = QColor(resolve_color(str(inst.get("color") or "green")))
        p.fillRect(r, empty)
        frac = 0.0 if mx <= 0 else val / mx
        if r.height() > r.width():
            fh = int((r.height() - 2) * frac)
            p.fillRect(QRect(r.x() + 1, r.bottom() - fh, r.width() - 2, fh), filled)
        else:
            fw = int((r.width() - 2) * frac)
            p.fillRect(QRect(r.x() + 1, r.y() + 1, fw, r.height() - 2), filled)
        p.setPen(QPen(QColor("#444444"), 1))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawRect(r)

    @staticmethod
    def _format_number(value: object) -> str:
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            return "" if value is None else str(value)
        if isinstance(value, float):
            if value.is_integer() and abs(value) < 1e12:
                return str(int(value))
            return f"{value:.6f}".rstrip("0").rstrip(".")
        return str(value)

    def _ink_on(self, color: QColor) -> QColor:
        if self._luma(color) < 140:
            return QColor("#ffffff")
        return QColor("#111111")

    @staticmethod
    def _polar(cx: float, cy: float, radius: float, qt_deg: float) -> QPoint:
        rad = math.radians(qt_deg)
        return QPoint(
            int(round(cx + radius * math.cos(rad))),
            int(round(cy - radius * math.sin(rad))),
        )

    def _paint_gauge(self, p: QPainter, r: QRect, inst: dict) -> None:
        if r.width() < 2 or r.height() < 2:
            return
        p.save()
        p.setClipRect(r)
        try:
            mn = float(inst.get("min") or 0)
            mx = float(inst.get("max") or 0)
            val = float(inst.get("value") or 0)
        except (TypeError, ValueError):
            mn, mx, val = 0.0, 100.0, 0.0
        try:
            sweep = float(inst.get("sweep") or 270)
        except (TypeError, ValueError):
            sweep = 270.0
        sweep = max(1.0, min(360.0, sweep))
        try:
            diameter = int(inst.get("diameter") or 0)
        except (TypeError, ValueError):
            diameter = 0
        side = diameter if diameter > 0 else min(r.width(), r.height())
        side = max(8, side)
        box = QRect(
            r.center().x() - side // 2,
            r.center().y() - side // 2,
            side,
            side,
        )
        ring = QColor(resolve_color(str(inst.get("background") or "gray")))
        needle = QColor(resolve_color(str(inst.get("color") or "red")))
        pen_w = max(2, side // 18)
        arc = QRectF(box).adjusted(pen_w, pen_w, -pen_w, -pen_w)
        start = 90.0 + sweep / 2.0
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.setPen(QPen(ring, pen_w, Qt.PenStyle.SolidLine, Qt.PenCapStyle.FlatCap))
        p.drawArc(arc, int(round(start * 16)), int(round(-sweep * 16)))
        radius = arc.width() / 2.0
        cx, cy = arc.center().x(), arc.center().y()
        try:
            ticks = int(inst.get("ticks") or 0)
        except (TypeError, ValueError):
            ticks = 0
        if inst.get("show_ticks", True) and ticks > 0 and radius > 4:
            inner = radius - max(4.0, radius * 0.14)
            p.setPen(QPen(needle, max(1, pen_w // 2)))
            for i in range(ticks + 1):
                ang = start - (i / ticks) * sweep
                p.drawLine(
                    self._polar(cx, cy, inner, ang),
                    self._polar(cx, cy, radius, ang),
                )
        span = mx - mn
        frac = 0.0 if span == 0 else (val - mn) / span
        frac = max(0.0, min(1.0, frac))
        ang = start - frac * sweep
        hub = self._polar(cx, cy, 0, ang)
        tip = self._polar(cx, cy, radius * 0.78, ang)
        p.setPen(QPen(needle, max(2, pen_w // 2), Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        p.drawLine(hub, tip)
        p.setBrush(needle)
        p.setPen(Qt.PenStyle.NoPen)
        hub_r = max(2, pen_w // 2)
        p.drawEllipse(QRect(int(round(cx)) - hub_r, int(round(cy)) - hub_r, hub_r * 2, hub_r * 2))
        p.setRenderHint(QPainter.RenderHint.Antialiasing, False)
        p.setFont(self._widget_font(inst))
        fm = QFontMetrics(p.font())
        ink = self._ink_on(self._screen_bg())
        p.setPen(ink)
        y_text = int(cy + radius * 0.12)
        line_h = fm.lineSpacing()
        if inst.get("show_value", True):
            shown = self._chars_fit(fm, self._format_number(inst.get("value")), box.width() - 4)
            p.drawText(
                QRect(box.left(), y_text, box.width(), line_h),
                int(Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop),
                shown,
            )
            y_text += line_h
        caption = str(inst.get("text") or "")
        if caption:
            shown = self._chars_fit(fm, caption, box.width() - 4)
            p.drawText(
                QRect(box.left(), y_text, box.width(), line_h),
                int(Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop),
                shown,
            )
        p.restore()

    def _paint_stepper(self, p: QPainter, r: QRect, inst: dict) -> None:
        if r.width() < 2 or r.height() < 2:
            return
        p.save()
        p.setClipRect(r)
        side = max(1, r.height())
        left = QRect(r.x(), r.y(), side, side)
        right = QRect(r.x() + r.width() - side, r.y(), side, side)
        enabled = bool(inst.get("enabled", True))
        btn = QColor(resolve_color(str(inst.get("color") or "green")))
        btn, _fg = self._dim_colors(btn, btn, enabled)
        p.fillRect(left, btn)
        p.fillRect(right, btn)
        mark = self._ink_on(btn)
        if not enabled:
            mark = QColor(170, 170, 170)
        glyph = QFont(self.font())
        glyph.setPixelSize(max(10, min(side - 4, 28)))
        p.setFont(glyph)
        p.setPen(mark)
        p.drawText(left, int(Qt.AlignmentFlag.AlignCenter), "-")
        p.drawText(right, int(Qt.AlignmentFlag.AlignCenter), "+")
        gap = QRect(r.x() + side, r.y(), r.width() - 2 * side, r.height())
        bg_name = str(inst.get("background") or "transparent").strip().lower()
        if gap.width() > 0 and bg_name != "transparent":
            fill = QColor(resolve_color(bg_name))
            fill, _fg = self._dim_colors(fill, fill, enabled)
            p.fillRect(gap, fill)
            ink_bg = fill
        else:
            ink_bg = self._screen_bg()
        p.setFont(self._widget_font(inst))
        ink = self._ink_on(ink_bg)
        if not enabled:
            ink = QColor(170, 170, 170)
        p.setPen(ink)
        shown = self._format_number(inst.get("value"))
        target = gap if gap.width() >= 8 else r
        p.drawText(target, int(Qt.AlignmentFlag.AlignCenter), shown)
        p.restore()

    def _chart_font_metrics(self, inst: dict) -> QFontMetrics:
        return QFontMetrics(self._widget_font(inst))

    def _paint_chart_grid(self, p: QPainter, plot: QRect, ink: QColor) -> None:
        if plot.height() < 4 or plot.width() < 2:
            return
        faint = QColor(ink)
        faint.setAlpha(70)
        p.setPen(QPen(faint, 1))
        for frac in (0.25, 0.5, 0.75):
            y = plot.bottom() - int(round(frac * plot.height()))
            p.drawLine(plot.left(), y, plot.right(), y)

    @staticmethod
    def _value_y(plot: QRect, mn: float, mx: float, value: float) -> int:
        span = mx - mn
        if span == 0 or plot.height() <= 0:
            return plot.center().y()
        frac = (float(value) - mn) / span
        frac = max(0.0, min(1.0, frac))
        return plot.bottom() - int(round(frac * plot.height()))

    def _sample_wave(self, inst: dict) -> list[float]:
        try:
            mn = float(inst.get("min") or 0)
            mx = float(inst.get("max") or 0)
        except (TypeError, ValueError):
            mn, mx = 0.0, 100.0
        try:
            count = int(inst.get("points") or 60)
        except (TypeError, ValueError):
            count = 60
        count = max(2, min(300, count))
        if mx <= mn:
            return [mn] * count
        mid = (mn + mx) / 2.0
        amp = (mx - mn) * 0.4
        return [
            mid + amp * math.sin((i / (count - 1)) * math.tau * 1.25)
            for i in range(count)
        ]

    def _paint_waveform(self, p: QPainter, r: QRect, inst: dict) -> None:
        if r.width() < 2 or r.height() < 2:
            return
        p.save()
        p.setClipRect(r)
        bg = QColor(resolve_color(str(inst.get("background") or "black")))
        trace = QColor(resolve_color(str(inst.get("color") or "green")))
        p.fillRect(r, bg)
        p.setFont(self._widget_font(inst))
        fm = QFontMetrics(p.font())
        ink = self._ink_on(bg)
        title = str(inst.get("title") or "")
        top = fm.lineSpacing() if title else 0
        plot = r.adjusted(2, top + 2, -2, -2)
        if inst.get("grid", True):
            self._paint_chart_grid(p, plot, ink)
        try:
            mn = float(inst.get("min") or 0)
            mx = float(inst.get("max") or 0)
        except (TypeError, ValueError):
            mn, mx = 0.0, 100.0
        samples = self._sample_wave(inst)
        style = str(inst.get("style") or "line").lower()
        p.setRenderHint(QPainter.RenderHint.Antialiasing, style != "bars")
        if plot.width() > 1 and plot.height() > 1 and samples:
            if style == "bars":
                slot = plot.width() / len(samples)
                p.setPen(Qt.PenStyle.NoPen)
                p.setBrush(trace)
                for i, sample in enumerate(samples):
                    y = self._value_y(plot, mn, mx, sample)
                    base = self._value_y(plot, mn, mx, mn)
                    x = plot.left() + int(i * slot)
                    bw = max(1, int(slot) - 1)
                    p.fillRect(QRect(x, min(y, base), bw, max(1, abs(base - y))), trace)
            else:
                path = QPainterPath()
                for i, sample in enumerate(samples):
                    x = plot.left() + (plot.width() - 1) * (i / (len(samples) - 1))
                    y = self._value_y(plot, mn, mx, sample)
                    if i == 0:
                        path.moveTo(x, y)
                    else:
                        path.lineTo(x, y)
                p.setBrush(Qt.BrushStyle.NoBrush)
                p.setPen(QPen(trace, 2))
                p.drawPath(path)
        if title:
            p.setRenderHint(QPainter.RenderHint.Antialiasing, False)
            p.setPen(ink)
            shown = self._chars_fit(fm, title, r.width() - 4)
            p.drawText(
                QRect(r.left() + 2, r.top(), r.width() - 4, fm.lineSpacing()),
                int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter),
                shown,
            )
        p.restore()

    def _paint_barchart(self, p: QPainter, r: QRect, inst: dict) -> None:
        if r.width() < 2 or r.height() < 2:
            return
        p.save()
        p.setClipRect(r)
        bg = QColor(resolve_color(str(inst.get("background") or "black")))
        bar = QColor(resolve_color(str(inst.get("color") or "green")))
        p.fillRect(r, bg)
        p.setFont(self._widget_font(inst))
        fm = QFontMetrics(p.font())
        ink = self._ink_on(bg)
        p.setPen(ink)
        line_h = fm.lineSpacing()
        title = str(inst.get("title") or "")
        labels = inst.get("labels") if isinstance(inst.get("labels"), list) else []
        values = inst.get("values") if isinstance(inst.get("values"), list) else []
        try:
            slots = max(1, int(inst.get("bars") or 1))
        except (TypeError, ValueError):
            slots = 1
        try:
            mn = float(inst.get("min") or 0)
            mx = float(inst.get("max") or 0)
        except (TypeError, ValueError):
            mn, mx = 0.0, 100.0
        sample = not labels and not values
        if sample:
            pattern = (0.45, 0.8, 0.35, 0.92, 0.55)
            span = mx - mn
            if span == 0:
                values = [mn] * slots
            else:
                values = [mn + span * pattern[i % len(pattern)] for i in range(slots)]
        top = line_h if title else 0
        bottom = line_h if labels else 0
        plot = r.adjusted(2, top + 2, -2, -(bottom + 2))
        if inst.get("show_values") and not sample and plot.height() > line_h:
            plot.setTop(plot.top() + line_h)
        if inst.get("grid", True):
            self._paint_chart_grid(p, plot, ink)
        if plot.width() > 1 and plot.height() > 1:
            slot = plot.width() / slots
            p.setPen(Qt.PenStyle.NoPen)
            for i in range(min(slots, len(values))):
                try:
                    value = float(values[i])
                except (TypeError, ValueError):
                    continue
                y = self._value_y(plot, mn, mx, value)
                base = self._value_y(plot, mn, mx, mn)
                height = abs(base - y)
                bw = max(1, int(slot * 0.7))
                x = plot.left() + int(i * slot + (slot - bw) / 2)
                if height > 0:
                    p.fillRect(QRect(x, min(y, base), bw, height), bar)
                if inst.get("show_values") and not sample:
                    p.setPen(ink)
                    text = self._chars_fit(fm, self._format_number(values[i]), max(1, int(slot)))
                    p.drawText(
                        QRect(plot.left() + int(i * slot), min(y, base) - line_h, int(slot), line_h),
                        int(Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignBottom),
                        text,
                    )
                    p.setPen(Qt.PenStyle.NoPen)
        if labels and bottom:
            p.setPen(ink)
            slot = plot.width() / slots
            for i in range(min(slots, len(labels))):
                text = self._chars_fit(fm, str(labels[i]), max(1, int(slot) - 2))
                p.drawText(
                    QRect(plot.left() + int(i * slot), r.bottom() - line_h + 1, int(slot), line_h),
                    int(Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignVCenter),
                    text,
                )
        if title:
            p.setPen(ink)
            shown = self._chars_fit(fm, title, r.width() - 4)
            p.drawText(
                QRect(r.left() + 2, r.top(), r.width() - 4, line_h),
                int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter),
                shown,
            )
        p.restore()

    def _load_pixmap(self, src: str) -> QPixmap:
        src = str(src or "").strip()
        if not src:
            return QPixmap()
        cached = self._pix_cache.get(src)
        if cached is not None and not cached.isNull():
            return cached
        pm = QPixmap()
        if src.startswith("file://"):
            pm = QPixmap(QUrl(src).toLocalFile() or src)
        elif src.startswith("data:"):
            try:
                import base64

                _head, _sep, payload = src.partition(",")
                img = QImage.fromData(base64.b64decode(payload))
                if not img.isNull():
                    pm = QPixmap.fromImage(img)
            except Exception:
                pm = QPixmap()
        elif src.startswith(("http://", "https://")):
            try:
                import ssl
                from urllib.request import Request, urlopen

                req = Request(src, headers={"User-Agent": "ESD/1.0"})
                ctx = ssl._create_unverified_context()
                with urlopen(req, timeout=12, context=ctx) as resp:
                    img = QImage.fromData(resp.read())
                if not img.isNull():
                    pm = QPixmap.fromImage(img)
            except Exception:
                pm = QPixmap()
        else:
            pm = QPixmap(src)
        if not pm.isNull():
            self._pix_cache[src] = pm
        return pm

    def _paint_image(self, p: QPainter, r: QRect, inst: dict) -> None:
        trans = bool(inst.get("transparent", True))
        if not trans:
            bg = QColor(resolve_color(str(inst.get("background") or "gray")))
            if bg.alpha() > 0:
                p.fillRect(r, bg)
        pm = self._load_pixmap(str(inst.get("source") or ""))
        p.save()
        p.setClipRect(r)
        if pm.isNull():
            p.setPen(QColor("#888888"))
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawRect(r.adjusted(0, 0, -1, -1))
            p.drawText(r, int(Qt.AlignmentFlag.AlignCenter), "Image")
            p.restore()
            return
        scale = str(inst.get("scale") or "fit")
        if scale == "natural":
            scale = "fit"
        if scale == "stretch":
            p.drawPixmap(r, pm)
        elif scale == "fill":
            scaled = pm.scaled(
                r.size(),
                Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                Qt.TransformationMode.SmoothTransformation,
            )
            x = r.x() + (r.width() - scaled.width()) // 2
            y = r.y() + (r.height() - scaled.height()) // 2
            p.drawPixmap(x, y, scaled)
        else:
            scaled = pm.scaled(
                r.size(),
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
            x = r.x() + (r.width() - scaled.width()) // 2
            y = r.y() + (r.height() - scaled.height()) // 2
            p.drawPixmap(x, y, scaled)
        p.restore()

    def _editor_visible(self, inst: dict) -> bool:
        """Hidden widgets stay on the canvas while Show Hidden Widgets is on."""
        return bool(inst.get("visible", True) or self.show_hidden)

    def _paint_hidden_outline(self, p: QPainter, sr: QRect, inst: dict) -> None:
        """Dashed box so a hidden widget does not look like empty screen."""
        r = QRect(
            sr.x() + int(inst.get("x") or 0),
            sr.y() + int(inst.get("y") or 0),
            int(inst.get("w") or 0),
            int(inst.get("h") or 0),
        )
        color = self._contrast_on_screen()
        color.setAlpha(170)
        pen = QPen(color, 1, Qt.PenStyle.DashLine)
        pen.setCosmetic(True)
        p.save()
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.setPen(pen)
        if str(inst.get("widget") or "") == "line":
            p.drawLine(r.topLeft(), r.bottomRight())
            text_r = QRect(r.x() + 4, r.y() + 2, max(8, abs(r.width())), 12)
        else:
            box = r.adjusted(0, 0, -1, -1)
            if box.width() < 1:
                box.setWidth(1)
            if box.height() < 1:
                box.setHeight(1)
            p.drawRect(box)
            text_r = QRect(box.x() + 3, box.y() + 1, max(8, box.width() - 4), 14)
        font = QFont()
        font.setPixelSize(10)
        p.setFont(font)
        p.setPen(color)
        p.drawText(
            text_r,
            int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter),
            str(inst.get("id") or "hidden"),
        )
        p.restore()

    def _paint_line(self, p: QPainter, r: QRect, inst: dict) -> None:
        color = QColor(resolve_color(str(inst.get("color") or "white")))
        thick = max(1, int(inst.get("thickness") or 1))
        p.save()
        p.setPen(QPen(color, thick))
        p.drawLine(r.topLeft(), r.bottomRight())
        p.restore()

    def _keyboard_key_rects(self, inst: dict, r: QRect) -> list[tuple[str, QRect]]:
        layout = str(inst.get("layout") or "full")
        if layout.lower() == "numeric":
            return self._numeric_key_rects(r)
        rows = keyboard_rows(layout, linefeed=bool(inst.get("linefeed")))
        if not rows or r.width() < 8 or r.height() < 8:
            return []
        gap = 2
        rh = max(12, (r.height() - gap * (len(rows) + 1)) // len(rows))
        out: list[tuple[str, QRect]] = []
        y = r.y() + gap
        for row in rows:
            n = max(1, len(row))
            kw = max(10, (r.width() - gap * (n + 1)) // n)
            x = r.x() + gap
            for i, lab in enumerate(row):
                remain_keys = n - i - 1
                if lab == "SPACE":
                    w = max(kw, (r.x() + r.width() - gap - x) - remain_keys * (kw + gap))
                else:
                    w = kw
                out.append((lab, QRect(x, y, w, rh)))
                x += w + gap
            y += rh + gap
        return out

    def _numeric_key_rects(self, r: QRect) -> list[tuple[str, QRect]]:
        """4x4 pad. Enter fills the right column of the last two rows."""
        rows = keyboard_rows("numeric", linefeed=False)
        if r.width() < 8 or r.height() < 8 or len(rows) != 4:
            return []
        gap = 2
        cols = 4
        cell_w = max(8, (r.width() - gap * (cols + 1)) // cols)
        cell_h = max(8, (r.height() - gap * (len(rows) + 1)) // len(rows))
        out: list[tuple[str, QRect]] = []
        for row_i, row in enumerate(rows):
            for col_i, lab in enumerate(row):
                x = r.x() + gap + col_i * (cell_w + gap)
                if lab == "ENT":
                    y = r.y() + gap + (row_i - 1) * (cell_h + gap)
                    out.append((lab, QRect(x, y, cell_w, cell_h * 2 + gap)))
                    continue
                y = r.y() + gap + row_i * (cell_h + gap)
                out.append((lab, QRect(x, y, cell_w, cell_h)))
        return out

    def _paint_keyboard(self, p: QPainter, r: QRect, inst: dict) -> None:
        fill = QColor(resolve_color(str(inst.get("background") or "gray")))
        fg = QColor(resolve_color(str(inst.get("color") or "black")))
        fill, fg = self._dim_colors(fill, fg, bool(inst.get("enabled", True)))
        if fill.alpha() > 0:
            p.fillRect(r, fill)
        border = inst.get("border") or {}
        bw = int(border.get("width") or 0)
        if bw > 0:
            p.setPen(QPen(QColor(resolve_color(str(border.get("color") or "black"))), bw))
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawRect(r)
        font = QFont()
        font.setPixelSize(11)
        p.setFont(font)
        for lab, kr in self._keyboard_key_rects(inst, r.adjusted(2, 2, -2, -2)):
            p.fillRect(kr, QColor("#d8d8d8"))
            p.setPen(QPen(QColor("#333333"), 1))
            p.drawRect(kr)
            shown = {"SPACE": "Space", "ENT": "Enter", "BS": "Bksp", "LF": "LF", "ESC": "Esc"}.get(lab, lab)
            p.setPen(fg)
            p.drawText(kr, int(Qt.AlignmentFlag.AlignCenter), shown)

    def start_keyboard_call(self, inst: dict) -> None:
        if inst is None or str(inst.get("widget") or "") != "keyboard":
            return
        if self._kb_session is not None:
            return
        self._kb_session = {
            "id": str(inst.get("id") or ""),
            "buffer": "",
            "target": str(inst.get("target") or ""),
            "secret": bool(inst.get("secret")),
            "max_length": int(inst.get("max_length") or 0),
            "layout": str(inst.get("layout") or "full"),
            "linefeed": bool(inst.get("linefeed")),
            "hide_on_enter": bool(inst.get("hide_on_enter", True)),
            "input_event": bool(inst.get("input_event")),
            "background": inst.get("background") or "gray",
            "color": inst.get("color") or "black",
            "border": inst.get("border") or {"color": "black", "width": 1},
        }
        self._drag = None
        self.setFocus(Qt.FocusReason.OtherFocusReason)
        self.update()

    def cancel_keyboard_call(self) -> None:
        self._kb_session = None
        self.update()

    def _kb_call_rects(self, sr: QRect) -> tuple[QRect, QRect]:
        memo_h = max(48, min(80, sr.height() // 4))
        memo = QRect(sr.x() + 8, sr.y() + 8, sr.width() - 16, memo_h)
        keys = QRect(
            sr.x() + 6,
            memo.bottom() + 8,
            sr.width() - 12,
            max(40, sr.bottom() - memo.bottom() - 14),
        )
        return memo, keys

    def _paint_keyboard_call(self, p: QPainter, sr: QRect) -> None:
        sess = self._kb_session or {}
        memo_r, keys_r = self._kb_call_rects(sr)
        p.fillRect(memo_r, QColor("#ffffff"))
        p.setPen(QPen(QColor("#222222"), 1))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawRect(memo_r)
        raw = str(sess.get("buffer") or "")
        shown = ("*" * len(raw)) if sess.get("secret") else raw
        font = QFont()
        font.setPixelSize(13)
        p.setFont(font)
        p.setPen(QColor("#111111"))
        inner = memo_r.adjusted(6, 4, -6, -4)
        fm = QFontMetrics(font)
        lines = self._wrap_chars(fm, shown, max(1, inner.width()))
        p.save()
        p.setClipRect(inner)
        y = inner.y()
        lh = fm.lineSpacing()
        for line in lines:
            if y > inner.bottom():
                break
            p.drawText(QRect(inner.x(), y, inner.width(), lh), int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter), line)
            y += lh
        p.restore()
        fake = {
            "layout": sess.get("layout") or "full",
            "linefeed": sess.get("linefeed"),
            "background": sess.get("background") or "gray",
            "color": sess.get("color") or "black",
            "border": sess.get("border") or {"color": "black", "width": 1},
            "enabled": True,
        }
        self._paint_keyboard(p, keys_r, fake)

    def _kb_type(self, token: str) -> None:
        sess = self._kb_session
        if sess is None:
            return
        buf = str(sess.get("buffer") or "")
        mx = int(sess.get("max_length") or 0)
        if token == "BS":
            sess["buffer"] = buf[:-1]
        elif token == "ESC":
            self.cancel_keyboard_call()
            return
        elif token == "ENT":
            target = str(sess.get("target") or "")
            text = str(sess.get("buffer") or "")
            self._kb_session = None
            self.keyboardFinished.emit(target, text)
            self.update()
            return
        elif token == "SPACE":
            token = " "
            if mx and len(buf) >= mx:
                self.update()
                return
            sess["buffer"] = buf + token
        elif token == "LF":
            if mx and len(buf) >= mx:
                self.update()
                return
            sess["buffer"] = buf + "\n"
        else:
            ch = token[:1] if token else ""
            if not ch:
                self.update()
                return
            if mx and len(buf) >= mx:
                self.update()
                return
            sess["buffer"] = buf + ch
        self.update()

    def mousePressEvent(self, event) -> None:  # noqa: N802
        if event.button() != Qt.MouseButton.LeftButton:
            return
        pos = event.position().toPoint()
        if self._kb_session is not None:
            _memo_r, keys_r = self._kb_call_rects(self.screen_rect())
            fake = {
                "layout": self._kb_session.get("layout") or "full",
                "linefeed": self._kb_session.get("linefeed"),
            }
            for lab, kr in self._keyboard_key_rects(fake, keys_r.adjusted(2, 2, -2, -2)):
                if kr.contains(pos):
                    self._kb_type(lab)
                    return
            return
        token, mode = self.hit_test(pos)
        self.select(token)
        if token.startswith("widget:"):
            found = self.design.find_widget(token.split(":", 1)[1])
            if found is None:
                self._drag = None
                return
            _sc, inst = found
            if str(inst.get("widget") or "") == "memo":
                r = self._widget_canvas_rect(inst)
                sb = self._memo_scrollbar_rect(inst, r)
                if sb is not None and sb.contains(pos):
                    self._drag = {
                        "id": inst.get("id"),
                        "mode": "memo_scroll",
                        "oy": pos.y(),
                        "os": self._memo_offset(inst, r),
                    }
                    return
            if mode in HANDLE_KEYS + ("move",):
                self._drag = {
                    "id": inst.get("id"),
                    "mode": mode,
                    "started": False,
                    "ox": pos.x(),
                    "oy": pos.y(),
                    "sx": int(inst.get("x") or 0),
                    "sy": int(inst.get("y") or 0),
                    "sw": int(inst.get("w") or 0),
                    "sh": int(inst.get("h") or 0),
                }
                return
        self._drag = None

    def mouseMoveEvent(self, event) -> None:  # noqa: N802
        pos = event.position().toPoint()
        if self._drag is None:
            _token, mode = self.hit_test(pos)
            cursors = {
                "nw": Qt.CursorShape.SizeFDiagCursor,
                "se": Qt.CursorShape.SizeFDiagCursor,
                "ne": Qt.CursorShape.SizeBDiagCursor,
                "sw": Qt.CursorShape.SizeBDiagCursor,
                "n": Qt.CursorShape.SizeVerCursor,
                "s": Qt.CursorShape.SizeVerCursor,
                "w": Qt.CursorShape.SizeHorCursor,
                "e": Qt.CursorShape.SizeHorCursor,
                "move": Qt.CursorShape.SizeAllCursor,
            }
            self.setCursor(cursors.get(mode, Qt.CursorShape.ArrowCursor))
            return
        found = self.design.find_widget(str(self._drag["id"]))
        if found is None:
            return
        _sc, inst = found
        if str(self._drag.get("mode") or "") == "memo_scroll":
            r = self._widget_canvas_rect(inst)
            pad = self._memo_pad(r, with_sb=True)
            ratio = self._memo_content_h(inst, pad.width()) / max(1, pad.height())
            dy = pos.y() - int(self._drag["oy"])
            self._set_memo_scroll(inst, int(self._drag["os"]) + int(dy * ratio), r)
            self.update()
            return
        dx = pos.x() - int(self._drag["ox"])
        dy = pos.y() - int(self._drag["oy"])
        mode = str(self._drag["mode"])
        sx, sy = int(self._drag["sx"]), int(self._drag["sy"])
        sw, sh = int(self._drag["sw"]), int(self._drag["sh"])
        x, y, w, h = sx, sy, sw, sh
        if mode == "move":
            x = self._snap(sx + dx)
            y = self._snap(sy + dy)
        else:
            if "e" in mode or mode == "e":
                w = self._snap(sw + dx)
            if "s" in mode or mode == "s":
                h = self._snap(sh + dy)
            if "w" in mode:
                x = self._snap(sx + dx)
                w = self._snap(sw - dx)
            if "n" in mode:
                y = self._snap(sy + dy)
                h = self._snap(sh - dy)
        kind = str(inst.get("widget") or "")
        if kind == "line":
            w = max(0, w)
            h = max(0, h)
        else:
            w = max(8, w)
            h = max(8, h)
        trial = {
            "widget": inst.get("widget"),
            "id": inst.get("id"),
            "x": x,
            "y": y,
            "w": w,
            "h": h,
        }
        sid = str(_sc.get("id") or self.active_screen_id)
        scr_w, scr_h = self.design.screen_size(sid)
        clamp_widget(trial, scr_w, scr_h)
        if kind in ("slider", "progressbar") and int(trial["w"]) == int(trial["h"]):
            if abs(h - sh) >= abs(w - sw):
                trial["h"] = int(trial["w"]) + (1 if h >= sh else -1)
            else:
                trial["w"] = int(trial["h"]) + (1 if w >= sw else -1)
            trial["h"] = max(8, int(trial["h"]))
            trial["w"] = max(8, int(trial["w"]))
            clamp_widget(trial, scr_w, scr_h)
        if not geometry_allowed(trial):
            return
        other = overlapping_interactive(self.design, sid, trial)
        if other is not None:
            self.overlapBlocked.emit(overlap_text(other))
            return
        if not self._drag.get("started"):
            self._drag["started"] = True
            self.dragAboutToStart.emit()
        inst["x"], inst["y"], inst["w"], inst["h"] = (
            trial["x"],
            trial["y"],
            trial["w"],
            trial["h"],
        )
        self.widgetsChanged.emit()
        self.update()

    def mouseReleaseEvent(self, _event) -> None:  # noqa: N802
        if self._drag is not None:
            mode = str(self._drag.get("mode") or "")
            self._drag = None
            if mode != "memo_scroll":
                self.dragFinished.emit()
                self.selectionChanged.emit(self._selected)
        else:
            self._drag = None

    def wheelEvent(self, event) -> None:  # noqa: N802
        pos = event.position().toPoint()
        inst = self._widget_at(pos)
        if inst is not None and str(inst.get("widget") or "") == "memo":
            r = self._widget_canvas_rect(inst)
            if self._memo_overflows(inst, r):
                steps = int(event.angleDelta().y())
                if steps == 0:
                    event.ignore()
                    return
                line = QFontMetrics(self._widget_font(inst)).lineSpacing()
                notches = max(1, abs(steps) // 120)
                delta = -notches * line if steps > 0 else notches * line
                self._set_memo_scroll(inst, self._memo_offset(inst, r) + delta, r)
                event.accept()
                self.update()
                return
        event.ignore()

    def mouseDoubleClickEvent(self, event) -> None:  # noqa: N802
        if self._kb_session is not None:
            return
        pos = event.position().toPoint()
        inst = self._widget_at(pos)
        if inst is not None and str(inst.get("widget") or "") == "keyboard":
            self.start_keyboard_call(inst)

    def keyPressEvent(self, event) -> None:  # noqa: N802
        if self._kb_session is None:
            super().keyPressEvent(event)
            return
        key = event.key()
        if key == Qt.Key.Key_Escape:
            self.cancel_keyboard_call()
            return
        if key in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            self._kb_type("ENT")
            return
        if key == Qt.Key.Key_Backspace:
            self._kb_type("BS")
            return
        text = event.text()
        if text == "\n":
            self._kb_type("LF")
            return
        if text == " ":
            self._kb_type("SPACE")
            return
        if text and text.isprintable():
            self._kb_type(text.upper() if len(text) == 1 else text)
            return
        event.ignore()

    def _mime_is_image_drop(self, mime) -> bool:
        if mime.hasUrls():
            return True
        if mime.hasImage():
            return True
        for fmt in ("image/png", "image/jpeg", "image/jpg", "image/bmp"):
            if mime.hasFormat(fmt):
                return True
        html = mime.html() if mime.hasHtml() else ""
        if html and "<img" in html.lower():
            return True
        if mime.hasText():
            t = mime.text().strip()
            if t.startswith(("http://", "https://", "file://", "/")):
                return True
        return False

    def _persist_qimage(self, img: QImage) -> str:
        if img is None or img.isNull():
            return ""
        folder = Path.cwd() / ".esd_images"
        folder.mkdir(parents=True, exist_ok=True)
        path = folder / f"drop_{uuid.uuid4().hex[:12]}.png"
        if not img.save(str(path), "PNG"):
            return ""
        return str(path)

    def _extract_drop_image(self, mime) -> str:
        if mime.hasUrls():
            for url in mime.urls():
                local = url.toLocalFile()
                if local:
                    return local
                s = url.toString()
                if s:
                    return s
        if mime.hasHtml():
            html = mime.html()
            low = html.lower()
            mark = "src="
            i = low.find(mark)
            if i >= 0:
                rest = html[i + 4 :].strip()
                if rest[:1] in "\"'":
                    q = rest[0]
                    end = rest.find(q, 1)
                    if end > 1:
                        return rest[1:end]
        for fmt in ("image/png", "image/jpeg", "image/jpg", "image/bmp"):
            if mime.hasFormat(fmt):
                img = QImage.fromData(bytes(mime.data(fmt)))
                saved = self._persist_qimage(img)
                if saved:
                    return saved
        if mime.hasImage():
            data = mime.imageData()
            img = None
            if isinstance(data, QImage):
                img = data
            elif isinstance(data, QPixmap):
                img = data.toImage()
            saved = self._persist_qimage(img)
            if saved:
                return saved
        if mime.hasText():
            t = mime.text().strip().splitlines()[0].strip()
            if t:
                return t
        return ""

    def dragEnterEvent(self, event) -> None:  # noqa: N802
        mime = event.mimeData()
        if mime.hasFormat(WIDGET_MIME) or self._mime_is_image_drop(mime):
            event.acceptProposedAction()
        else:
            event.ignore()

    def dragMoveEvent(self, event) -> None:  # noqa: N802
        self.dragEnterEvent(event)

    def dropEvent(self, event) -> None:  # noqa: N802
        mime = event.mimeData()
        pos = event.position().toPoint()
        sr = self.screen_rect()
        if not sr.contains(pos):
            event.ignore()
            return
        x = self._snap(pos.x() - sr.x())
        y = self._snap(pos.y() - sr.y())
        if (not mime.hasFormat(WIDGET_MIME)) and self._mime_is_image_drop(mime):
            src = self._extract_drop_image(mime)
            if not src:
                event.ignore()
                return
            self.imageDropped.emit(src, x, y)
            event.acceptProposedAction()
            return
        if not mime.hasFormat(WIDGET_MIME):
            event.ignore()
            return
        kind = bytes(mime.data(WIDGET_MIME)).decode("utf-8")
        self.widgetDropped.emit(kind, x, y)
        event.acceptProposedAction()
