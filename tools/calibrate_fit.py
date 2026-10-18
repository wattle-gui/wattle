#!/usr/bin/env python3
# calibrate_fit.py -- DESKTOP tool. Turns the "RAW ..." lines printed by calibrate_touch.py into the six touch numbers
# for the board file (TOUCH_CAL / TOUCH_CAL_PORTRAIT in board_cyd.py):
#       x = a*rx + b*ry + c        y = d*rx + e*ry + f
#
#   mpremote connect /dev/ttyUSB0 run calibrate_touch.py > raw.txt     (tap the four crosses)
#   python3 calibrate_fit.py raw.txt
# (or paste the four RAW lines on the keyboard and finish with Ctrl-D:  python3 calibrate_fit.py)
import re, sys

text = open(sys.argv[1]).read() if len(sys.argv) > 1 else sys.stdin.read()
pts = []
for line in text.splitlines():
    m = re.match(r"\s*RAW\s+\S+\s+(\d+)\s+(\d+)\s+(\d+)\s+(\d+)", line)
    if m:
        pts.append(tuple(int(v) for v in m.groups()))      # target x, target y, raw x, raw y
if len(pts) < 3:
    sys.exit("need at least 3 RAW lines (calibrate_touch.py prints four)")


def solve3(A, b):
    M = [A[i][:] + [b[i]] for i in range(3)]
    for i in range(3):
        p = max(range(i, 3), key=lambda r: abs(M[r][i]))
        M[i], M[p] = M[p], M[i]
        for r in range(3):
            if r != i:
                f = M[r][i] / M[i][i]
                M[r] = [M[r][k] - f * M[i][k] for k in range(4)]
    return [M[i][3] / M[i][i] for i in range(3)]


def fit(which):                        # which = 0: screen x, 1: screen y
    A = [[0.0] * 3 for _ in range(3)]
    b = [0.0] * 3
    for tx, ty, rx, ry in pts:
        row = (rx, ry, 1)
        t = (tx, ty)[which]
        for i in range(3):
            b[i] += row[i] * t
            for j in range(3):
                A[i][j] += row[i] * row[j]
    return solve3(A, b)


a, b, c = fit(0)
d, e, f = fit(1)
cal = tuple(round(v, 6) for v in (a, b, c, d, e, f))
print("Fitted from %d points. Check (target -> calculated):" % len(pts))
worst = 0
for tx, ty, rx, ry in pts:
    px, py = a * rx + b * ry + c, d * rx + e * ry + f
    worst = max(worst, abs(px - tx), abs(py - ty))
    print("  (%3d,%3d) -> (%6.1f,%6.1f)" % (tx, ty, px, py))
print("largest error: %.1f pixels%s" % (worst, "" if worst < 5 else "   <-- too large: tap more carefully and repeat"))
print()
print("Put this in board_cyd.py (TOUCH_CAL for landscape, TOUCH_CAL_PORTRAIT for portrait):")
print("    %r" % (cal,))
