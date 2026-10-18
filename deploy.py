#!/usr/bin/env python3
# deploy.py -- DESKTOP tool: puts your design and your script on the board, CHECKS the copies on the board, and starts
# the board only if the check finds no errors.
#
#   python3 deploy.py hello.json Project_1.py
#   python3 deploy.py hello.json Project_1.py --no-check        (skip the check)
#
# What it does: stops the board, writes design.txt (the design's name and the board), copies the design and the script
# (the script gets the name that main.py expects: PROJECT, "Project_1" by default), copies the fonts and pictures the
# design uses, checks the files that are now on the board (check_script.py), and restarts the board.
# The Runtime and the drivers are not touched: copy them once, as described in the Quick Guide.
import json, os, subprocess, sys, tempfile

import boardlink

HERE = os.path.dirname(os.path.abspath(__file__))


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    if len(args) != 2:
        sys.exit("usage: python3 deploy.py design.json script.py [--no-check]")
    design_path, script_path = args
    check = "--no-check" not in sys.argv
    for p in (design_path, script_path):
        if not os.path.exists(p):
            sys.exit("file not found: " + p)
    try:
        design = json.load(open(design_path))
    except ValueError as e:
        sys.exit("%s is not valid JSON: %s" % (design_path, e))
    design_name = os.path.basename(design_path)

    print("stopping the board ...")
    boardlink.halt()

    main_py = boardlink.cat("main.py")
    if main_py is None:
        sys.exit("main.py is not on the board: copy the program files first (see the Quick Guide).")
    import re
    m = re.search(r'PROJECT\s*=\s*["\']([^"\']+)["\']', main_py)
    project = (m.group(1) if m else "Project_1") + ".py"

    board = design.get("target", {}).get("board") or "board_cyd"
    with tempfile.TemporaryDirectory() as tmp:
        txt = os.path.join(tmp, "design.txt")
        open(txt, "w").write(design_name + "\n" + board + "\n")
        print("copying design.txt, %s, %s (as %s) ..." % (design_name, os.path.basename(script_path), project))
        boardlink.put(txt, "design.txt")
        boardlink.put(design_path, design_name)
        boardlink.put(script_path, project)

        widgets = [w for s in design.get("screens", []) for w in s.get("widgets", [])]
        errfont = os.path.join(HERE, "fonts", "dejavusansmono_12.fnt")      # for the on-screen error messages
        fonts = {w.get("font_type", "default") for w in widgets} - {"default", ""}
        if fonts or os.path.exists(errfont):
            subprocess.run(["mpremote", "connect", boardlink.PORT, "fs", "mkdir", ":fonts"], capture_output=True)
        if os.path.exists(errfont):
            boardlink.put(errfont, "fonts/dejavusansmono_12.fnt")
        if fonts:
            print("copying fonts: " + ", ".join(sorted(fonts)))
            subprocess.run([sys.executable, os.path.join(HERE, "make_fonts.py"), "--upload", design_path], check=True)
        if any(w.get("widget") == "image" for w in widgets):
            print("converting and copying pictures ...")
            subprocess.run([sys.executable, os.path.join(HERE, "make_images.py"), os.path.abspath(design_path), "upload"],
                           check=True, cwd=tmp)

    if check:
        import check_script
        print("checking the files on the board ...")
        if check_script.check_board(restart=False, halt=False):
            print("\nThe board has NOT been started because of the errors above.")
            print("Fix them and run deploy.py again.")
            sys.exit(1)
    print("starting the board ...")
    boardlink.restart()
    print("done.")


main()
