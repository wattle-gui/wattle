#!/usr/bin/env python3
# deploy.py -- DESKTOP tool: puts your design and your script on the board, CHECKS the copies on the board, and starts
# the board only if the check finds no errors.
#
#   python3 deploy.py hello.json Project_1.py
#   python3 deploy.py hello.json Project_1.py --no-check        (skip the check)
#   python3 deploy.py demo.json demo.py --as demo               (the script gets another name; the installer does this for the demo)
#
# What it does: stops the board, writes design.txt (the design's name and the board), copies the design and the script
# (the script gets the name that main.py expects: PROJECT, "Project_1" by default), copies the fonts and pictures the
# design uses, checks the files that are now on the board (check_script.py), and restarts the board.
# The Runtime and the drivers are not touched: copy them once, as described in the Quick Guide.
import json, os, subprocess, sys, tempfile, time

import boardlink

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))     # the Wattle folder (this file is in tools/)


def browser_files(tmp, design, design_path, script_path, project):
    """Browser board: the design goes up as design.json, the script under its project name, and every picture of the design into
    pictures/ as it is (jpg, png or gif; a big one is made smaller first, the browser never needs more than twice the widget size)."""
    import shutil
    here = os.path.dirname(os.path.abspath(design_path))
    pics = {}                                            # picture file on this computer -> name on the board
    for scr in design.get("screens", []):
        for w in scr.get("widgets", []):
            if w.get("widget") != "image" or not w.get("source"):
                continue
            src = w["source"]
            found = next((p for p in (src, os.path.join(here, src)) if os.path.exists(p)), None)
            if found is None:
                print("WARNING: the picture '%s' of %s was not found; the page will show its name instead." % (src, w.get("id")))
                continue
            name = "pictures/" + os.path.basename(src)
            pics[found] = name
            w["source"] = name
            try:
                from PIL import Image
                im = Image.open(found)
                if im.format in ("JPEG", "PNG") and (im.width > 2 * w["w"] or im.height > 2 * w["h"]):
                    im.thumbnail((2 * w["w"], 2 * w["h"]))
                    small = os.path.join(tmp, os.path.basename(src))
                    im.save(small, im.format, **({"quality": 85} if im.format == "JPEG" else {}))
                    pics[found] = (name, small)
            except Exception:
                pass
    out = os.path.join(tmp, "design.json")
    json.dump(design, open(out, "w"))
    boardlink.put(out, "design.json")
    boardlink.put(script_path, project)
    if pics:
        subprocess.run(boardlink.MPREMOTE + ["connect", boardlink.PORT, "fs", "mkdir", ":pictures"], capture_output=True)
        print("copying pictures: " + ", ".join(sorted(os.path.basename(v if isinstance(v, str) else v[0]) for v in pics.values())))
        for found, v in pics.items():
            name, local = (v, found) if isinstance(v, str) else v
            boardlink.put(local, name)


def show_address(name="wattle"):
    """Browser board: asks the board over the network (NOT over the cable: reading a file with mpremote stops the program that is just
    starting) whether it has joined the Wi-Fi, and tells where to point the phone."""
    import urllib.request
    print("waiting for the board to join the Wi-Fi ...")
    time.sleep(8)
    for _ in range(10):
        try:
            log = urllib.request.urlopen("http://%s.local/log" % name, timeout=4).read().decode().split("\n")
            last = max([i for i, l in enumerate(log) if "boot, reset cause" in l] or [0])
            ok = [l for l in log[last:] if "wifi ok" in l]
            ip = ok[-1].split("wifi ok")[1].strip() if ok else "(see your router's list of devices)"
            print("\nOpen this on your phone, tablet or computer (same Wi-Fi):")
            print("    http://" + ip)
            print("    http://%s.local      (the name: it works on most phones, but not always)" % name)
            return
        except Exception:
            time.sleep(2)
    print("\nThe board did not answer from this computer yet. Give it a little longer, then open  http://%s.local  on the phone." % name)
    print("If that does not work, the board may not have your Wi-Fi:   wattle wifi")


def detect_board():
    """Which kind of board this is, from the Wattle files on it: 'board_cyd', 'board_browser', or '' when it cannot tell."""
    if boardlink.cat("board_cyd.py") is not None:
        return "board_cyd"
    if boardlink.cat("wnet.py") is not None:
        return "board_browser"
    return ""


def catalogue_size(board):
    """(width, height) of the board's own screen from hardware/<board>.json, or None for a board without a screen of its own (the browser)."""
    if board == "board_browser":
        return None
    try:
        with open(os.path.join(HERE, "hardware", board + ".json"), encoding="utf-8") as f:
            d = json.load(f)
        return int(d["width"]), int(d["height"])
    except (OSError, ValueError, KeyError, TypeError):
        return None


