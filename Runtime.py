# Runtime.py
# Importable GUI engine for 555.json (CYD board: ILI9341 + XPT2046).
# Pure engine, no application behaviour -- that lives in a separate USER
# script (e.g. Project_1.py) which imports this module.
#
# On import, it loads 555.json and draws every widget once. A touch that
# lands on a widget whose "events" list contains "click" is pushed as
# (widget_id, event, value) onto a FIFO queue (value is None for a plain
# click; switch/checkbox/slider push event "changed" with the new value).
# Widgets: label, button, memo, switch, checkbox, slider, progressbar,
# image, line, keyboard (opened by the USER script: keyboard1.show()).
#
# Touch detection is light polling, not a hardware interrupt: this
# board's Pin.irq() does not fire on the XPT2046 IRQ line (verified --
# a machine.Timer interrupt fires fine on this same firmware, so this is
# specific to Pin.irq() on this chip/pin, not interrupts in general).
# get_event()/wait_event() check the touch pin each time they're called;
# wait_event() sleeps via machine.lightsleep() between checks, so it's
# still far lighter than a tight 20ms busy loop, just not a true
# zero-power wait.
#
# USER script usage:
#
#     import Runtime as gui
#
#     while True:
#         widget_id, value = gui.wait_event()   # blocks; CPU light-sleeps
#         print("clicked:", widget_id)
#
# Or, non-blocking, folded into your own loop:
#
#     ev = gui.get_event()
#     if ev is not None:
#         widget_id, event, value = ev
#         ...
#
# Widget properties are readable by id:
#
#     gui.widgets["button1"]["text"]
#     gui.widgets["button1"]["x"]

from machine import lightsleep
import micropython
import os
import json
import framebuf
import time
import math
import gc

_boot_ms = time.ticks_ms()      # when the runtime was loaded (for LOW_POWER_GRACE_MS)

JSON_FILE = "888.json"
try:                                # design.txt (line 1) overrides it
    with open("design.txt") as _f:
        JSON_FILE = _f.read().split("\n")[0].strip() or JSON_FILE
except OSError:
    pass

# False = plain sleep between touch checks: Thonny/mpremote can stop the
# program cleanly (use while developing). True = lightsleep: lower power,
# but the board then needs ./reset.sh to be stopped.
LOW_POWER = False
LONG_PRESS_MS = 700           # how long a touch must be held for a "longpress" event (after the touch was recognised)
LOW_POWER_GRACE_MS = 10000      # LOW_POWER only starts sleeping this long after start-up, so a
                                # computer can still connect right after a reset

print()
print("Runtime: loading", JSON_FILE)

with open(JSON_FILE, "r") as f:
    data = json.load(f)

screens = {sc["id"]: sc for sc in data["screens"]}
screen = data["screens"][0]         # the CURRENT screen (first one to start)

# Public: widget properties by id. Dict preserves insertion order (same
# as the JSON list), so _zorder below stays "later = on top".
# Every widget of every screen (ids are unique across all of them); _zorder
# is only the CURRENT screen's widgets (drawn and touchable).
widgets = {}
_wscreen = {}
for _sc in data["screens"]:
    for _w in _sc["widgets"]:
        widgets[_w["id"]] = _w
        _wscreen[_w["id"]] = _sc["id"]
_zorder = list(screen["widgets"])

WIDTH = screen.get("width", 320)
HEIGHT = screen.get("height", 240)

print("Screen:", screen["id"], " widgets:", len(_zorder))


def colour(v):

    if not v.startswith("#"):
        v = v.lower()

    if v == "green": return 0x07E0
    if v == "black": return 0x0000
    if v == "white": return 0xFFFF
    if v == "red": return 0xF800
    if v == "yellow": return 0xFFE0
    if v == "blue": return 0x001F
    if v == "cyan": return 0x07FF
    if v == "magenta": return 0xF81F
    if v == "gray": return 0x8410
    if v == "grey": return 0x8410
    if v == "orange": return 0xFD20
    if v == "purple": return 0x8010
    if v == "pink": return 0xFE19
    if v == "brown": return 0xA145

    if v.startswith("#") and len(v) == 7:

        r = int(v[1:3], 16)
        g = int(v[3:5], 16)
        b = int(v[5:7], 16)

        return ((r & 0xF8) << 8) | ((g & 0xFC) << 3) | (b >> 3)

    return 0


def draw_char(d, x, y, c, fg, bg, bold=False, italic=False, scale=1, c0=0, c1=None):

    dw = 10 if italic else 9 if bold else 8

    src = bytearray(128)
    sf = framebuf.FrameBuffer(src, 8, 8, framebuf.RGB565)

    bs = ((bg & 255) << 8) | ((bg >> 8) & 255)
    fs = ((fg & 255) << 8) | ((fg >> 8) & 255)

    sf.fill(bs)
    sf.text(c, 0, 0, fs)

    dst = bytearray(dw * scale * 8 * scale * 2)
    df = framebuf.FrameBuffer(dst, dw * scale, 8 * scale, framebuf.RGB565)
    df.fill(bs)

    for sy in range(8):

        shift = (7 - sy) // 3 if italic else 0

        for sx in range(8):

            p = sf.pixel(sx, sy)

            if p != bs:

                dx = sx + shift

                if dx < dw:
                    df.fill_rect(dx * scale, sy * scale, scale, scale, p)

                if bold and dx + 1 < dw:
                    df.fill_rect((dx + 1) * scale, sy * scale, scale, scale, p)

    cw = dw * scale

    if c1 is None:
        c1 = cw

    if c0 > 0 or c1 < cw:           # draw only columns c0 .. c1-1
        crop = bytearray()
        for r in range(8 * scale):
            crop += dst[(r * cw + c0) * 2:(r * cw + c1) * 2]
        dst = crop

    d.block(x + c0, y, x + c1 - 1, y + 8 * scale - 1, dst)

    return cw


def draw_line(d, x, ww, y, line, fg, bg, bold, italic, align, scale=1, font=None):

    # Anything outside x .. x+ww is cut off at the pixel (a partial letter shows).

    if font is not None:

        tw = font.width(line)

        if align == "left":
            cx = x
        elif align == "right":
            cx = x + ww - tw
        else:
            cx = x + (ww - tw) // 2

        tmv = _pal_table(fg, bg)

        for c in line:
            cw = font.adv[font.index(c)]
            lo = max(0, x - cx)
            hi = min(cw, x + ww - cx)
            if hi > lo:
                font.draw(d, cx, y, c, tmv, lo, hi)
            cx += cw

        return

    cw = (10 if italic else 9 if bold else 8) * scale
    tw = len(line) * cw

    if align == "left":
        tx = x
    elif align == "right":
        tx = x + ww - tw
    else:
        tx = x + (ww - tw) // 2

    cx = tx

    for c in line:
        lo = max(0, x - cx)
        hi = min(cw, x + ww - cx)
        if hi > lo:
            draw_char(d, cx, y, c, fg, bg, bold, italic, scale, lo, hi)
        cx += cw


# ------------------------------------------------------------
# Bitmap fonts made by make_fonts.py (<name>_<size>[b][i].fnt)
# ------------------------------------------------------------

@micropython.viper
def _expand(g: ptr8, tbl: ptr8, out: ptr8, n: int):
    # Compiled loop: every file byte (two 4-bit alphas) -> 4 bytes of RGB565.
    i = 0
    while i < n:
        v = int(g[i]) * 4
        o = i * 4
        out[o] = tbl[v]
        out[o + 1] = tbl[v + 1]
        out[o + 2] = tbl[v + 2]
        out[o + 3] = tbl[v + 3]
        i += 1


_sb_need = 0
_sb_rbuf = _sb_cbuf = _sb_gbuf = _sb_rmv = _sb_cmv = None


