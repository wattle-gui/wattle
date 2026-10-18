#!/usr/bin/env python3
# make_fonts.py -- DESKTOP tool (not for the board).
# Converts TrueType fonts into small anti-aliased bitmap fonts (.fnt) that
# Runtime.py draws, and writes a manifest into hardware/ so picker.py and the
# designer list them.
#
#   python3 make_fonts.py                       all built-in presets, default sizes
#   python3 make_fonts.py --sizes 12,16,24      choose sizes
#   python3 make_fonts.py --upload fonts.json   copy to the board ONLY the .fnt
#                                               files that design uses
#
# .fnt layout (little endian):
#   header: height, first char (32), count (95), 0
#   table : count x [advance u8, offset u32]      (offset from start of glyph data)
#   glyphs: each advance x height pixels, 4-bit alpha, high nibble first,
#           rows padded to whole bytes (stride = (advance + 1) // 2)
import glob, json, os, re, struct, subprocess, sys
from PIL import Image, ImageDraw, ImageFont

import wattle_port
PORT = wattle_port.PORT   # ESP_PORT, or wattle.port, or /dev/ttyUSB0
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))     # the Wattle folder (this file is in tools/)
OUT = os.path.join(HERE, "fonts")
HW = os.path.join(HERE, "hardware")
SIZES = [10, 12, 14, 16, 20, 24, 32]
FIRST, COUNT = 32, 95          # ASCII 32..126
SHEAR = 0.2                    # slant used when a font has no italic file

D = "/usr/share/fonts/truetype/dejavu/"
L = "/usr/share/fonts/truetype/liberation/"
C = "/usr/share/fonts/truetype/comic-relief-zorin-os/"
PRESETS = {
    "DejaVu Sans": {"": D + "DejaVuSans.ttf", "b": D + "DejaVuSans-Bold.ttf"},
    "DejaVu Sans Mono": {"": D + "DejaVuSansMono.ttf", "b": D + "DejaVuSansMono-Bold.ttf",
                         "i": D + "DejaVuSansMono-Oblique.ttf", "bi": D + "DejaVuSansMono-BoldOblique.ttf"},
    "DejaVu Serif": {"": D + "DejaVuSerif.ttf", "b": D + "DejaVuSerif-Bold.ttf"},
    # Familiar names, made from the free look-alike fonts (same letter shapes/widths)
    "Arial": {"": L + "LiberationSans-Regular.ttf", "b": L + "LiberationSans-Bold.ttf",
              "i": L + "LiberationSans-Italic.ttf", "bi": L + "LiberationSans-BoldItalic.ttf"},
    "Times New Roman": {"": L + "LiberationSerif-Regular.ttf", "b": L + "LiberationSerif-Bold.ttf",
                        "i": L + "LiberationSerif-Italic.ttf", "bi": L + "LiberationSerif-BoldItalic.ttf"},
    "Comic Sans MS": {"": C + "ComicRelief-Regular.ttf", "b": C + "ComicRelief-Bold.ttf"},
}
SOURCE = {"Arial": "Liberation Sans (free look-alike)",
          "Times New Roman": "Liberation Serif (free look-alike)",
          "Comic Sans MS": "Comic Relief (free look-alike)"}


def slug(name):
    return re.sub(r"[^a-z0-9]", "", name.lower())


def fnt_name(name, size, style):
    return "%s_%d%s.fnt" % (slug(name), size, style)


def glyph(font, ch, ascent, h, slant):
    """(advance, 4-bit rows) for one character."""
    adv = max(1, round(font.getlength(ch)))
    pad = int(h * SHEAR) if slant else 0
    img = Image.new("L", (adv + pad + 4, h), 0)
    ImageDraw.Draw(img).text((0, ascent), ch, font=font, fill=255, anchor="ls")
    if slant:   # shear about the baseline: top moves right
        img = img.transform(img.size, Image.AFFINE, (1, SHEAR, -SHEAR * ascent, 0, 1, 0),
                            resample=Image.BILINEAR)
    # keep ink that overhangs the advance (italic, wide letters), widen the cell
    bbox = img.getbbox()
    width = max(adv, bbox[2] if bbox else adv)
    img = img.crop((0, 0, width, h))
    return width, img


