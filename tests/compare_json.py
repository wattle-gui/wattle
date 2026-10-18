#!/usr/bin/env python3
# compare_json.py A.json B.json -- lists every difference between two designs, widget by widget:
# missing / extra properties, changed values, changed TYPES (e.g. 16 vs "16"), and key order.
# Used to check that the Editor writes the same JSON that the runtime expects.
import json, sys

def walk(a, b, path, out):
    if type(a) != type(b):
        out.append("%s: type %s -> %s  (%r -> %r)" % (path, type(a).__name__, type(b).__name__, a, b))
        return
    if isinstance(a, dict):
        for k in a:
            if k not in b:
                out.append("%s.%s: MISSING in second file (was %r)" % (path, k, a[k]))
        for k in b:
            if k not in a:
                out.append("%s.%s: EXTRA in second file (%r)" % (path, k, b[k]))
        for k in a:
            if k in b:
                walk(a[k], b[k], path + "." + k, out)
        if [k for k in a if k in b] != [k for k in b if k in a]:
            out.append("%s: same keys, different ORDER (harmless)" % path)
    elif isinstance(a, list):
        if len(a) != len(b):
            out.append("%s: list length %d -> %d" % (path, len(a), len(b)))
        for i in range(min(len(a), len(b))):
            walk(a[i], b[i], "%s[%d]" % (path, i), out)
    elif a != b:
        out.append("%s: %r -> %r" % (path, a, b))

def label(d):
    # name widgets by id so messages are readable
    for s in d.get("screens", []):
        s["__n"] = s.get("id")
    return d

a = json.load(open(sys.argv[1]))
b = json.load(open(sys.argv[2]))
out = []
walk(a, b, "design", out)
# readable widget ids in the messages
ids = [w.get("id") for s in a["screens"] for w in s["widgets"]]
print("first file : %d screens, %d widgets" % (len(a["screens"]), len(ids)))
print("second file: %d screens, %d widgets" % (len(b["screens"]), sum(len(s["widgets"]) for s in b["screens"])))
if not out:
    print("IDENTICAL (same keys, values, types and order)")
else:
    print("%d difference(s):" % len(out))
    for line in out:
        print(" -", line)