def _share_buffers(wmax, h):
    # One set of letter buffers for every font, as big as the biggest font needs.
    # Buffers reused for every letter (no allocation while drawing).
    global _sb_need, _sb_rbuf, _sb_cbuf, _sb_gbuf, _sb_rmv, _sb_cmv
    need = wmax * h * 2
    if need <= _sb_need:
        return
    _sb_rbuf = _sb_cbuf = _sb_gbuf = _sb_rmv = _sb_cmv = None   # free the small ones first
    gc.collect()
    _sb_rbuf = bytearray(need)          # whole letter, even width
    _sb_cbuf = bytearray(need)          # cropped copy
    _sb_gbuf = bytearray(need // 2)     # glyph bytes from the file
    _sb_rmv = memoryview(_sb_rbuf)
    _sb_cmv = memoryview(_sb_cbuf)
    _sb_need = need


class FileFont:

    def __init__(self, path):
        self.f = open(path, "rb")
        hdr = self.f.read(4)
        self.h = hdr[0]
        self.first = hdr[1]
        self.count = hdr[2]
        tbl = self.f.read(self.count * 5)
        self.adv = [tbl[i * 5] for i in range(self.count)]
        self.off = [int.from_bytes(tbl[i * 5 + 1:i * 5 + 5], "little") for i in range(self.count)]
        self.base = 4 + self.count * 5
        # The letter buffers are shared by all fonts (see _share_buffers): a font costs
        # only its small tables here, not three buffers of its own.
        _share_buffers(max(self.adv) + 2, self.h)

    def index(self, ch):
        i = ord(ch) - self.first
        if i < 0 or i >= self.count:
            i = ord("?") - self.first
        return i

    def width(self, text):
        t = 0
        for ch in text:
            t += self.adv[self.index(ch)]
        return t

    def draw(self, d, x, y, ch, tmv, c0=0, c1=None):
        # tmv: bytearray, 256 x 4-byte table (two blended pixels per file byte), see _pal_table
        i = self.index(ch)
        w = self.adv[i]
        stride = (w + 1) // 2
        w2 = stride * 2
        h = self.h
        self.f.seek(self.base + self.off[i])
        g = _sb_gbuf
        self.f.readinto(g, stride * h)      # fills g[0:stride*h]
        _expand(g, tmv, _sb_rbuf, stride * h)
        if c1 is None:
            c1 = w
        if c0 == 0 and c1 == w2:
            d.block(x, y, x + w2 - 1, y + h - 1, _sb_rmv[:w2 * h * 2])
        else:                               # crop columns c0 .. c1-1
            cw2 = (c1 - c0) * 2
            cbuf = _sb_cbuf
            for r in range(h):
                a = (r * w2 + c0) * 2
                cbuf[r * cw2:(r + 1) * cw2] = _sb_rmv[a:a + cw2]
            d.block(x + c0, y, x + c1 - 1, y + h - 1, _sb_cmv[:cw2 * h])
        return w


def _pal_table(fg, bg):
    # 256 entries x 4 bytes: for a file byte (two 4-bit alphas) the two blended
    # RGB565 pixels, ready to copy. Cached for the last colour pair used.
    global _tbl_key, _tbl
    if _tbl_key == (fg, bg):
        return _tbl
    px = bytearray(32)
    for a in range(16):
        r = ((bg >> 11) & 31) + ((((fg >> 11) & 31) - ((bg >> 11) & 31)) * a) // 15
        g = ((bg >> 5) & 63) + ((((fg >> 5) & 63) - ((bg >> 5) & 63)) * a) // 15
        b = (bg & 31) + (((fg & 31) - (bg & 31)) * a) // 15
        c = (r << 11) | (g << 5) | b
        px[a * 2] = c >> 8
        px[a * 2 + 1] = c & 255
    t = bytearray(1024)
    for v in range(256):
        hi = (v >> 4) * 2
        lo = (v & 15) * 2
        t[v * 4] = px[hi]
        t[v * 4 + 1] = px[hi + 1]
        t[v * 4 + 2] = px[lo]
        t[v * 4 + 3] = px[lo + 1]
    _tbl_key = (fg, bg)
    _tbl = t
    return _tbl


_tbl_key = None
_tbl = None


FONT_DIR = "fonts"        # font files live in this folder on the board
_font_cache = {}
_font_files = None


def _slug(name):
    return "".join(c for c in name.lower() if "a" <= c <= "z" or "0" <= c <= "9")


def widget_font(w):
    """The FileFont a widget asks for with font_type/font_size/bold/italic,
    or None for the built-in 8x8 font (also when no matching file exists)."""

    global _font_files

    ft = w.get("font_type", "default")

    if ft in ("", "default"):
        return None

    if _font_files is None:
        try:
            _font_files = os.listdir(FONT_DIR)      # a small folder: fast
        except OSError:
            _font_files = []

    sl = _slug(ft)
    style = ("b" if w.get("bold", False) else "") + ("i" if w.get("italic", False) else "")

    try:
        want = int(w.get("font_size", 16))
    except (ValueError, TypeError):
        want = 16

    best = None
    for n in _font_files:
        if n.startswith(sl + "_") and n.endswith(style + ".fnt"):
            mid = n[len(sl) + 1:-len(style + ".fnt")]
            if mid.isdigit() and (best is None or abs(int(mid) - want) < abs(best - want)):
                best = int(mid)

    if best is None:
        return None

    path = "%s/%s_%d%s.fnt" % (FONT_DIR, sl, best, style)

    if path not in _font_cache:
        _font_cache[path] = FileFont(path)

    return _font_cache[path]


def fsize(w):
    """Text scale from a widget's font_size: default/8 -> 1, 16 -> 2, 24 -> 3."""
    try:
        return max(1, min(3, int(w.get("font_size", 8)) // 8))
    except (ValueError, TypeError):
        return 1


# Hardware comes from a board profile (board_*.py): JSON target.board, else the
# 2nd line of design.txt, else board_cyd. See hardware/ for the catalogue.
_board_name = data.get("target", {}).get("board", "")

if not _board_name:
    try:
        with open("design.txt") as _f:
            _l = _f.read().split("\n")
            _board_name = _l[1].strip() if len(_l) > 1 else ""
    except OSError:
        pass

board = __import__(_board_name or "board_cyd")
print("Board:", board.NAME)

display = board.make_display(WIDTH, HEIGHT)

display.clear(colour(screen.get("background", "black")))


# ============================================================
# DRAW WIDGETS
# ============================================================

def _draw_text_widget(w):

    if not w.get("visible", True):
        return

    x = w["x"]
    y = w["y"]
    ww = w["w"]
    h = w["h"]

    bg = _bg(w)
    fg = colour(w.get("color", "white"))

    border = w.get("border", {})
    bc = colour(border.get("color", "black"))
    bw = border.get("width", 0)

    text = w.get("text", "")
    align = w.get("alignment", "center")
    bold = w.get("bold", False)
    italic = w.get("italic", False)

    display.fill_rectangle(x, y, ww, h, bg)

    if bw:

        bw = min(bw, ww // 2, h // 2)

        for i in range(bw):

            display.fill_rectangle(x + i, y + i, ww - 2 * i, 1, bc)
            display.fill_rectangle(x + i, y + h - 1 - i, ww - 2 * i, 1, bc)
            display.fill_rectangle(x + i, y + i, 1, h - 2 * i, bc)
            display.fill_rectangle(x + ww - 1 - i, y + i, 1, h - 2 * i, bc)

    if not text:
        return

    font = widget_font(w)
    sc = fsize(w)
    cell_h = font.h if font else 8 * sc
    lines = text.split("\n")
    line_h = cell_h + 2
    block_h = len(lines) * line_h

    pad = bw + 1 if bw else 0       # text stays inside the border

    if w.get("widget") == "memo":
        ty = y + pad + 1            # a memo starts at the top (labels/buttons are centred)
    else:
        ty = y + (h - block_h) // 2

    for line in lines:

        # lines that don't fit inside the widget vertically are clipped
        if line and ty >= y + pad and ty + cell_h <= y + h - pad:
            draw_line(display, x + pad, ww - 2 * pad, ty, line, fg, bg, bold, italic, align, sc, font)

        ty += line_h


def _bg(w):
    b = w.get("background", "black")
    if b == "transparent":
        b = screen.get("background", "black")
    return colour(b)


def _label(w, tx, avail):
    # Left-aligned, vertically centred caption used by switch/checkbox.
    text = w.get("text", "")
    if text:
        font = widget_font(w)
        sc = fsize(w)
        ty = w["y"] + (w["h"] - (font.h if font else 8 * sc)) // 2
        draw_line(display, tx, avail, ty, text, colour(w.get("color", "white")),
                  _bg(w), w.get("bold", False), w.get("italic", False), "left", sc, font)


def _frac(w):
    lo = w.get("min", 0)
    hi = w.get("max", 100)
    if hi == lo:
        return 0
    f = (w.get("value", lo) - lo) / (hi - lo)
    return max(0.0, min(1.0, f))


def _draw_x(x, y, size, colr):
    # An X, two pixels thick, inside a size x size square at (x, y).
    for d in (0, 1):
        display.draw_line(x + d, y, x + size - 1, y + size - 1 - d, colr)
        display.draw_line(x, y + d, x + size - 1 - d, y + size - 1, colr)
        display.draw_line(x + d, y + size - 1, x + size - 1, y + d, colr)
        display.draw_line(x, y + size - 1 - d, x + size - 1 - d, y, colr)


def _draw_switch(w):
    x = w["x"]; y = w["y"]; h = w["h"]
    display.fill_rectangle(x, y, w["w"], h, _bg(w))
    th = h - 4
    tw = th * 2
    ty = y + (h - th) // 2
    on = w.get("value", False)
    display.fill_rectangle(x, ty, tw, th, colour("green" if on else "gray"))
    kw = th - 4
    kx = x + tw - 2 - kw if on else x + 2
    display.fill_rectangle(kx, ty + 2, kw, kw, colour("white"))
    if on:
        _draw_x(kx + 4, ty + 6, kw - 8, colour("black"))
    _label(w, x + tw + 8, w["w"] - tw - 8)


def _draw_checkbox(w):
    x = w["x"]; y = w["y"]; h = w["h"]
    display.fill_rectangle(x, y, w["w"], h, _bg(w))
    bs = min(h, 20)
    by = y + (h - bs) // 2
    white = colour("white")
    display.fill_rectangle(x, by, bs, bs, white)
    display.fill_rectangle(x + 2, by + 2, bs - 4, bs - 4, colour("black"))
    if w.get("value", False):
        _draw_x(x + 4, by + 4, bs - 8, colour("white"))
    _label(w, x + bs + 8, w["w"] - bs - 8)


def _draw_bar(w, thumb):
    # Shared by progressbar (no thumb) and slider (thumb). Horizontal if
    # wider than tall, otherwise vertical (fills from the bottom).
    x = w["x"]; y = w["y"]; ww = w["w"]; h = w["h"]
    f = _frac(w)
    display.fill_rectangle(x, y, ww, h, colour(w.get("background", "gray")))
    col = colour(w.get("color", "green"))
    white = colour("white")
    if ww >= h:
        fw = int(ww * f)
        if fw:
            display.fill_rectangle(x, y, fw, h, col)
        if thumb:
            tx = x + int((ww - 8) * f)
            display.fill_rectangle(tx, y, 8, h, white)
    else:
        fh = int(h * f)
        if fh:
            display.fill_rectangle(x, y + h - fh, ww, fh, col)
        if thumb:
            ty = y + h - 8 - int((h - 8) * f)
            display.fill_rectangle(x, ty, ww, 8, white)


def _slider_r(w):
    # Radius of the slider's round knob: about half the widget's thickness, never tiny.
    return max(5, min(w["w"], w["h"]) // 2 - 1)


def _draw_slider(w):
    # A thin track with a ROUND knob (a ring in the slider's colour with a white centre), so it cannot be
    # mistaken for a progress bar. Horizontal if wider than tall, otherwise vertical (the low end at the bottom).
    x = w["x"]; y = w["y"]; ww = w["w"]; h = w["h"]
    f = _frac(w)
    r = _slider_r(w)
    t = 4                                               # track thickness
    track = colour(w.get("background", "gray"))
    col = colour(w.get("color", "green"))
    display.fill_rectangle(x, y, ww, h, colour(screen.get("background", "black")))   # clear the widget's area
    if ww >= h:
        cy = y + h // 2
        x0 = x + r
        span = ww - 2 * r
        kx = x0 + int(span * f)
        display.fill_rectangle(x0, cy - t // 2, span, t, track)
        if kx > x0:
            display.fill_rectangle(x0, cy - t // 2, kx - x0, t, col)
        display.fill_circle(kx, cy, r, col)
        display.fill_circle(kx, cy, r - 3, colour("white"))
    else:
        cx = x + ww // 2
        y1 = y + h - r                                  # position of the lowest value
        span = h - 2 * r
        ky = y1 - int(span * f)
        display.fill_rectangle(cx - t // 2, y1 - span, t, span, track)
        if ky < y1:
            display.fill_rectangle(cx - t // 2, ky, t, y1 - ky, col)
        display.fill_circle(cx, ky, r, col)
        display.fill_circle(cx, ky, r - 3, colour("white"))


def _draw_line_widget(w):
    # From (x, y) to (x + w, y + h); thickness is centred on the line.
    x1 = w["x"]; y1 = w["y"]
    x2 = x1 + w["w"]; y2 = y1 + w["h"]
    t = w.get("thickness", 1)
    c = colour(w.get("color", "white"))
    lo = -(t // 2)

    if y1 == y2:
        display.fill_rectangle(min(x1, x2), y1 + lo, abs(x2 - x1) + 1, t, c)
    elif x1 == x2:
        display.fill_rectangle(x1 + lo, min(y1, y2), t, abs(y2 - y1) + 1, c)
    else:
        steep = abs(y2 - y1) > abs(x2 - x1)
        for i in range(lo, lo + t):
            if steep:
                display.draw_line(x1 + i, y1, x2 + i, y2, c)
            else:
                display.draw_line(x1, y1 + i, x2, y2 + i, c)


def _draw_image(w):
    # <widget id>.raw = RGB565 pixels at exactly w x h, made on the desktop
    # by make_images.py (the board can't decode JPEG/PNG).
    x = w["x"]; y = w["y"]; ww = w["w"]; h = w["h"]
    try:
        display.draw_image(w["id"] + ".raw", x, y, ww, h)
    except OSError:
        display.fill_rectangle(x, y, ww, h, colour(w.get("background", "gray")))


# ------------------------------------------------------------
# choice (radio group; dropdown comes next) -- "style" picks the look
# ------------------------------------------------------------

def _border_box(w, bw):
    # Plain rectangular frame inside the widget's area, bw pixels thick.
    x = w["x"]; y = w["y"]; ww = w["w"]; h = w["h"]
    bc = colour(w.get("border", {}).get("color", "gray"))
    for i in range(min(bw, ww // 2, h // 2)):
        display.fill_rectangle(x + i, y + i, ww - 2 * i, 1, bc)
        display.fill_rectangle(x + i, y + h - 1 - i, ww - 2 * i, 1, bc)
        display.fill_rectangle(x + i, y + i, 1, h - 2 * i, bc)
        display.fill_rectangle(x + ww - 1 - i, y + i, 1, h - 2 * i, bc)


def _radio_slot(w):
    # (x0, y0, slot_w, slot_h, horizontal): the area of ONE item. The widget's inner area is
    # divided equally between the items (by height if vertical, by width if horizontal).
    bw = w.get("border", {}).get("width", 0)
    n = max(1, len(w.get("items", [])))
    iw = w["w"] - 2 * bw
    ih = w["h"] - 2 * bw
    horizontal = w.get("orientation", "vertical") == "horizontal"
    if horizontal:
        return w["x"] + bw, w["y"] + bw, iw // n, ih, True
    return w["x"] + bw, w["y"] + bw, iw, ih // n, False


def _draw_radio(w, only=None):
    # only=None: draw the whole group. only=(a, b): redraw just those items (after a tap).
    x = w["x"]; y = w["y"]
    fg = colour(w.get("color", "white"))
    bg = _bg(w)
    bw = w.get("border", {}).get("width", 0)
    if only is None:
        display.fill_rectangle(x, y, w["w"], w["h"], bg)
        if bw:
            _border_box(w, bw)

    x0, y0, sw, sh, horizontal = _radio_slot(w)
    font = widget_font(w)
    sc = fsize(w)
    cell_h = font.h if font else 8 * sc
    r = max(3, min(cell_h // 2 + 2, sh // 2 - 2))
    sel = w.get("selected", -1)
    bold = w.get("bold", False)
    italic = w.get("italic", False)
    items = w.get("items", [])

    for i in range(len(items)):
        if only is not None and i not in only:
            continue
        sx = x0 + (i * sw if horizontal else 0)
        sy = y0 + (0 if horizontal else i * sh)
        if only is not None:
            display.fill_rectangle(sx, sy, sw, sh, bg)      # clear just this item
        cx = sx + 4 + r
        cy = sy + sh // 2
        display.draw_circle(cx, cy, r, fg)
        if i == sel:
            display.fill_circle(cx, cy, max(1, r - 2), fg)
        tx = cx + r + 6
        avail = sx + sw - tx - 2
        if avail > 0 and cy - cell_h // 2 >= sy:
            draw_line(display, tx, avail, cy - cell_h // 2, items[i], fg, bg, bold, italic, "left", sc, font)


def _draw_dropdown(w):
    # The CLOSED field: border, the chosen item's text, a small arrow on the right.
    x = w["x"]; y = w["y"]; ww = w["w"]; h = w["h"]
    fg = colour(w.get("color", "white"))
    bg = _bg(w)
    bw = w.get("border", {}).get("width", 0)
    display.fill_rectangle(x, y, ww, h, bg)
    if bw:
        _border_box(w, bw)
    font = widget_font(w)
    sc = fsize(w)
    cell_h = font.h if font else 8 * sc
    items = w.get("items", [])
    sel = w.get("selected", -1)
    if 0 <= sel < len(items):
        draw_line(display, x + bw + 4, ww - 2 * bw - 26, y + (h - cell_h) // 2, items[sel], fg, bg,
                  w.get("bold", False), w.get("italic", False), "left", sc, font)
    ax = x + ww - 14
    ay = y + h // 2 - 2
    for k in range(5):
        display.fill_rectangle(ax - 4 + k, ay + k, 9 - 2 * k, 1, fg)


def _dropdown_list(w, top, ly, vis, bar):
    # Draws the open list (vis rows from item `top`), plus a scroll bar if bar > 0.
    x = w["x"]; ww = w["w"]; rh = w["h"]
    fg = colour(w.get("color", "white"))
    bg = _bg(w)
    font = widget_font(w)
    sc = fsize(w)
    cell_h = font.h if font else 8 * sc
    items = w.get("items", [])
    sel = w.get("selected", -1)
    rw = ww - bar
    for r in range(vis):
        idx = top + r
        ry = ly + r * rh
        on = idx == sel
        display.fill_rectangle(x, ry, rw, rh, fg if on else bg)
        draw_line(display, x + 4, rw - 8, ry + (rh - cell_h) // 2, items[idx], bg if on else fg,
                  fg if on else bg, w.get("bold", False), w.get("italic", False), "left", sc, font)
    lh = vis * rh
    if bar:
        n = len(items)
        display.fill_rectangle(x + rw, ly, bar, lh, bg)
        display.fill_rectangle(x + rw + 2, ly + 2, bar - 4, lh - 4, colour("#404040"))
        th = max(8, (lh - 4) * vis // n)
        ty = ly + 2 + ((lh - 4) - th) * top // max(1, n - vis)
        display.fill_rectangle(x + rw + 2, ty, bar - 4, th, colour("#c0c0c0"))
    bc = colour(w.get("border", {}).get("color", "gray"))
    display.fill_rectangle(x, ly, ww, 1, bc)
    display.fill_rectangle(x, ly + lh - 1, ww, 1, bc)
    display.fill_rectangle(x, ly, 1, lh, bc)
    display.fill_rectangle(x + ww - 1, ly, 1, lh, bc)


def _dropdown_open(w):
    # Takes over like the keyboard: shows the list over the screen until an item is tapped
    # (chosen) or a tap lands outside (cancel). Tasks pause meanwhile.
    x = w["x"]; y = w["y"]; ww = w["w"]; rh = w["h"]
    items = w.get("items", [])
    n = len(items)
    if n == 0:
        return
    below = HEIGHT - (y + rh)
    above = y
    down = below >= above or below >= rh * min(n, 3)
    avail = below if down else above
    vis = max(1, min(n, avail // rh))
    lh = vis * rh
    ly = y + rh if down else y - lh
    bar = 16 if n > vis else 0
    old = w.get("selected", -1)
    top = 0 if old < vis else old - vis + 1      # start at the FIRST item; scroll only if the chosen one is out of sight

    _dropdown_list(w, top, ly, vis, bar)

    while touch.pressed():                  # the tap that opened it may still be down
        time.sleep_ms(10)

    chosen = None
    while True:
        if not touch.pressed():
            time.sleep_ms(20)
            continue
        p = _read_point(5, 20)
        while touch.pressed():
            time.sleep_ms(10)
        if p is None:
            continue
        if x <= p[0] < x + ww and ly <= p[1] < ly + lh:
            if bar and p[0] >= x + ww - bar:            # scroll bar: ends = one row, middle = jump
                step, frac = _bar_zone(p[1], ly, lh)
                top = max(0, min(n - vis, top + step)) if step else max(0, min(n - vis, int(frac * (n - vis) + 0.5)))
                _dropdown_list(w, top, ly, vis, bar)
                continue
            chosen = top + (p[1] - ly) // rh
            break
        break                                           # tap outside = cancel

    _repaint_area(x, ly, x + ww, ly + lh)               # remove the list, restore what was under it
    if chosen is not None and chosen != old:
        w["selected"] = chosen
        _draw_dropdown(w)
        if "changed" in w.get("events", []):
            _queue.append((w["id"], "changed", chosen))


# ------------------------------------------------------------
# tree (menu): up to 3 levels, parents open/close, end items are selected
# ------------------------------------------------------------
#
# "items": [{"text": "Display", "items": [{"text": "Brightness"}, ...]}, ...]
# The state (which branches are open, how far it is scrolled) lives here, not in the JSON.
# Row height follows the font (character height + 12 px); each level indents 3 characters.

_tree_state = {}


def _tstate(w):
    st = _tree_state.get(w["id"])
    if st is None:
        st = {"open": [], "top": 0}
        _tree_state[w["id"]] = st
    return st


def _tree_walk(items, level, prefix, openl, rows):
    for it in items:
        path = prefix + it["text"]
        kids = it.get("items")
        is_open = path in openl
        rows.append((path, it["text"], level, bool(kids), is_open))
        if kids and is_open:
            _tree_walk(kids, level + 1, path + "/", openl, rows)


def _tree_rows(w):
    rows = []
    _tree_walk(w.get("items", []), 0, "", _tstate(w)["open"], rows)
    return rows


def _tree_geom(w):
    # (row_h, char_w, cell_h, font, sc, visible_rows, bar_w)
    font = widget_font(w)
    sc = fsize(w)
    cell_h = font.h if font else 8 * sc
    cw = font.adv[font.index(" ")] if font else 8 * sc
    bw = w.get("border", {}).get("width", 0)
    row_h = cell_h + 12
    vis = max(1, (w["h"] - 2 * bw) // row_h)
    bar = 16 if len(_tree_rows(w)) > vis else 0
    return row_h, cw, cell_h, font, sc, vis, bar


def _draw_tree(w, only=None, first=0):
    # only=None: everything (or, with first=k, rows k.. downwards). only=(a, b): just those rows.
    x = w["x"]; y = w["y"]; ww = w["w"]; h = w["h"]
    fg = colour(w.get("color", "white"))
    bg = _bg(w)
    bw = w.get("border", {}).get("width", 0)
    st = _tstate(w)
    rows = _tree_rows(w)
    row_h, cw, cell_h, font, sc, vis, bar = _tree_geom(w)
    maxtop = max(0, len(rows) - vis)
    if st["top"] > maxtop:
        st["top"] = maxtop
    top = st["top"]
    if only is None and first == 0:
        display.fill_rectangle(x, y, ww, h, bg)
        if bw:
            _border_box(w, bw)
    rw = ww - 2 * bw - bar
    sel = w.get("selected", "")
    bold = w.get("bold", False)
    italic = w.get("italic", False)

    for r in range(vis):
        i = top + r
        if only is not None and i not in only:
            continue
        if only is None and r < first:
            continue
        ry = y + bw + r * row_h
        if i >= len(rows):
            display.fill_rectangle(x + bw, ry, rw, row_h, bg)
            continue
        path, text, level, parent, is_open = rows[i]
        on = (path == sel) and not parent
        rf = bg if on else fg
        rb = fg if on else bg
        display.fill_rectangle(x + bw, ry, rw, row_h, rb)
        tx = x + bw + 4 + level * 3 * cw
        ty = ry + (row_h - cell_h) // 2
        if parent:
            draw_line(display, tx, 2 * cw, ty, "-" if is_open else "+", rf, rb, bold, italic, "left", sc, font)
        draw_line(display, tx + 2 * cw, x + bw + rw - tx - 2 * cw, ty, text, rf, rb, bold, italic,
                  "left", sc, font)

    if bar and only is None:
        bx = x + ww - bw - bar
        display.fill_rectangle(bx, y + bw, bar, h - 2 * bw, bg)
        th_all = h - 2 * bw - 4
        display.fill_rectangle(bx + 2, y + bw + 2, bar - 4, th_all, colour("#404040"))
        kh = max(8, th_all * vis // len(rows))
        ky = y + bw + 2 + (th_all - kh) * top // max(1, len(rows) - vis)
        display.fill_rectangle(bx + 2, ky, bar - 4, kh, colour("#c0c0c0"))


def _tree_tap(w, px, py):
    # Handles a tap on a tree: scroll bar, open/close a parent, or select an end item.
    x = w["x"]; y = w["y"]; ww = w["w"]
    bw = w.get("border", {}).get("width", 0)
    st = _tstate(w)
    rows = _tree_rows(w)
    row_h, cw, cell_h, font, sc, vis, bar = _tree_geom(w)

    if bar and px >= x + ww - bw - bar:                       # scroll bar: ends = one row, middle = jump
        step, frac = _bar_zone(py, y + bw, w["h"] - 2 * bw)
        last = len(rows) - vis
        st["top"] = max(0, min(last, st["top"] + step)) if step else max(0, min(last, int(frac * last + 0.5)))
        _draw_tree(w)
        return

    r = (py - (y + bw)) // row_h
    i = st["top"] + r
    if r < 0 or r >= vis or i >= len(rows):
        return
    path, text, level, parent, is_open = rows[i]

    if parent:                                                  # open / close the branch
        if is_open:
            st["open"].remove(path)
        else:
            st["open"].append(path)
        n = len(_tree_rows(w))
        maxtop = max(0, n - vis)
        full = False
        if st["top"] > maxtop:                                  # fewer rows now: the list scrolls back
            st["top"] = maxtop
            full = True
        if bar != (16 if n > vis else 0):                       # scroll bar appeared/vanished
            full = True
        if full:
            _draw_tree(w)                                       # everything shifts: redraw it all
        else:
            _draw_tree(w, None, r)                              # this row and everything below
        return

    old = w.get("selected", "")
    if path != old:
        w["selected"] = path
        _draw_tree(w, (_tree_index(w, old), i))
        if "selected" in w.get("events", []):
            _queue.append((w["id"], "selected", path))


def _tree_index(w, path):
    # Row number of `path` in the current list of rows, or -1 (hidden / not found).
    n = 0
    for row in _tree_rows(w):
        if row[0] == path:
            return n
        n += 1
    return -1


def _tree_reveal(w):
    # After a script sets .selected: open the branches above the item and scroll it into view.
    path = w.get("selected", "")
    if not path:
        return
    st = _tstate(w)
    parts = path.split("/")
    acc = ""
    for k in range(len(parts) - 1):
        acc = parts[k] if k == 0 else acc + "/" + parts[k]
        if acc not in st["open"]:
            st["open"].append(acc)
    idx = _tree_index(w, path)
    if idx >= 0:
        vis = _tree_geom(w)[5]
        if idx < st["top"]:
            st["top"] = idx
        elif idx >= st["top"] + vis:
            st["top"] = idx - vis + 1


def _draw_choice(w):
    if w.get("style", "radio") == "radio":
        _draw_radio(w)
    else:
        _draw_dropdown(w)


# ---- gauge: a round dial with a needle (display only) ------------------------------------------------------
def _num_text(v):
    return str(int(v)) if v == int(v) else "%.1f" % v


def _text_c(w, cx, y, ww, text, fg, bg):
    # One line of text centred on cx, in the widget's font; returns its height.
    font = widget_font(w)
    sc = fsize(w)
    draw_line(display, cx - ww // 2, ww, y, text, fg, bg, w.get("bold", False), w.get("italic", False), "center", sc, font)
    return font.h if font else 8 * sc


def _gauge_geom(w):
    d = w.get("diameter", 0) or min(w["w"], w["h"])
    sweep = w.get("sweep", 270)
    return w["x"] + w["w"] // 2, w["y"] + w["h"] // 2, d // 2 - 1, 90 + sweep / 2, sweep


_ring_cache = {}
_gauge_buf = {}
_tick_cache = {}


def _gauge_render(w, full):
    # The dial is drawn into a small framebuffer in bands of 12 rows (fast, in C) and each band is sent to the display with
    # one block() call. full=True: the whole dial. full=False (the value changed): only the rectangle that holds the old
    # and the new needle; the circle and the tick marks are drawn into it again, so they stay where they are.
    cx, cy, r, start, sweep = _gauge_geom(w)
    sbg = _sw(colour(screen.get("background", "black")))
    white = _sw(colour("white"))
    ring = _sw(colour(w.get("background", "gray")))
    needle = _sw(colour(w.get("color", "red")))
    a = math.radians(start - sweep * _frac(w))
    nx = int((r - 13) * math.cos(a))
    ny = -int((r - 13) * math.sin(a))
    n = max(1, w.get("ticks", 10))
    old = _gauge_last.get(w["id"])
    if full or not isinstance(old, tuple):
        lx0 = cx - r - 1; ly0 = cy - r - 1; lx1 = cx + r + 1; ly1 = cy + r + 1
    else:
        lx0 = cx + min(0, nx, old[0]) - 5; lx1 = cx + max(0, nx, old[0]) + 6
        ly0 = cy + min(0, ny, old[1]) - 5; ly1 = cy + max(0, ny, old[1]) + 6
        lx0 = max(lx0, cx - r - 1); ly0 = max(ly0, cy - r - 1); lx1 = min(lx1, cx + r + 1); ly1 = min(ly1, cy + r + 1)
    _gauge_last[w["id"]] = (nx, ny)
    side = lx1 - lx0 + 1
    ring_pts = _ring_cache.get(r)               # the same for every update of this dial: built once, not on every needle move
    if ring_pts is None:
        ring_pts = []
        for i in range(72):
            t0_ = math.radians(i * 5); t1_ = math.radians(i * 5 + 5)
            ring_pts.append((int(round(r * math.cos(t0_))), int(round(r * math.sin(t0_))),
                             int(round(r * math.cos(t1_))), int(round(r * math.sin(t1_)))))
        _ring_cache[r] = ring_pts
    tk = (r, start, sweep, n, w.get("show_ticks", True))
    tick_pts = _tick_cache.get(w["id"])          # also the same on every update of this dial
    if tick_pts is None or tick_pts[0] != tk:
        pts = []
        if tk[4]:
            for i in range(n + 1):
                t = math.radians(start - sweep * i / n)
                c = math.cos(t); sn = math.sin(t)
                pts.append((int((r - 2) * c), -int((r - 2) * sn), int((r - 8) * c), -int((r - 8) * sn)))
        tick_pts = _tick_cache[w["id"]] = (tk, pts)
    tick_pts = tick_pts[1]
    need = (2 * r + 3) * 12 * 2                 # the largest the dirty rectangle can be, so the buffer never has to grow
    buf = _gauge_buf.get(w["id"])               # one buffer per gauge, kept: a new one each time fragments the heap
    if buf is None or len(buf) < need:
        buf = _gauge_buf[w["id"]] = bytearray(need)
    for by in range(ly0, ly1 + 1, 12):
        rr = min(12, ly1 + 1 - by)
        fb = framebuf.FrameBuffer(buf, side, rr, framebuf.RGB565)
        fb.fill(sbg)
        ox = cx - lx0; oy = cy - by                     # the centre of the dial inside this band
        for px, py, qx, qy in ring_pts:                # the ring as 72 short lines (framebuf's ellipse leaves gaps)
            fb.line(ox + px, oy + py, ox + qx, oy + qy, ring)
        for px, py, qx, qy in tick_pts:
            fb.line(ox + px, oy + py, ox + qx, oy + qy, white)
        fb.line(ox, oy, ox + nx, oy + ny, needle)
        fb.line(ox + 1, oy, ox + nx + 1, oy + ny, needle)
        fb.ellipse(ox, oy, 4, 4, white, True)
        display.block(lx0, by, lx1, by + rr - 1, memoryview(buf)[:side * rr * 2])


def _gauge_text(w):
    cx, cy, r, start, sweep = _gauge_geom(w)
    sbg = colour(screen.get("background", "black"))
    ty = cy + r // 2
    font = widget_font(w)
    th = font.h if font else 8 * fsize(w)
    lines = [(t, f) for t, f, show in ((_num_text(w.get("value", 0)), "white", w.get("show_value", True)),
                                       (w.get("text", ""), "gray", w.get("text"))) if show]
    if lines:
        # A bigger font on a small dial: lift the lines until the last one has room inside the dial (else it is cut off).
        last = lines[-1][0]
        tw = font.width(last) if font else 8 * fsize(w) * len(last)
        while ty > cy:
            low = ty + len(lines) * (th + 2) - 2 - cy
            if 2 * int(math.sqrt(max(0, (r - 10) * (r - 10) - low * low))) >= tw:
                break
            ty -= 2
    for text, fg in lines:
        low = ty + th - cy                                   # the bottom of this line, below the centre
        room = int(math.sqrt(max(0, (r - 10) * (r - 10) - low * low)))     # half the width inside the dial there
        _text_c(w, cx, ty, max(8, 2 * room), text, colour(fg), sbg)
        ty += th + 2


_gauge_last = {}        # ids of the gauges that are on the display


def _draw_gauge(w):
    display.fill_rectangle(w["x"], w["y"], w["w"], w["h"], colour(screen.get("background", "black")))
    _gauge_render(w, True)
    _gauge_text(w)


def _gauge_value_changed(w):
    # Only the inside of the dial (needle, number, caption) is redrawn: the circle and the tick marks stay.
    _gauge_render(w, False)
    _gauge_text(w)


# ---- waveform: a moving trace of the last values given to waveform1.add(v); barchart: fixed bars -------------------------------------------
_chart_data = {}


def _chart_frame(w):
    # The part that never changes between updates: background, border and title. Returns the plot area (x0, y0, x1, y1).
    x = w["x"]; y = w["y"]; ww = w["w"]; h = w["h"]
    bgc = colour(w.get("background", "black"))
    display.fill_rectangle(x, y, ww, h, bgc)
    display.draw_rectangle(x, y, ww, h, colour("gray"))
    top = y + 2
    if w.get("title"):
        font = widget_font(w)
        draw_line(display, x + 4, ww - 8, y + 3, w["title"], colour("gray"), bgc, False, False, "left", fsize(w), font)
        top = y + 5 + (font.h if font else 8 * fsize(w))
    x0, top, x1, bot = _chart_area(w)
    labels = w.get("labels") if w["widget"] == "barchart" else None
    if labels:
        font = widget_font(w); sc = fsize(w)
        n = max(1, w.get("bars", 20))
        sw = (x1 - x0) / n
        for i in range(min(n, len(labels))):
            bx = x0 + int(sw * i)
            draw_line(display, bx, int(sw), bot + 2, str(labels[i]), colour("gray"), bgc, False, False, "center", sc, font)
    return x0, top, x1, bot


def _sw(c):
    return ((c & 255) << 8) | ((c >> 8) & 255)         # the display wants the two bytes of a colour the other way round


def _chart_plot(w):
    # The part that changes: the area inside the frame, the grid and the data. It is drawn in bands of 12 pixel rows
    # into a small framebuffer (fast, in C) and each band is sent to the display with ONE block() call.
    kind = w["widget"]
    x0, top, x1, bot = _chart_area(w)
    bars = kind == "barchart" or w.get("style") == "bars"
    lo = w.get("min", 0); hi = w.get("max", 100)
    if hi == lo:
        hi = lo + 1
    pw = x1 - x0
    ph = bot - top
    bgc = _sw(colour(w.get("background", "black")))
    dark = _sw(colour("#303030"))
    col = _sw(colour(w.get("color", "green")))
    grid = [ph * i // 4 for i in range(1, 4)] if w.get("grid", True) else []
    data = _chart_get(w) or []
    shapes = []                                  # ("r", x, y, w, h) filled rectangles / ("l", x1, y1, x2, y2) lines, plot coordinates
    if not bars:
        n = w.get("points", 60)
        px = py = None
        for i in range(len(data)):
            v = max(lo, min(hi, data[i]))
            qx = 1 + (pw - 3) * i // max(1, n - 1)
            qy = ph - 3 - int((ph - 4) * (v - lo) / (hi - lo))
            if px is not None:
                shapes.append((1, px, py, qx, qy))
            px = qx; py = qy
    else:
        n = max(1, w.get("bars", 20) if kind == "barchart" else w.get("points", 60))
        sw = pw / n                                     # width of one slot
        gap = 1 if sw >= 3 else 0
        for i in range(len(data)):
            v = max(lo, min(hi, data[i]))
            bh = int(ph * (v - lo) / (hi - lo))
            if bh > 0:
                bx = int(sw * i)
                shapes.append((0, bx, ph - bh, max(1, int(sw * (i + 1)) - bx - gap), bh))
    rows = 12
    buf = _gauge_buf.get(w["id"])               # one buffer per chart, kept (a new one each redraw fragments the heap)
    if buf is None or len(buf) < pw * rows * 2:
        buf = _gauge_buf[w["id"]] = bytearray(pw * rows * 2)
    for by in range(0, ph, rows):
        r = min(rows, ph - by)
        fb = framebuf.FrameBuffer(buf, pw, r, framebuf.RGB565)
        fb.fill(bgc)
        for g in grid:
            fb.hline(0, g - by, pw, dark)
        for sh in shapes:
            if sh[0]:
                fb.line(sh[1], sh[2] - by, sh[3], sh[4] - by, col)
            else:
                fb.fill_rect(sh[1], sh[2] - by, sh[3], sh[4], col)
        display.block(x0, top + by, x1 - 1, top + by + r - 1, memoryview(buf)[:pw * r * 2])
    if bars and w.get("show_values", False):
        font = widget_font(w); th = font.h if font else 8 * fsize(w)
        n = max(1, w.get("bars", 20))
        sw = pw / n
        for i in range(len(data)):
            v = max(lo, min(hi, data[i]))
            bh = int(ph * (v - lo) / (hi - lo))
            draw_line(display, x0 + int(sw * i), int(sw), max(top, bot - bh - th - 1), _num_text(data[i]), colour("white"),
                      colour(w.get("background", "black")), False, False, "center", fsize(w), font)


def _chart_get(w):
    # The values on show. A fixed bar chart starts with the design's "values" (a chart that is never updated).
    d = _chart_data.get(w["id"])
    if d is None:
        if w["widget"] == "barchart":
            n = w.get("bars", 20)
            d = (list(w.get("values", [])) + [w.get("min", 0)] * n)[:n]
        else:
            d = []
        _chart_data[w["id"]] = d
    return d


def _chart_area(w):
    top = w["y"] + 2
    if w.get("title"):
        font = widget_font(w)
        top = w["y"] + 5 + (font.h if font else 8 * fsize(w))
    bot = w["y"] + w["h"] - 2
    if w.get("labels") and w["widget"] == "barchart":
        font = widget_font(w)
        bot -= (font.h if font else 8 * fsize(w)) + 3
    return w["x"] + 2, top, w["x"] + w["w"] - 2, bot


def _draw_chart(w):
    _chart_frame(w)
    _chart_plot(w)


_draw_barchart = _draw_chart


_chart_dirty = {}                  # chart id -> True: new data that is not on the display yet
_chart_last = {}                   # chart id -> time of its last redraw


def _chart_refresh(widget_id):
    # Only the plot area is redrawn, so the border and the title do not flicker. "update_ms" is the shortest time
    # between two redraws: data that arrives sooner is kept and drawn a little later (see _chart_flush).
    w = widgets[widget_id]
    if w.get("visible", True) and _wscreen[widget_id] == screen["id"]:
        gap = w.get("update_ms", 0)
        now_ = time.ticks_ms()
        if gap and widget_id in _chart_last and time.ticks_diff(now_, _chart_last[widget_id]) < gap:
            _chart_dirty[widget_id] = True
            return
        _chart_dirty.pop(widget_id, None)
        _chart_plot(w)
        _chart_last[widget_id] = time.ticks_ms()


def _chart_flush():
    # Called from the touch poll: draws charts whose last update had to wait.
    for wid in list(_chart_dirty):
        if time.ticks_diff(time.ticks_ms(), _chart_last.get(wid, 0)) >= widgets[wid].get("update_ms", 0):
            _chart_refresh(wid)


def _chart_add(widget_id, value):
    w = widgets[widget_id]
    data = _chart_get(w)
    data.append(value)
    n = w.get("points", 60) if w["widget"] == "waveform" else w.get("bars", 20)
    while len(data) > n:
        data.pop(0)
    _chart_refresh(widget_id)


def _chart_clear(widget_id):
    w = widgets[widget_id]
    _chart_data[widget_id] = [w.get("min", 0)] * w.get("bars", 20) if w["widget"] == "barchart" else []
    _chart_refresh(widget_id)


def _chart_set(widget_id, index, value):
    # barchart: sets bar number `index` (0 = the first)
    data = _chart_get(widgets[widget_id])
    if 0 <= index < len(data):
        data[index] = value
        _chart_refresh(widget_id)


# ---- stepper: [ - ]  value  [ + ] ----------------------------------------------------------------------------
def _draw_stepper(w):
    x = w["x"]; y = w["y"]; ww = w["w"]; h = w["h"]
    bg = _bg(w)
    display.fill_rectangle(x, y, ww, h, bg)
    col = colour(w.get("color", "green"))
    white = colour("white")
    display.fill_rectangle(x, y, h, h, col)
    display.fill_rectangle(x + ww - h, y, h, h, col)
    m = h // 4
    cy = y + h // 2
    display.fill_rectangle(x + m, cy - 1, h - 2 * m, 3, white)                      # the minus
    display.fill_rectangle(x + ww - h + m, cy - 1, h - 2 * m, 3, white)             # the plus ...
    display.fill_rectangle(x + ww - h // 2 - 1, y + m, 3, h - 2 * m, white)
    font = widget_font(w); sc = fsize(w)
    th = font.h if font else 8 * sc
    draw_line(display, x + h, ww - 2 * h, y + (h - th) // 2, _num_text(w.get("value", 0)), white, bg,
              w.get("bold", False), w.get("italic", False), "center", sc, font)


def _stepper_tap(w, px):
    h = w["h"]
    if px < w["x"] + h:
        d = -1
    elif px >= w["x"] + w["w"] - h:
        d = 1
    else:
        return
    old = w.get("value", 0)
    new = max(w.get("min", 0), min(w.get("max", 100), old + d * w.get("step", 1)))
    if new != old:
        w["value"] = new
        _draw_stepper(w)
        if "changed" in w.get("events", []):
            _queue.append((w["id"], "changed", new))


def _draw_widget(w):

    if not w.get("visible", True):
        return

    kind = w.get("widget")

    if kind == "switch":
        _draw_switch(w)
    elif kind == "checkbox":
        _draw_checkbox(w)
    elif kind == "slider":
        _draw_slider(w)
    elif kind == "progressbar":
        _draw_bar(w, False)
    elif kind == "gauge":
        _draw_gauge(w)
    elif kind == "waveform":
        _draw_chart(w)
    elif kind == "barchart":
        _draw_barchart(w)
    elif kind == "stepper":
        _draw_stepper(w)
    elif kind == "image":
        _draw_image(w)
    elif kind == "line":
        _draw_line_widget(w)
    elif kind == "choice":
        _draw_choice(w)
    elif kind == "tree":
        _draw_tree(w)
    elif kind == "keyboard":
        pass    # only appears while open (not drawn with the screen)
    else:
        _draw_text_widget(w)


def _bar_zone(py, y0, h):
    """Where was a scroll bar (from y0, h pixels high) tapped? Returns (step, fraction):
    the outer fifth at the top / bottom -> (-1, None) / (+1, None): move one row;
    the middle -> (0, f) with f from 0.0 (start of the list) to 1.0 (end): jump there."""
    f = (py - y0) / h
    if f < 0.2:
        return -1, None
    if f > 0.8:
        return 1, None
    return 0, (f - 0.2) / 0.6


def _repaint_area(x0, y0, x1, y1, skip=None):
    """Paints the rectangle x0..x1 / y0..y1 (x1, y1 not included) with the screen background, then
    redraws every visible widget that touches it (except `skip`), in order."""
    display.fill_rectangle(x0, y0, x1 - x0, y1 - y0, colour(screen.get("background", "black")))
    for o in _zorder:
        if o is skip or not o.get("visible", True):
            continue
        ox0 = min(o["x"], o["x"] + o["w"])
        oy0 = min(o["y"], o["y"] + o["h"])
        ox1 = max(o["x"], o["x"] + o["w"]) + 1
        oy1 = max(o["y"], o["y"] + o["h"]) + 1
        if ox0 < x1 and ox1 > x0 and oy0 < y1 and oy1 > y0:
            _draw_widget(o)


def redraw_widget(widget_id):
    """Redraws one widget using its CURRENT properties in `widgets[widget_id]`.
    Call this after mutating a property (e.g. widgets['button1']['background'])
    for the change to actually appear on screen."""

    # A widget on a screen that isn't showing just keeps the new value;
    # it is drawn when that screen is next shown.
    if _wscreen[widget_id] != screen["id"]:
        return

    w = widgets[widget_id]

    if w.get("visible", True):
        _draw_widget(w)
        return

    # Hidden: erase it (screen background), then redraw what was behind/around it.
    _repaint_area(min(w["x"], w["x"] + w["w"]), min(w["y"], w["y"] + w["h"]),
                  max(w["x"], w["x"] + w["w"]) + 1, max(w["y"], w["y"] + w["h"]) + 1, w)


_t0 = time.ticks_ms()

for w in _zorder:
    _draw_widget(w)

print("Runtime: widgets drawn in", time.ticks_diff(time.ticks_ms(), _t0), "ms")


# ============================================================
# WIDGET OBJECTS -- button1.Background = "Red" style access
# ============================================================
#
# Any capitalised attribute maps to the matching lowercase JSON key
# (Background -> "background", Text -> "text", ...). Setting one updates
# the widget and redraws it immediately -- no separate redraw call.

class Widget:

    def __init__(self, widget_id):
        object.__setattr__(self, "_id", widget_id)

    def __getattr__(self, name):
        key = name.lower()
        data = widgets[self._id]
        if key in data:
            return data[key]
        raise AttributeError(name)

    def show(self):
        """keyboard widgets only: opens the on-screen keyboard (blocks until
        Enter or Cancel). Returns the typed text, or None if cancelled."""
        return _keyboard_show(self._id)

    def add(self, value):
        """waveform only: appends a value (the oldest drops out when it is full)."""
        _chart_add(self._id, value)

    def set(self, index, value):
        """barchart only: sets bar number `index` (0 = the first)."""
        _chart_set(self._id, index, value)

    def clear(self):
        """waveform / barchart only: empties the chart (a barchart: all bars to min)."""
        _chart_clear(self._id)

    def __setattr__(self, name, value):
        widgets[self._id][name.lower()] = value
        w = widgets[self._id]
        if name.lower() == "values":
            _chart_data.pop(self._id, None)         # a new list of bar values
        if name.lower() == "value" and w.get("widget") == "gauge" and w.get("visible", True) \
                and _wscreen[self._id] == screen["id"] and self._id in _gauge_last:
            _gauge_value_changed(w)             # only the needle and the number are redrawn
            return
        if name.lower() == "selected" and widgets[self._id].get("widget") == "tree":
            _tree_reveal(widgets[self._id])
        redraw_widget(self._id)


widget_objs = {}

for _wid in widgets:
    _w = Widget(_wid)
    widget_objs[_wid] = _w
    globals()[_wid] = _w


def Screen(screen_id):
    """Switches to another screen: clears the display and draws that screen's
    widgets (with their current properties). Widgets on other screens keep
    whatever you last set."""

    global screen, _zorder

    if screen_id not in screens:
        raise ValueError("no screen: " + str(screen_id))

    # Drawing a screen allocates a short burst of small buffers (one per gauge/chart
    # widget, freed again right after). gc.collect() here compacts the heap right
    # before that burst, so a block that would otherwise be refused for being merely
    # fragmented (plenty of free memory overall, just not in one contiguous piece --
    # confirmed by the stress test, Oct 2026: two MemoryErrors in 18 hours, free
    # memory steady throughout) finds the room it needs.
    gc.collect()

    screen = screens[screen_id]
    _zorder = list(screen["widgets"])

    display.clear(colour(screen.get("background", "black")))

    for w in _zorder:
        _draw_widget(w)


# ============================================================
# TOUCH (XPT2046) -- polled
# ============================================================

# These react to touch whenever they are enabled; "events" only decides whether the script is told.
_INTERACTIVE = ("switch", "checkbox", "slider", "choice", "tree", "stepper")


def find_widget(x, y):

    # Later widget = on top. Invisible/disabled widgets don't receive touch.

    for w in reversed(_zorder):

        if not w.get("visible", True):
            continue

        if not w.get("enabled", True):
            continue

        if not w.get("events") and w.get("widget") not in _INTERACTIVE:
            continue

        if w.get("widget") == "keyboard":
            continue            # not drawn on the screen, so it must never catch a tap

        if (
            x >= w["x"] and x < w["x"] + w["w"]
            and y >= w["y"] and y < w["y"] + w["h"]
        ):
            return w

    return None


touch = board.make_touch(WIDTH, HEIGHT)

_queue = []
_active = False


# ============================================================
# BACKLIGHT, SCREEN SAVER and the BOOT button
# ============================================================
#
# backlight(percent)         brightness 0..100 now; 0 = the screen is BLANK (the next touch, or the BOOT button, brings
#                            it back to the brightness it had). backlight() with no argument returns the setting.
# screensaver(seconds, dim)  after `seconds` without a touch the backlight drops to `dim` percent (default 0 = blank);
#                            the next touch only wakes the screen (it is not a click). screensaver(0) = off.
# power_button(True)         the BOOT button on the back also blanks the screen when it is on (like a phone's power
#                            button); with the default (False) it only WAKES the screen.
# The board profile provides set_backlight(percent) (PWM on the CYD) and BUTTON_PIN (the BOOT button, GPIO 0).

_bl = 100                    # the brightness the script asked for
_wake_to = 100               # what a touch restores
_asleep = False              # blank, or dimmed by the screen saver
_saver_s = 0                 # idle seconds before dimming (0 = no screen saver)
_saver_dim = 0
_last_touch = time.ticks_ms()
_power_blanks = False
_button = None
_button_down = False

_bp = getattr(board, "BUTTON_PIN", None)
if _bp is not None:
    from machine import Pin
    _button = Pin(_bp, Pin.IN, Pin.PULL_UP)       # pressed = 0


def _set_backlight(percent):
    f = getattr(board, "set_backlight", None)
    if f is not None:
        f(percent)


def backlight(percent=None):
    """Sets the backlight brightness (0 = blank .. 100 = full); without an argument returns the current setting."""
    global _bl, _wake_to, _asleep, _last_touch
    if percent is None:
        return _bl
    percent = max(0, min(100, int(percent)))
    if percent == 0:
        if _bl > 0:
            _wake_to = _bl
        _asleep = True
    else:
        _wake_to = percent
        _asleep = False
    _bl = percent
    _last_touch = time.ticks_ms()
    _set_backlight(percent)


def screensaver(seconds, dim=0):
    """After `seconds` without a touch the backlight is set to `dim` percent (0 = blank). The next touch wakes the
    screen and is NOT delivered as a click. screensaver(0) switches the screen saver off."""
    global _saver_s, _saver_dim, _last_touch
    _saver_s = seconds
    _saver_dim = dim
    _last_touch = time.ticks_ms()
    if _asleep and not seconds and _bl > 0:
        _wake()


def power_button(on=True):
    """True: the BOOT button on the back blanks the screen when it is on, and wakes it when it is off.
    False (the default): it only wakes the screen."""
    global _power_blanks
    _power_blanks = bool(on)


def _wake():
    global _bl, _asleep, _last_touch
    _asleep = False
    _bl = _wake_to
    _last_touch = time.ticks_ms()
    _set_backlight(_bl)


def _saver_check():
    global _asleep
    if _saver_s and not _asleep and time.ticks_diff(time.ticks_ms(), _last_touch) > _saver_s * 1000:
        _asleep = True
        _set_backlight(_saver_dim)


def _check_button():
    # The BOOT button: wakes the screen; with power_button(True) it also blanks it. Returns True if it was just pressed.
    global _button_down
    if _button is None:
        return False
    if _button.value() == 0:
        if not _button_down:
            _button_down = True
            if _asleep:
                _wake()
            elif _power_blanks:
                backlight(0)
            return True
    else:
        _button_down = False
    return False


def _read_point(want, max_attempts):

    # Averages up to `want` touch readings; None if the screen isn't being
    # touched (or was released before any good reading).

    total_x = 0
    total_y = 0
    count = 0
    attempts = 0

    while count < want and attempts < max_attempts:

        pt = touch.read()
        attempts += 1

        if pt is not None:
            total_x += pt[0]
            total_y += pt[1]
            count += 1

        time.sleep_ms(10)

    if count == 0:
        return None

    global _last_touch
    _last_touch = time.ticks_ms()                    # a touch: the screen saver starts counting again

    return total_x // count, total_y // count


def _slider_value(w, x, y):

    lo = w.get("min", 0)
    hi = w.get("max", 100)
    step = w.get("step", 1) or 1

    r = _slider_r(w)
    if w["w"] >= w["h"]:
        f = (x - w["x"] - r) / (w["w"] - 2 * r)
    else:
        f = 1 - (y - w["y"] - r) / (w["h"] - 2 * r)

    f = max(0.0, min(1.0, f))
    v = lo + int(round((f * (hi - lo)) / step)) * step

    return max(lo, min(hi, v))


def _drag_slider(w, p):

    # Follows the finger while it stays down, redrawing live. One "changed"
    # event is queued on release (not one per step), carrying the final value.
    # Optional: <id>_changing(value) in the USER script is called on every step.

    start = w.get("value", w.get("min", 0))
    live = _find_handler(w["id"] + "_changing", None)     # optional live callback

    while p is not None:

        v = _slider_value(w, p[0], p[1])

        if v != w.get("value"):
            w["value"] = v
            _draw_widget(w)
            if live is not None:
                live(v)

        p = _read_point(3, 6)

    if w.get("value") != start and "changed" in w.get("events", []):
        _queue.append((w["id"], "changed", w["value"]))


def _choice_hit(w, x, y):
    # Which item (0, 1, 2 ...) of a radio group was tapped? None if the tap is on the frame.
    x0, y0, sw, sh, horizontal = _radio_slot(w)
    n = len(w.get("items", []))
    i = (x - x0) // sw if horizontal else (y - y0) // sh
    if i < 0 or i >= n:
        return None
    return i


def _sample_and_enqueue():

    # Called only once we already know the pin is down (cheap check in
    # _check_touch). Capped so a very brief tap can't spin forever.

    p = _read_point(10, 40)

    if p is None:
        return

    w = find_widget(p[0], p[1])

    if w is None:
        return

    events = w.get("events", [])
    kind = w.get("widget")

    if kind == "slider":
        _drag_slider(w, p)

    elif kind in ("switch", "checkbox"):
        w["value"] = not w.get("value", False)
        _draw_widget(w)
        if "changed" in events:
            _queue.append((w["id"], "changed", w["value"]))

    elif kind == "tree":
        _tree_tap(w, p[0], p[1])

    elif kind == "stepper":
        _stepper_tap(w, p[0])

    elif kind == "choice" and w.get("style", "radio") == "dropdown":
        _dropdown_open(w)

    elif kind == "choice":
        i = _choice_hit(w, p[0], p[1])
        old = w.get("selected", -1)
        if i is not None and i != old:
            w["selected"] = i
            _draw_radio(w, (old, i))         # only the two items that changed
            if "changed" in events:
                _queue.append((w["id"], "changed", i))

    elif "longpress" in events:
        # held for LONG_PRESS_MS -> "longpress"; released earlier -> "click" (if that is listed too).
        # A release counts only if the touch stays away for 80 ms: a resistive panel flickers under a steady finger.
        t0 = time.ticks_ms()
        up = None
        held = True
        while time.ticks_diff(time.ticks_ms(), t0) < LONG_PRESS_MS:
            if touch.pressed():
                up = None
            elif up is None:
                up = time.ticks_ms()
            elif time.ticks_diff(time.ticks_ms(), up) > 80:
                held = False
                break
            time.sleep_ms(20)
        if held:
            _queue.append((w["id"], "longpress", None))
        elif "click" in events:
            _queue.append((w["id"], "click", None))

    elif "click" in events:
        _queue.append((w["id"], "click", None))


# ============================================================
# KEYBOARD -- modal: clear screen, memo + keyboard, restore on exit
# ============================================================
#
# layout "numeric": 4x4 keypad under a 2-line memo (one '.', '-' only first).
# keyboard1.show() takes over the screen: the keyboard (fixed size, its
# x/y/w/h are ignored) fills the bottom, a temporary memo the top 72 px, and
# each key tap updates the memo. Enter copies the text to the "target"
# widget (if one is set), cancel leaves it untouched; either way the
# screen is then redrawn from the widgets (so the target shows the new text).
# secret: the memo shows * instead of the characters. max_length: 0 = no
# limit. Enter also queues event "enter" (handler keyboard1_enter(text)).
# input_event: calls keyboard1_input(text) in the USER script on
# every key. hide_on_enter true (default): Enter closes it. False: Enter sends
# the text (target + keyboard1_enter(text) called at once), clears the memo and
# the keyboard stays open until Esc; show() then returns the last text sent.

_KB_ROWS = (
    (("1", 1), ("2", 1), ("3", 1), ("4", 1), ("5", 1), ("6", 1), ("7", 1), ("8", 1), ("9", 1), ("0", 1)),
    (("Q", 1), ("W", 1), ("E", 1), ("R", 1), ("T", 1), ("Y", 1), ("U", 1), ("I", 1), ("O", 1), ("P", 1)),
    (("A", 1), ("S", 1), ("D", 1), ("F", 1), ("G", 1), ("H", 1), ("J", 1), ("K", 1), ("L", 1)),
    (("Z", 1), ("X", 1), ("C", 1), ("V", 1), ("B", 1), ("N", 1), ("M", 1), ("Bksp", 2)),
    (("Space", 5), ("Cancel", 2), ("Enter", 3)),
)

# Bottom row when the keyboard's "linefeed" setting is on (adds an LF key).
_KB_LAST_LF = (("Space", 3), ("LF", 2), ("Cancel", 2), ("Enter", 3))


KB_MEMO_H = 72      # memo band at the top (5 lines of text)


def _kb_geom():
    # Fixed: the keyboard fills the screen below the memo band.
    return 0, KB_MEMO_H, WIDTH, HEIGHT - KB_MEMO_H


def _big_text(label, x, y, w, h, fg, bg):
    # Draws label at 2x size, centred in the (x, y, w, h) box.
    tw = len(label) * 16
    bs = ((bg & 255) << 8) | ((bg >> 8) & 255)
    fs = ((fg & 255) << 8) | ((fg >> 8) & 255)
    dst = bytearray(tw * 16 * 2)
    df = framebuf.FrameBuffer(dst, tw, 16, framebuf.RGB565)
    df.fill(bs)
    src = bytearray(128)
    sf = framebuf.FrameBuffer(src, 8, 8, framebuf.RGB565)
    for i in range(len(label)):
        sf.fill(bs)
        sf.text(label[i], 0, 0, fs)
        for sy in range(8):
            for sx in range(8):
                if sf.pixel(sx, sy) != bs:
                    df.fill_rect(i * 16 + sx * 2, sy * 2, 2, 2, fs)
    x0 = x + (w - tw) // 2
    y0 = y + (h - 16) // 2
    display.block(x0, y0, x0 + tw - 1, y0 + 15, dst)


def _kb_numeric_keys(geom):
    # 4 columns x 4 rows; Bksp / Esc on the right, a tall Enter beside 7-8-9 and - 0 .
    gx, gy, gw, gh = geom
    u = gw // 4
    rh = gh // 4
    cells = (("1", 0, 0, 1, 1), ("2", 1, 0, 1, 1), ("3", 2, 0, 1, 1), ("Bksp", 3, 0, 1, 1),
             ("4", 0, 1, 1, 1), ("5", 1, 1, 1, 1), ("6", 2, 1, 1, 1), ("Cancel", 3, 1, 1, 1),
             ("7", 0, 2, 1, 1), ("8", 1, 2, 1, 1), ("9", 2, 2, 1, 1), ("Enter", 3, 2, 1, 2),
             ("-", 0, 3, 1, 1), ("0", 1, 3, 1, 1), (".", 2, 3, 1, 1))
    return [(lab, gx + c * u + 1, gy + r * rh + 1, cs * u - 2, rs * rh - 2)
            for lab, c, r, cs, rs in cells]


def _kb_keys(geom, linefeed=False):

    gx, gy, gw, gh = geom
    unit = gw // 10
    rows = _KB_ROWS[:-1] + (_KB_LAST_LF,) if linefeed else _KB_ROWS
    rh = gh // len(rows)
    keys = []

    for r in range(len(rows)):
        col = 0
        for label, span in rows[r]:
            keys.append((label, gx + col * unit + 1, gy + r * rh + 1,
                         span * unit - 2, rh - 2))
            col += span

    return keys


def _kb_key(kb, k, pressed):

    label, x, y, w, h = k
    face = colour("gray") if pressed else colour("#d8d8d8")
    bc = colour(kb.get("border", {}).get("color", "black"))

    display.fill_rectangle(x, y, w, h, bc)
    display.fill_rectangle(x + 1, y + 1, w - 2, h - 2, face)
    fg = colour(kb.get("color", "black"))

    if len(label) * 16 > w - 4:
        label = {"Bksp": "<-", "Cancel": "Esc", "Enter": "OK"}.get(label, label)

    if len(label) * 16 <= w - 4 and h >= 18:
        _big_text(label, x, y, w, h, fg, face)
    else:
        draw_line(display, x, w, y + (h - 8) // 2, label, fg, face, False, False, "center")


_MEMO_X = 8
_MEMO_BAR_W = 16        # scrollbar strip on the memo's right edge
_m_prev = []            # what each memo row currently shows (None = unknown)
_m_top = 0              # first visible line
_m_bar = None           # scrollbar state last drawn


def _kb_memo(kb, text, band, delta=None, full=False, frac=None):

    # Draws only what changed since the last call. delta=None -> follow the
    # end of the text (used after typing); +1/-1 -> scroll that many lines.

    global _m_prev, _m_top, _m_bar

    x = _MEMO_X
    y = band[0] + 6
    w = WIDTH - 2 * _MEMO_X
    h = band[1] - band[0] - 12
    cols = (w - 8 - _MEMO_BAR_W) // 8
    rows = max(1, (h - 8) // 10)
    white = colour("white")
    black = colour("black")

    if kb.get("secret", False):
        text = "".join(c if c == "\n" else "*" for c in text)

    lines = []
    for para in (text + "_").split("\n"):
        lines += [para[k:k + cols] for k in range(0, len(para), cols)] or [""]

    n = len(lines)
    maxtop = max(0, n - rows)

    if frac is not None:
        _m_top = max(0, min(maxtop, int(frac * maxtop + 0.5)))      # jump to a place in the text
    elif delta is None:
        _m_top = maxtop
    else:
        _m_top = max(0, min(maxtop, _m_top + delta))

    if full:
        display.fill_rectangle(x, y, w, h, white)
        display.fill_rectangle(x + 1, y + 1, w - 2, h - 2, black)
        _m_prev = [None] * rows
        _m_bar = None

    visible = lines[_m_top:_m_top + rows]
    visible += [""] * (rows - len(visible))

    for r in range(rows):

        old = _m_prev[r]
        new = visible[r]

        if old == new:
            continue

        # Only the part of the row from the first differing character on.
        c = 0
        if old is not None:
            while c < len(old) and c < len(new) and old[c] == new[c]:
                c += 1
        end = len(new) if old is None else max(len(old), len(new))
        ty = y + 4 + r * 10

        display.fill_rectangle(x + 4 + c * 8, ty, (end - c) * 8, 10, black)
        if new[c:]:
            draw_line(display, x + 4 + c * 8, 8 * len(new) - c * 8, ty, new[c:],
                      white, black, False, False, "left")

        _m_prev[r] = new

    bar = (_m_top, n) if n > rows else None

    if bar != _m_bar:

        bx = x + w - _MEMO_BAR_W
        display.fill_rectangle(bx, y + 1, _MEMO_BAR_W - 1, h - 2, black)

        if bar is not None:
            th = h - 6
            display.fill_rectangle(bx + 2, y + 3, _MEMO_BAR_W - 5, th, colour("#404040"))
            kh = max(8, th * rows // n)
            ky = y + 3 + (th - kh) * _m_top // maxtop
            display.fill_rectangle(bx + 2, ky, _MEMO_BAR_W - 5, kh, colour("#c0c0c0"))

        _m_bar = bar


def _keyboard_show(kb_id):

    kb = widgets[kb_id]
    numeric = kb.get("layout", "full") == "numeric"
    memo_h = 48 if numeric else KB_MEMO_H
    geom = (0, memo_h, WIDTH, HEIGHT - memo_h)
    keys = _kb_numeric_keys(geom) if numeric else _kb_keys(geom, kb.get("linefeed", False))
    target = widgets.get(kb.get("target", ""))
    limit = kb.get("max_length", 0)

    band = (0, memo_h)

    text = ""       # always starts empty; the USER script keeps any earlier value (e.g. memo1.text)

    display.clear(colour(screen.get("background", "black")))
    display.fill_rectangle(geom[0], geom[1], geom[2], geom[3], colour(kb.get("background", "gray")))
    for k in keys:
        _kb_key(kb, k, False)
    _kb_memo(kb, text, band, None, True)

    # The tap that opened the keyboard may still be down: wait for release.
    while touch.pressed():
        time.sleep_ms(10)

    result = None
    by_enter = False        # closed with Enter (hide_on_enter) -> commit below

    while True:

        if not touch.pressed():
            time.sleep_ms(20)
            continue

        p = _read_point(5, 20)

        # Tap on the memo's scrollbar strip: ends = one line, middle = jump.
        if p is not None and p[1] < band[1] and p[0] >= WIDTH - _MEMO_X - _MEMO_BAR_W:
            step, frac = _bar_zone(p[1], band[0] + 6, band[1] - band[0] - 12)
            _kb_memo(kb, text, band, step, False, frac)
            while touch.pressed():
                time.sleep_ms(10)
            continue

        hit = None
        if p is not None:
            for k in keys:
                if p[0] >= k[1] and p[0] < k[1] + k[3] and p[1] >= k[2] and p[1] < k[2] + k[4]:
                    hit = k
                    break

        if hit is not None:

            label = hit[0]
            _kb_key(kb, hit, True)

            if label == "Enter" and numeric and text == "-":
                pass                        # a lone minus is not a number: ignore OK
            elif label == "Enter":
                if kb.get("hide_on_enter", True):
                    result = text
                    by_enter = True
                    break
                # Stay open: send the text now, clear the memo for the next entry.
                result = text
                if target is not None:
                    target["text"] = text
                h = _find_handler(kb_id + "_enter", None)
                if h is not None:
                    h(text)
                text = ""
            elif label == "Cancel":
                break       # keeps `result` (None, or the last text sent)
            elif label == "Bksp":
                text = text[:-1]
            elif label == "LF":
                if not limit or len(text) < limit:
                    text += "\n"
            elif label == "Space":
                if not limit or len(text) < limit:
                    text += " "
            elif numeric and label == "." and "." in text:
                pass                        # only one decimal point
            elif numeric and label == "-" and text != "":
                pass                        # minus only as the first character
            elif not limit or len(text) < limit:
                if numeric and label == "." and text in ("", "-"):
                    text += "0"             # ".5" -> "0.5"
                text += label

            _kb_memo(kb, text, band)

            if kb.get("input_event", False) and label != "Enter":
                h = _find_handler(kb_id + "_input", None)
                if h is not None:
                    h(text)

        while touch.pressed():
            time.sleep_ms(10)

        if hit is not None:
            _kb_key(kb, hit, False)

    while touch.pressed():
        time.sleep_ms(10)

    if by_enter:
        if target is not None:
            target["text"] = result
        if "enter" in kb.get("events", []):
            _queue.append((kb_id, "enter", result))

    display.clear(colour(screen.get("background", "black")))
    for w in _zorder:
        _draw_widget(w)

    return result


def _check_touch():

    # One cheap poll of the touch pin. Latches on _active so a sustained
    # press is only processed once (same "wait for release" behaviour
    # the original polling loop had), without blocking here to wait for
    # the release -- that just happens naturally across later calls.

    global _active

    down = touch.pressed()

    if down and not _active:
        _active = True
        if _asleep:
            _wake()                                  # the touch that wakes the screen is not a click
        else:
            # Unlike handlers (run()) and periodic tasks (_run_tasks()), this was the one place
            # a bug could escape uncaught: all the way out of wait_event()/run(), out of the
            # USER script's own run() call, out through main.py's import -- which main.py then
            # treats as a startup failure and shows the unrecoverable error screen for, even
            # though nothing failed at startup. Guarded the same way as the other two now.
            try:
                _sample_and_enqueue()
            except Exception as e:
                _error_screen(e, "handling a touch")
                _restore_screen()
    elif not down:
        _active = False

    _check_button()
    _saver_check()
    if _chart_dirty:
        _chart_flush()


print("Runtime: touch polling ready")


# ============================================================
# PUBLIC EVENT API
# ============================================================

# ============================================================
# PERIODIC TASKS -- every(ms, function) / stop(function)
# ============================================================
#
# every(1000, tick) calls tick() once a second, from inside the event loop
# (run() / wait_event() / get_event()), so tasks and touch handlers never run
# at the same time. A task that takes long just makes the next call late. An
# error inside a task is printed and the task keeps its schedule. Tasks do not
# run while the keyboard is open (it takes over the loop).

_tasks = []          # [period_ms, due_ticks, function, consecutive_failures]
_TASK_FAIL_LIMIT = 3  # stop a task only after this many FAILURES IN A ROW, not on one bad tick
                       # (a transient heap-fragmentation MemoryError during a redraw -- see Screen()'s
                       # gc.collect() -- would otherwise permanently kill e.g. a clock's every(1000, ...)
                       # task after a single unlucky tick, leaving the display frozen even once the
                       # error screen is dismissed and nothing is actually still wrong)


def every(ms, function):
    """Calls function() every `ms` milliseconds (first call after `ms`).
    Registering the same function again just changes its period."""
    due = time.ticks_add(time.ticks_ms(), ms)
    for t in _tasks:
        if t[2] is function:
            t[0] = ms
            t[1] = due
            t[3] = 0
            return function
    _tasks.append([ms, due, function, 0])
    return function


def stop(function):
    """Stops a task started with every()."""
    for t in _tasks:
        if t[2] is function:
            _tasks.remove(t)
            return


def _run_tasks():
    if not _tasks:
        return
    now = time.ticks_ms()
    for t in list(_tasks):
        if time.ticks_diff(now, t[1]) >= 0:
            t[1] = time.ticks_add(now, t[0])
            try:
                t[2]()
                t[3] = 0
            except Exception as e:
                t[3] += 1
                name = getattr(t[2], "__name__", "?")
                if t[3] >= _TASK_FAIL_LIMIT:
                    stop(t[2])                                   # failed too many times in a row: likely a real bug, not a blip
                    _error_screen(e, "in periodic task %s (stopped)" % name)
                else:
                    _error_screen(e, "in periodic task %s (retrying)" % name)
                _restore_screen()


def _ms_to_next_task(limit):
    # How long we may sleep: `limit`, or less if a task is due sooner.
    if not _tasks:
        return limit
    now = time.ticks_ms()
    soonest = limit
    for t in _tasks:
        d = time.ticks_diff(t[1], now)
        if d < soonest:
            soonest = d
    return max(soonest, 5)


def get_event():
    """Runs any due periodic tasks, checks the touch pin once, then returns the
    oldest queued (widget_id, event, value) tuple, or None if nothing's queued."""

    _run_tasks()
    _check_touch()

    if _queue:
        return _queue.pop(0)

    return None


def wait_event(timeout_ms=None, poll_ms=150):
    """Blocks, light-sleeping poll_ms between checks, until an event is
    queued or timeout_ms elapses (returns None on timeout). No timeout =
    wait forever. poll_ms trades responsiveness for power: longer =
    lower average current, shorter = snappier clicks."""

    elapsed = 0

    while True:

        ev = get_event()

        if ev is not None:
            return ev

        if timeout_ms is not None and elapsed >= timeout_ms:
            return None

        nap = _ms_to_next_task(poll_ms)

        if LOW_POWER and time.ticks_diff(time.ticks_ms(), _boot_ms) > LOW_POWER_GRACE_MS:
            lightsleep(nap)
        else:
            time.sleep_ms(nap)
        elapsed += nap


# ============================================================
# run() -- the event loop, so USER scripts don't need one
# ============================================================
#
# Handlers are plain functions in the USER script named
# <widget_id>_<event>, e.g. button1_click(). A value-bearing event
# (e.g. a slider) passes its value as the one argument.

def _find_handler(name, module):

    import sys

    if module is not None:
        h = getattr(module, name, None)
        if h is not None:
            return h

    try:
        import __main__ as main_script          # a script started from Thonny is NOT listed in sys.modules, but it can be imported by this name
    except ImportError:
        main_script = None

    for m in [main_script, sys.modules.get("__main__")] + list(sys.modules.values()):
        h = getattr(m, name, None)
        if h is not None and callable(h):
            return h

    return None


_poll = 150


def set_longpress_ms(ms):
    """How long (milliseconds) a touch must last to count as a long press. Default 700."""
    global LONG_PRESS_MS
    LONG_PRESS_MS = ms


def set_poll_ms(ms):
    """Changes how often the touch screen is checked (see run(poll_ms=...)) while running."""
    global _poll
    _poll = ms


# ============================================================
# ERROR SCREEN -- a mistake in your script is shown on the display
# ============================================================
#
# An error inside a handler or a periodic task is printed on the serial port AND shown on the screen
# (what failed, where, which line); a tap continues. An error while your script starts is shown by
# fatal() (main.py calls it) and stays until the board is reset. Ctrl-C still works.

def _wrap(text, cols):
    # Breaks lines at SPACES only. A single word longer than a whole line is split (nothing else can be done).
    lines = []
    for para in str(text).split("\n"):
        cur = ""
        for word in para.split(" "):
            while len(word) > cols:
                if cur:
                    lines.append(cur)
                    cur = ""
                lines.append(word[:cols])
                word = word[cols:]
            if not cur:
                cur = word
            elif len(cur) + 1 + len(word) <= cols:
                cur += " " + word
            else:
                lines.append(cur)
                cur = word
        lines.append(cur)
    return lines


def _parse_frames(trace):
    # MicroPython traceback text -> [(file, line, function), ...]; your own files first, the Runtime's only if there are none
    mine = []
    other = []
    for line in trace.split("\n"):
        line = line.strip()
        if not line.startswith("File "):
            continue
        try:
            fname = line.split('"')[1]
            num = line.split("line ")[1].split(",")[0].strip()
            func = line.split(" in ")[1].strip() if " in " in line else ""
            item = (fname, num, func)
            if fname.startswith("Runtime") or fname.startswith("main"):
                other.append(item)
            else:
                mine.append(item)
        except Exception:
            pass
    return mine if mine else other


def _draw_error(where, exc, trace, footer):
    bg = colour("#300000")
    display.clear(bg)
    draw_line(display, 4, WIDTH - 8, 6, "SCRIPT ERROR", colour("#ff7070"), bg, True, False, "center", 2)
    text = str(exc)
    tail = "' isn't defined"
    if isinstance(exc, NameError) and text.startswith("name '") and text.endswith(tail):
        text = text[6:-len(tail)]                               # just the name: tidier than MicroPython's wording
    msg = "%s: %s" % (type(exc).__name__, text)
    frames = _parse_frames(trace)[-3:]
    places = []
    if frames and not frames[-1][2]:
        # a syntax error has a file and a line, but no function: put the line number at the end of the message
        msg += " (line %s)" % frames[-1][1]
        places.append("in file " + frames[-1][0])
    else:
        for fname, num, func in frames:
            places.append("File %s, line %s%s" % (fname, num, ", in " + func if func else ""))
    try:
        font = widget_font({"font_type": "DejaVu Sans Mono", "font_size": 12})    # 12 px, if its file is on the board
    except Exception:
        font = None
    if font:
        cw = font.adv[font.index("M")]
        step = font.h + 3
    else:
        cw = 8
        step = 10
    cols = max(8, (WIDTH - 8) // cw)
    lines = [(t, "#ffffff") for t in _wrap(where, cols)] + [("", "#ffffff")]
    lines += [(t, "#ffffff") for t in _wrap(msg, cols)]
    if places:
        lines.append(("", "#ffffff"))
        for f in places:
            lines += [(t, "#ffffff") for t in _wrap(f, cols)]
    y = 42                                   # a little space under the heading
    for text, col in lines:
        if y + step > HEIGHT - 32:
            break
        if text:
            draw_line(display, 4, WIDTH - 8, y, text, colour(col), bg, False, False, "left", 1, font)
        y += step
    draw_line(display, 4, WIDTH - 8, HEIGHT - 26, footer, colour("#a0a0a0"), bg, False, False, "left")      # a blank line below it


def _restore_screen():
    display.clear(colour(screen.get("background", "black")))
    for w in _zorder:
        _draw_widget(w)


def _error_screen(exc, where, wait=True):
    trace = ""
    try:
        import sys
        import io
        buf = io.StringIO()
        sys.print_exception(exc, buf)
        trace = buf.getvalue()
        print(trace)                                  # also on the serial port
    except Exception:
        pass
    try:
        _draw_error(where, exc, trace, "tap to continue" if wait else "RUN CHECK_SCRIPT.PY ON THE PC")
    except Exception as e2:
        print("error screen failed:", e2)
        return
    if wait:
        while touch.pressed():
            time.sleep_ms(10)
        while not touch.pressed():
            time.sleep_ms(50)
        while touch.pressed():
            time.sleep_ms(10)
    else:
        while True:
            time.sleep_ms(300)


def fatal(exc):
    """For main.py: show an error that stopped your script from starting (stays until the board is reset)."""
    _error_screen(exc, "while your script was starting", False)


# ============================================================
# message(text, "Yes", "No") -- a pop-up the user must answer
# ============================================================

def message(text, *buttons):
    """Shows a pop-up box with the text and one button per label (default "OK"), waits until a button is
    tapped, removes the box and returns the label of the tapped button. Like the keyboard it takes over
    while open (periodic tasks pause)."""

    if not buttons:
        buttons = ("OK",)

    fg = colour("white")
    bg = colour("#1c2a30")
    frame = colour("#0ea5c5")
    btn = colour("#0b6f86")

    box_w = WIDTH - 40
    sc = 2
    lines = _wrap(text, (box_w - 16) // (8 * sc))
    if len(lines) > 4:
        sc = 1
        lines = _wrap(text, (box_w - 16) // 8)
    lh = 8 * sc + 4
    btn_h = 40
    box_h = 12 + len(lines) * lh + 14 + btn_h + 12
    bx = 20
    by = max(0, (HEIGHT - box_h) // 2)

    display.fill_rectangle(bx, by, box_w, box_h, frame)
    display.fill_rectangle(bx + 2, by + 2, box_w - 4, box_h - 4, bg)
    y = by + 12
    for t in lines:
        draw_line(display, bx + 8, box_w - 16, y, t, fg, bg, False, False, "center", sc)
        y += lh

    n = len(buttons)
    gap = 8
    each = (box_w - 16 - gap * (n - 1)) // n
    btn_y = by + box_h - 12 - btn_h
    rects = []
    for i in range(n):
        rx = bx + 8 + i * (each + gap)
        display.fill_rectangle(rx, btn_y, each, btn_h, btn)
        s2 = 2 if len(buttons[i]) * 16 <= each - 6 else 1
        draw_line(display, rx, each, btn_y + (btn_h - 8 * s2) // 2, buttons[i], fg, btn, False, False, "center", s2)
        rects.append((rx, btn_y, each, btn_h))

    while touch.pressed():                          # the tap that opened it may still be down
        time.sleep_ms(10)

    chosen = None
    while chosen is None:
        if not touch.pressed():
            time.sleep_ms(20)
            continue
        p = _read_point(5, 20)
        while touch.pressed():
            time.sleep_ms(10)
        if p is None:
            continue
        for i in range(n):
            rx, ry, rw, rh = rects[i]
            if rx <= p[0] < rx + rw and ry <= p[1] < ry + rh:
                chosen = buttons[i]
                break

    _repaint_area(bx, by, bx + box_w, by + box_h)    # remove the box, restore what was under it
    return chosen


# ============================================================
# save(name, data) / load(name, default) -- settings that survive a restart
# ============================================================

def _data_file(name):
    return "data_" + "".join(c for c in str(name) if c.isalpha() or c.isdigit() or c == "_") + ".json"


def save(name, data):
    """Stores data (numbers, text, True/False, lists, dictionaries) in the file data_<name>.json on the board.
    Flash memory wears out after very many writes: save when something really changed, not every second."""
    with open(_data_file(name), "w") as f:
        json.dump(data, f)


def load(name, default=None):
    """Returns what save(name, ...) stored, or `default` if nothing was saved yet (or the file is damaged)."""
    try:
        with open(_data_file(name)) as f:
            return json.load(f)
    except (OSError, ValueError):
        return default


# ============================================================
# WI-FI and the real time
# ============================================================
#
# wifi()          connects to the network named in the file wifi.dat on the board: line 1 = the network name,
#                 line 2 = the password. Returns True when connected. The name and the password are never printed or
#                 shown anywhere. wifi.dat is SEALED (AES, key from the chip's unique id; see wifi_cipher.py); a plain two-line
#                 file also works. (Older boards kept them in ID.dat lines 5 and 6; that still works when wifi.dat is
#                 absent. In a new ID.dat lines 5 and 6 are left EMPTY, so the town / state / country / hours-from-UTC
#                 lines below keep their numbers.) wifi.dat holds the only secret, so it is the one file never to share.
# wifi_ip()       the board's address on the network (text), or None if not connected
# wifi_off()      disconnects and switches the radio off (saves power)
# ntp()           sets the board's clock from the internet (needs wifi() first); True if it worked
# timezone(h)     hours from UTC for now(): 10 = Sydney standard time, 11 in summer time, 9.5 = Adelaide ...
#                 set automatically from ID.dat line 10 if present (lines 7/8/9 = town/state/country, for
#                 a human reading the file -- not used by the Runtime, just so "Melbourne" doesn't mean
#                 Florida). Not every Australian state observes daylight saving (WA/QLD/NT don't) and
#                 state also sets the base offset (WA UTC+8, SA/NT UTC+9:30, the rest UTC+10 standard) --
#                 state doesn't change the mechanism here, just explains the number. It does not switch
#                 itself between standard and summer time; update line 10 by hand when the season changes.
# now()           the local time as a tuple (year, month, day, hour, minute, second, weekday, yearday)
# locality()      (town, state, country, timezone_hours) from ID.dat lines 7/8/9/10, or None if not there
# Do not combine Wi-Fi with LOW_POWER = True: sleeping interrupts the connection.

_tz = 0


def _credentials():
    # (name, password) from wifi.dat, else from ID.dat lines 5-6 (older boards), else None.
    # wifi.dat is normally SEALED (one line "wattle1:...", made by wifi_setup.py, readable only on this board, see
    # wifi_cipher.py); a plain two-line file (name, password) is still accepted.
    for path, a in (("wifi.dat", 0), ("ID.dat", 4)):
        try:
            with open(path) as f:
                text = f.read()
        except OSError:
            continue
        if text.startswith("wattle1:"):
            try:
                import wifi_cipher
                text = wifi_cipher.unseal(text.split("\n")[0])
            except ImportError:
                text = None
            if text is None:
                print("wifi: wifi.dat cannot be read on this board (damaged, made for another board, or wifi_cipher is missing): run wifi_setup.py")
                return None
        lines = [t.strip() for t in text.split("\n")]
        if len(lines) > a + 1 and lines[a]:
            return lines[a], lines[a + 1]
    return None


def locality():
    """(town, state, country, timezone_hours) from ID.dat lines 7/8/9/10, or None if not set."""
    try:
        with open("ID.dat") as f:
            lines = [t.strip() for t in f.read().split("\n")]
    except OSError:
        return None
    if len(lines) >= 10 and lines[6] and lines[9]:
        try:
            return lines[6], lines[7], lines[8], float(lines[9])
        except ValueError:
            return None
    return None


_where = locality()
if _where is not None:
    _tz = _where[3]


def wifi(timeout=15):
    """Connects to the Wi-Fi network named in wifi.dat (line 1 = name, line 2 = password), waits up to `timeout`
    seconds, and returns True if connected."""
    import network
    sta = network.WLAN(network.STA_IF)
    sta.active(True)
    if sta.isconnected():
        return True
    cred = _credentials()
    if cred is None:
        print("wifi: no network name (wifi.dat line 1 is missing; run wifi_setup.py)")
        return False
    sta.connect(cred[0], cred[1])
    t0 = time.ticks_ms()
    while not sta.isconnected() and time.ticks_diff(time.ticks_ms(), t0) < timeout * 1000:
        time.sleep_ms(200)
    return sta.isconnected()


def wifi_ip():
    import network
    sta = network.WLAN(network.STA_IF)
    return sta.ifconfig()[0] if sta.active() and sta.isconnected() else None


def wifi_off():
    import network
    sta = network.WLAN(network.STA_IF)
    if sta.active():
        sta.disconnect()
        sta.active(False)


def ntp():
    """Sets the clock from the internet (pool.ntp.org). Returns True if it worked."""
    try:
        import ntptime
        ntptime.settime()
        return True
    except Exception as e:
        print("ntp:", e)
        return False


def timezone(hours):
    """Hours from UTC used by now() (10 = Sydney standard time; the script handles summer time)."""
    global _tz
    _tz = hours


def now():
    """The local time (see timezone()): (year, month, day, hour, minute, second, weekday, yearday)."""
    return time.localtime(time.time() + int(_tz * 3600))


def _prealloc_buffers():
    # Gauge and chart drawing keep one buffer per widget. Allocating them all now, once, while the heap is still
    # in one piece, stops a later screen change failing for want of a contiguous block (stress test 37, Oct 2026).
    gc.collect()
    for w in widgets.values():
        kind = w.get("widget")
        if kind == "gauge":
            need = (2 * _gauge_geom(w)[2] + 3) * 12 * 2
        elif kind in ("waveform", "barchart"):
            x0, top, x1, bot = _chart_area(w)
            need = (x1 - x0) * 12 * 2
        else:
            continue
        buf = _gauge_buf.get(w["id"])
        if buf is None or len(buf) < need:
            _gauge_buf[w["id"]] = bytearray(need)


def run(module=None, poll_ms=150):
    """Runs forever: waits for events and calls the matching handler.
    module = the USER script's module (optional; by default the script
    that is running, then any imported module, is searched).
    poll_ms = how often the touch screen is checked (default 150 ms). A longer
    interval saves power (especially with LOW_POWER) but taps are noticed later."""

    print("Runtime: running")

    _prealloc_buffers()

    set_poll_ms(poll_ms)

    while True:

        widget_id, event, value = wait_event(None, _poll)

        handler = _find_handler(widget_id + "_" + event, module)

        if handler is None:
            continue

        try:
            if value is None:
                handler()
            else:
                handler(value)
        except Exception as e:
            _error_screen(e, "in handler %s_%s" % (widget_id, event))
            _restore_screen()


# What "from Runtime import *" hands to the USER script: widgets by name.
__all__ = list(widgets) + ["Screen", "every", "stop", "set_poll_ms", "set_longpress_ms", "message", "save", "load", "fatal", "backlight", "screensaver", "power_button", "wifi", "wifi_ip", "wifi_off", "ntp", "timezone", "now", "locality", "run", "get_event", "wait_event", "widgets", "widget_objs"]