def build(name, size, style, path, slant):
    font = ImageFont.truetype(path, size)
    ascent, descent = font.getmetrics()
    h = ascent + descent
    table, data, widths = [], bytearray(), {}
    for code in range(FIRST, FIRST + COUNT):
        ch = chr(code)
        w, img = glyph(font, ch, ascent, h, slant)
        table.append((w, len(data)))
        widths[ch] = w
        px = img.load()
        for y in range(h):
            row = bytearray((w + 1) // 2)
            for x in range(w):
                a = (px[x, y] + 8) // 17
                row[x >> 1] |= (a << 4) if x % 2 == 0 else a
            data += row
    out = bytearray([h, FIRST, COUNT, 0])
    for w, off in table:
        out += struct.pack("<BI", w, off)
    out += data
    os.makedirs(OUT, exist_ok=True)
    open(os.path.join(OUT, fnt_name(name, size, style)), "wb").write(out)
    return h, widths


def convert(sizes):
    os.makedirs(HW, exist_ok=True)
    for name, files in PRESETS.items():
        metrics = {}
        for size in sizes:
            for style in ("", "b", "i", "bi"):
                if style in files:
                    path, slant = files[style], False
                else:       # no italic file: slant the upright one
                    path, slant = files[style.replace("i", "")], True
                h, widths = build(name, size, style, path, slant)
                metrics["%d%s" % (size, style)] = {"height": h, "widths": widths}
        open(os.path.join(HW, "font_%s.json" % slug(name)), "w").write(json.dumps(
            {"kind": "font", "name": name, "type": "anti-aliased bitmap (4-bit)",
             "file": "%s_<size>[b][i].fnt" % slug(name), "sizes": sizes,
             "styles": ["bold", "italic"], "source": SOURCE.get(name, name)}, indent=1) + "\n")
        # per-glyph widths: lets the designer measure text exactly
        open(os.path.join(OUT, "metrics_%s.json" % slug(name)), "w").write(json.dumps(metrics))
        print(name, "->", len(sizes) * 4, "files")


def pick_size(name, size):
    """Same rule Runtime.py uses: nearest available size, else 16."""
    try:
        want = int(size)
    except (ValueError, TypeError):
        want = 16
    have = sorted(int(re.search(r"_(\d+)", os.path.basename(p)).group(1))
                  for p in glob.glob(os.path.join(OUT, slug(name) + "_*.fnt")))
    have = sorted(set(have))
    return min(have, key=lambda s: abs(s - want)) if have else None


def upload(design_path):
    design = json.load(open(design_path))
    need = set()
    for scr in design["screens"]:
        for w in scr["widgets"]:
            ft = w.get("font_type", "default")
            if ft in ("", "default"):
                continue
            size = pick_size(ft, w.get("font_size", "default"))
            if size is None:
                print("no font files for", ft)
                continue
            style = ("b" if w.get("bold") else "") + ("i" if w.get("italic") else "")
            need.add(fnt_name(ft, size, style))
    subprocess.run(["mpremote", "connect", PORT, "fs", "mkdir", ":fonts"],
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)   # ok if it exists
    for n in sorted(need):
        subprocess.run(["mpremote", "connect", PORT, "fs", "cp",
                        os.path.join(OUT, n), ":fonts/" + n], check=True)
    print("uploaded", len(need), "font files")


if __name__ == "__main__":
    a = sys.argv
    if "--upload" in a:
        upload(a[a.index("--upload") + 1])
    else:
        sizes = [int(v) for v in a[a.index("--sizes") + 1].split(",")] if "--sizes" in a else SIZES
        convert(sizes)
