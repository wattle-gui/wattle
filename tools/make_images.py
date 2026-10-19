#!/usr/bin/env python3
# make_images.py -- DESKTOP tool (not for the board).
# Converts every "image" widget in a design JSON into <widget id>.raw
# (RGB565, exactly w x h pixels, big-endian) which Runtime.py draws.
# Usage: python3 make_images.py 777.json [upload]
#   "upload" also copies the .raw files to the board with mpremote.
import os as _os
import wattle_port
PORT = wattle_port.PORT   # ESP_PORT, or wattle.port, or the plugged-in board
MPREMOTE = wattle_port.MPREMOTE
import json, subprocess, sys
from PIL import Image

COLOURS = {"gray": (128, 128, 128), "black": (0, 0, 0), "white": (255, 255, 255), "red": (255, 0, 0),
           "green": (0, 255, 0), "blue": (0, 0, 255), "yellow": (255, 255, 0), "cyan": (0, 255, 255),
           "magenta": (255, 0, 255)}


def colour(v):
    v = v.lower()
    if v.startswith("#") and len(v) == 7:
        return tuple(int(v[i:i + 2], 16) for i in (1, 3, 5))
    return COLOURS.get(v, (0, 0, 0))

design = json.load(open(sys.argv[1]))
made = []


def find_source(path):
    """A picture path may be absolute, or relative to where you run this program, or relative to the design file's own folder."""
    if _os.path.isabs(path) or _os.path.exists(path):
        return path
    beside = _os.path.join(_os.path.dirname(_os.path.abspath(sys.argv[1])), path)
    return beside if _os.path.exists(beside) else path


for scr in design["screens"]:
    for w in scr["widgets"]:
        if w.get("widget") != "image":
            continue
        W, H = w["w"], w["h"]
        im = Image.open(find_source(w["source"])).convert("RGBA")
        # "transparent": true -> the screen's background shows around/through the
        # picture; otherwise the widget's own background colour is used.
        pad = colour(scr.get("background", "black") if w.get("transparent") else w.get("background", "gray"))
        mode = w.get("scale", "fit")
        if mode == "stretch":
            im = im.resize((W, H))
            canvas = Image.new("RGB", (W, H), pad)
            canvas.paste(im, (0, 0), im)
        elif mode == "fill":  # crop to cover, no distortion, no bars
            k = max(W / im.width, H / im.height)
            im = im.resize((max(W, round(im.width * k)), max(H, round(im.height * k))))
            l, t = (im.width - W) // 2, (im.height - H) // 2
            im = im.crop((l, t, l + W, t + H))
            canvas = Image.new("RGB", (W, H), pad)
            canvas.paste(im, (0, 0), im)
        else:  # fit: keep aspect ratio, pad with the colour above
            im.thumbnail((W, H))
            canvas = Image.new("RGB", (W, H), pad)
            canvas.paste(im, ((W - im.width) // 2, (H - im.height) // 2), im)
        out = bytearray()
        for r, g, b in canvas.getdata():
            v = ((r & 0xF8) << 8) | ((g & 0xFC) << 3) | (b >> 3)
            out += bytes((v >> 8, v & 255))
        name = w["id"] + ".raw"
        open(name, "wb").write(out)
        made.append(name)
        print(name, W, "x", H, len(out), "bytes")

if "upload" in sys.argv:
    for n in made:
        subprocess.run(MPREMOTE + ["connect", PORT, "fs", "cp", n, ":" + n], check=True)
