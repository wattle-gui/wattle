#!/usr/bin/env python3
# install_board.py -- DESKTOP tool: puts the Wattle program files on the CYD in one go.
#
#   python3 install_board.py            copy the files, then restart the board
#   (--fast is accepted but no longer needed: the precompiled files are always installed)
#   python3 install_board.py --dry-run  only show what would be copied; touches nothing
#
# It copies: Runtime.mpy, ili9341.mpy, board_cyd.py, touch_xpt2046.py, main.py (and calibrate_touch.py), and the one font that the
# on-screen error messages use. The other fonts are NOT copied (the whole fonts folder is bigger than the board's memory): deploy.py
# copies the fonts a design needs. Your own design and script are added afterwards with deploy.py (chapter 6.1).
# The port is /dev/ttyUSB0 unless the environment variable ESP_PORT says otherwise (Windows: set ESP_PORT=COM5).
import os, shutil, subprocess, sys

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))     # the Wattle folder (this file is in tools/)
sys.path.insert(0, HERE)
# Runtime and the display driver go to the board PRECOMPILED (.mpy): a board cannot compile the 92 KB Runtime.py source itself
# (MemoryError at start-up, black screen). The .mpy files come with the package; make_mpy.py makes them after a source change.
FILES = ["Runtime.mpy", "ili9341.mpy", "board_cyd.py", "touch_xpt2046.py", "main.py", "wifi_cipher.py", "calibrate_touch.py"]
OLD_SOURCES = ["Runtime.py", "ili9341.py"]     # a .py on the board would be used INSTEAD of the .mpy, so these are removed
dry = "--dry-run" in sys.argv
fast = "--fast" in sys.argv


def find(name):
    for folder in (HERE, os.path.join(HERE, "board"), os.path.join(os.path.dirname(HERE), "board")):
        p = os.path.join(folder, name)
        if os.path.exists(p):
            return p
    return None


def step(text):
    print(" *", text)


if not shutil.which("mpremote"):
    sys.exit("mpremote is not installed. Run:  pip install mpremote")
missing = [f for f in FILES[:6] if not find(f)]
if missing:
    sys.exit("these files were not found next to install_board.py (or in a 'board' folder): " + ", ".join(missing))

import boardlink
print("Installing Wattle on the board at", boardlink.PORT)
for f in FILES:
    p = find(f)
    if p:
        step("%s  (%d bytes)%s" % (f, os.path.getsize(p), "" if f in FILES[:6] else "  optional"))
errfont = find("fonts/dejavusansmono_12.fnt")
if errfont:
    step("fonts/dejavusansmono_12.fnt  (the font of the on-screen error messages)")
if dry:
    print("Dry run: nothing was copied.")
    sys.exit(0)

step("stopping whatever the board is running")
boardlink.halt()
for old in OLD_SOURCES:
    subprocess.run(["mpremote", "connect", boardlink.PORT, "fs", "rm", ":" + old], capture_output=True)   # fine if absent
step("removed any old Runtime.py / ili9341.py (they would hide the precompiled files)")
for f in FILES:
    p = find(f)
    if p:
        step("copying " + f)
        boardlink.put(p, f)
if errfont:
    step("copying the error-message font")
    subprocess.run(["mpremote", "connect", boardlink.PORT, "fs", "mkdir", ":fonts"], capture_output=True)
    boardlink.put(errfont, "fonts/dejavusansmono_12.fnt")
boardlink.restart()
if os.environ.get("WATTLE_FROM_INSTALLER"):
    print("Done. The board has restarted.")
else:
    print("Done. The board has restarted. Next: ./wattle deploy yourapp  (or: python3 tools/deploy.py yourdesign.json Project_1.py)")
