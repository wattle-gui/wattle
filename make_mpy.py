#!/usr/bin/env python3
# make_mpy.py -- DESKTOP tool (optional speed-up for ESP32 / "xtensawin" boards).
# Precompiles Runtime.py and ili9341.py to .mpy and puts them on the board in place
# of the .py sources: start-up is ~3x faster and uses less RAM.
#
#   pip install mpy-cross==1.24.1.post3          (must match the board's MicroPython: 1.24.x)
#   python3 make_mpy.py                          compile + upload + delete the .py on the board
#   python3 make_mpy.py --arch rv32imc           other chips (ESP32-C3/C6 = rv32imc)
#
# GOTCHA: if you later copy a new Runtime.py to the board, a .py wins over a .mpy.
# Run this tool again (or delete the .mpy) after changing the source.
import glob, os, shutil, subprocess, sys

HERE = os.path.dirname(os.path.abspath(__file__))
import wattle_port
PORT = wattle_port.PORT     # ESP_PORT, or wattle.port, or /dev/ttyUSB0
FILES = ["Runtime", "ili9341"]

arch = sys.argv[sys.argv.index("--arch") + 1] if "--arch" in sys.argv else "xtensawin"

exe = shutil.which("mpy-cross")
if not exe:
    for pat in ("mpy_cross/mpy-cross*", "mpy_cross/mpy_cross*"):
        import site
        for base in site.getsitepackages() + [site.getusersitepackages()]:
            hits = [h for h in glob.glob(os.path.join(base, pat)) if os.path.isfile(h) and not h.endswith(".py")]
            if hits:
                exe = hits[0]
                if not os.access(exe, os.X_OK):          # pip may not keep the "executable" mark
                    os.chmod(exe, 0o755)
if not exe:
    sys.exit("mpy-cross not found. pip install mpy-cross==1.24.1.post3")

for name in FILES:
    src, out = os.path.join(HERE, name + ".py"), os.path.join(HERE, name + ".mpy")
    subprocess.run([exe, "-march=" + arch, "-o", out, src], check=True)
    subprocess.run(["mpremote", "connect", PORT, "fs", "cp", out, ":" + name + ".mpy"], check=True)
    subprocess.run(["mpremote", "connect", PORT, "fs", "rm", ":" + name + ".py"])   # ok if absent
    print(name, "->", name + ".mpy", os.path.getsize(out), "bytes")
print("done -- run reset to restart the board")
