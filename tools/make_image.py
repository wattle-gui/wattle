#!/usr/bin/env python3
# make_image.py -- DEVELOPER tool. Builds ONE ready-made flash image for a plain ESP32 (4 MB): MicroPython and all the Wattle files for the
# browser version, so that a new ESP32 only has to be written once (no MicroPython step, no copying of files).
#
#   python3 tools/make_image.py --firmware ESP32_GENERIC-20251209-v1.27.0.bin --out wattle_esp32_4MB.bin
#
# Needs the Python package littlefs-python (pip install littlefs-python). The image is 4 MiB:
#   0x0000-0x0fff   empty        0x1000   MicroPython (bootloader, partition table and program, as downloaded from micropython.org)
#   0x200000        the file system (2 MiB, littlefs) holding the Wattle files: main.py, Runtime.py, wnet.py, wifi_cipher.py, webui.html and the demo.
# Write it with:  esptool --chip esp32 write_flash -z 0x0 wattle_esp32_4MB.bin   (this ERASES everything on the ESP32).
import argparse, os, sys
from littlefs import LittleFS

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)
import install_wattle as iw

FLASH = 4 * 1024 * 1024
FS_AT, FS_SIZE, BLOCK = 0x200000, 0x200000, 4096        # the "vfs" partition of the standard 4 MB layout of MicroPython for the ESP32


def wattle_files():
    files = [(dst, iw.load(src)) for src, dst in iw.BROWSER_FILES + iw.BROWSER_DEMO]
    files.append(("design.txt", b"design.json\nboard_browser\n"))
    for name, data in files:
        if data is None:
            sys.exit("a Wattle file is missing: " + name)
    return files


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--firmware", required=True, help="MicroPython for the ESP32 (ESP32_GENERIC ... .bin)")
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    fw = open(a.firmware, "rb").read()
    if fw[:1] != b"\xe9":
        sys.exit("that does not look like an ESP32 firmware file")
    fs = LittleFS(block_size=BLOCK, block_count=FS_SIZE // BLOCK, read_size=32, prog_size=32, lookahead_size=32, cache_size=512)
    fs.mkdir("pictures")
    total = 0
    for name, data in wattle_files():
        with fs.open(name, "wb") as f:
            f.write(data)
        total += len(data)
        print("  %-18s %6d bytes" % (name, len(data)))
    image = bytearray(b"\xff" * FLASH)
    image[0x1000:0x1000 + len(fw)] = fw
    image[FS_AT:FS_AT + FS_SIZE] = bytes(fs.context.buffer)
    open(a.out, "wb").write(image)
    print("wrote %s: %d KB firmware + %d KB of Wattle files, 4 MiB in all" % (a.out, len(fw) // 1024, total // 1024))


if __name__ == "__main__":
    main()
