#!/usr/bin/env python3
# check_functions_table.py -- every public function of the two Runtimes must appear in the table "What your script can do" (manual/01_Introduction.md).
import re, sys, os
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
table = open(os.path.join(ROOT, "manual", "01_Introduction.md"), encoding="utf-8").read()
table = table[table.index("What your script can do"):]
table = table[:table.index("## 1.3")] if "## 1.3" in table else table
# internal helpers of the CYD Runtime that a script never calls
INTERNAL = {"colour", "draw_char", "draw_line", "widget_font", "fsize", "redraw_widget", "find_widget", "fatal", "Screen"}
missing = []
for runtime in ("Runtime.py", os.path.join("browser", "Runtime.py")):
    src = open(os.path.join(ROOT, runtime), encoding="utf-8").read()
    names = set(re.findall(r"^def ([a-z][a-zA-Z0-9_]*)\(", src, re.M)) - INTERNAL
    if runtime.startswith("browser"):
        m = re.search(r"class _Phone:(.*?)^phone = ", src, re.S | re.M)
        names |= set("phone." + n for n in re.findall(r"^    def ([a-z]\w*)\(", m.group(1), re.M) if n != "landscape") | {"phone.landscape", "phone.width", "phone.height"}
        m = re.search(r"class _Board:(.*?)^board = ", src, re.S | re.M)
        names |= set("board." + n for n in re.findall(r"^    def ([a-z]\w*)\(", m.group(1), re.M)) | {"board.name"}
    for n in sorted(names):
        if n not in table:
            missing.append((runtime, n))
for runtime, n in missing:
    print("NOT IN THE TABLE: %-10s %s" % (n, runtime))
print("all public functions are in the table" if not missing else "%d missing" % len(missing))
sys.exit(1 if missing else 0)
