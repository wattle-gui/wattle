#!/usr/bin/env python3
# make_installer.py -- DEVELOPER tool. Builds the board files INTO install_wattle.py, so the installer is ONE self-contained file
# (the only thing a user has to download).
#
#   python3 make_installer.py            refresh the files inside install_wattle.py
#   python3 make_installer.py --check    only say whether the files inside are up to date (exit code 1 if not)
#
# RUN IT AFTER ANY CHANGE to Runtime.py / ili9341.py (first make the new .mpy files with make_mpy.py or mpy-cross), board_cyd.py,
# touch_xpt2046.py, main.py, wifi_cipher.py, calibrate_touch.py, the font or hello_demo/ -- and commit install_wattle.py again.
import base64
import os
import re
import sys
import zlib

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))     # the Wattle folder (this file is in tools/)
sys.path.insert(0, HERE)
import install_wattle as iw

SOURCES = list(iw.PROGRAMS if hasattr(iw, "PROGRAMS") else iw.PROGRAM_FILES) + [iw.FONT] + list(iw.OPTIONAL_FILES) + [s for s, _ in iw.DEMO]
BEGIN = "# BEGIN EMBEDDED FILES (made by make_installer.py: do not edit by hand)\n"
END = "# END EMBEDDED FILES\n"


def block():
    out = ["EMBEDDED = {\n"]
    for src in SOURCES:
        path = os.path.join(HERE, src)
        if not os.path.exists(path):
            if src in iw.OPTIONAL_FILES or src == iw.FONT:
                print("  (skipped, not found: %s)" % src)
                continue
            sys.exit("missing file: %s" % src)
        raw = open(path, "rb").read()
        b64 = base64.b64encode(zlib.compress(raw, 9)).decode()
        lines = "\n".join(b64[i:i + 100] for i in range(0, len(b64), 100))
        out.append('    "%s": """\n%s\n""",   # %d bytes\n' % (src, lines, len(raw)))
    out.append("}\n")
    return "".join(out)


def main():
    path = os.path.join(HERE, "install_wattle.py")
    text = open(path, encoding="utf-8").read()
    a = text.index(BEGIN) + len(BEGIN)
    b = text.index(END)
    new = block()
    if "--check" in sys.argv:
        if text[a:b] == new:
            print("install_wattle.py is up to date.")
            return 0
        print("install_wattle.py is OUT OF DATE: run make_installer.py and commit it.")
        return 1
    open(path, "w", encoding="utf-8").write(text[:a] + new + text[b:])
    count = len(re.findall(r'^    "[^"]+": """', new, re.M))
    print("install_wattle.py now carries %d files (installer %d KB in all)." % (count, os.path.getsize(path) // 1024))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