def main():
    argv = sys.argv[1:]
    as_name = None                                       # --as NAME: give the script this name on the board (the installer uses it for the demo)
    if "--as" in argv:
        i = argv.index("--as")
        as_name = argv[i + 1] if i + 1 < len(argv) else None
        del argv[i:i + 2]
    args = [a for a in argv if not a.startswith("--")]
    if len(args) != 2:
        sys.exit("usage: python3 tools/deploy.py design.json script.py [--no-check]")
    design_path, script_path = args
    check = "--no-check" not in sys.argv
    for p in (design_path, script_path):
        if not os.path.exists(p):
            sys.exit("file not found: " + p)
    try:
        design = json.load(open(design_path))
    except ValueError as e:
        sys.exit("%s is not a valid design file (bad JSON): %s" % (design_path, e))
    design_name = os.path.basename(design_path)

    print("stopping the board ...")
    boardlink.halt()
    board_name = (boardlink.cat("board_name.txt") or "").strip()
    if board_name:
        print("  (the board: %s)" % board_name)

    main_py = boardlink.cat("main.py")
    if main_py is None:
        sys.exit("main.py is not on the board: copy the Wattle files first (see the Quick Guide).")
    import re
    m = re.search(r'PROJECT\s*=\s*["\']([^"\']+)["\']', main_py)
    project = (as_name or (m.group(1) if m else "Project_1")) + ".py"

    header = (design.get("target") or {}).get("board") or ""
    found = detect_board()
    board = found or header or "board_cyd"               # the BOARD decides, not the design's header
    if found and header and header != found:
        print("  (the design says it is for %s, but this board is %s: it is sent as a %s design)" %
              (header, found, "CYD" if found == "board_cyd" else "browser"))
        design.setdefault("target", {})["board"] = found
    size = catalogue_size(board)
    if size and "--force" not in sys.argv:
        for sc in design.get("screens", []):
            w, h = int(sc.get("width") or 0), int(sc.get("height") or 0)
            if (w, h) not in (size, size[::-1]):
                sys.exit("\n  Your design's screen is %d x %d, but this board's screen is %d x %d (or %d x %d turned).\n"
                         "  Change the size of the screen in the Editor (select the screen, then Width and Height), or put this design on a board with a bigger screen.\n"
                         "  (To send it anyway:  add  --force )" % (w, h, size[0], size[1], size[1], size[0]))
    with tempfile.TemporaryDirectory() as tmp:
        if board == "board_browser":
            design_name = "design.json"                  # the browser Runtime always reads this file
        txt = os.path.join(tmp, "design.txt")
        open(txt, "w").write(design_name + "\n" + board + "\n")
        print("sending your design and script to the board ...")
        boardlink.put(txt, "design.txt")
        if board != "board_browser":
            if (design.get("target") or {}).get("board") != header:      # the header was corrected: send the corrected copy
                fixed = os.path.join(tmp, design_name)
                json.dump(design, open(fixed, "w"), indent=2)
                boardlink.put(fixed, design_name)
            else:
                boardlink.put(design_path, design_name)
            boardlink.put(script_path, project)

        widgets = [w for s in design.get("screens", []) for w in s.get("widgets", [])]
        if board == "board_browser":
            browser_files(tmp, design, design_path, script_path, project)
            widgets = []                                 # the browser needs no fonts and no .raw pictures
        errfont = os.path.join(HERE, "fonts", "dejavusansmono_12.fnt")      # for the on-screen error messages
        fonts = {w.get("font_type", "default") for w in widgets} - {"default", ""}
        if fonts or os.path.exists(errfont):
            subprocess.run(boardlink.MPREMOTE + ["connect", boardlink.PORT, "fs", "mkdir", ":fonts"], capture_output=True)
        if os.path.exists(errfont):
            boardlink.put(errfont, "fonts/dejavusansmono_12.fnt")
        if fonts:
            print("copying fonts: " + ", ".join(sorted(fonts)))
            subprocess.run([sys.executable, os.path.join(HERE, "tools", "make_fonts.py"), "--upload", design_path], check=True)
        if any(w.get("widget") == "image" for w in widgets):
            print("converting and copying pictures ...")
            result = subprocess.run([sys.executable, os.path.join(HERE, "tools", "make_images.py"), os.path.abspath(design_path), "upload"],
                                    cwd=tmp)
            if result.returncode:                        # make_images has already said, in plain words, what is wrong
                sys.exit(1)

    if check:
        import check_script
        print("checking the files on the board ...")
        if check_script.check_board(restart=False, halt=False):
            print("\nThe board has NOT been started because of the errors above.")
            print("Fix them and run deploy.py again.")
            sys.exit(1)
    name = ((boardlink.cat("name.dat") or "").strip() or "wattle") if board == "board_browser" else ""     # read BEFORE the restart (never after)
    print("starting the board ...")
    boardlink.restart()
    if board == "board_browser":
        show_address(name)
    print("done.")


main()
