#!/usr/bin/env python3
# check_script.py -- DESKTOP tool: checks the design and the script that are ON THE BOARD, and tells you in plain
# language what is wrong, before (or after) MicroPython complains with "invalid syntax".
#
#   python3 check_script.py          reads design.txt, main.py, the design and the script from the board, checks them,
#                                    and restarts the board when it is done
#
# It looks for: Python syntax errors (with Python's own precise message); widget names that are not in the design;
# misspelt property names (label1.txt); handlers that do not match any widget or event, that can never be called
# (the event is not in the widget's "events" list) or that take the wrong number of arguments; values of an obviously
# wrong kind (label1.text = 5); code after run() that never runs.
import ast, builtins, difflib, json, re, sys

API = {"Screen", "every", "stop", "set_poll_ms", "set_longpress_ms", "message", "save", "load", "fatal", "run", "get_event", "wait_event",
       "widgets", "widget_objs", "backlight", "screensaver", "power_button", "wifi", "wifi_ip", "wifi_off", "ntp",
       "timezone", "now"}
METHODS = {"keyboard": {"show"}, "waveform": {"add", "clear"}, "barchart": {"set", "clear", "add"}}   # functions of a widget, not properties
EVENT_WIDGETS = {"click": ("label", "button", "memo", "image"), "longpress": ("label", "button", "memo", "image"), "changed": ("switch", "checkbox", "slider", "choice", "stepper"),
                 "changing": ("slider",), "selected": ("tree",), "enter": ("keyboard",), "input": ("keyboard",)}
NEEDS_LISTED = ("click", "longpress", "changed", "selected", "enter")        # must be in the widget's "events" list
ARGS = {"click": 0, "longpress": 0, "changed": 1, "changing": 1, "selected": 1, "enter": 1, "input": 1}


def suggest(word, options):
    m = difflib.get_close_matches(word, sorted(options), n=1, cutoff=0.6)
    return " (did you mean '%s'?)" % m[0] if m else ""


def analyse(design, script, script_name="Project_1.py"):
    """Returns a list of (severity, line, message); severity is 'ERROR' or 'WARNING'."""
    out = []

    def add(sev, node_or_line, msg):
        line = node_or_line if isinstance(node_or_line, int) else getattr(node_or_line, "lineno", 0)
        out.append((sev, line, msg))

    # ---- 1. Python syntax (CPython's parser: much more precise than MicroPython's "invalid syntax")
    try:
        tree = ast.parse(script, "<script on the board>")
    except SyntaxError as e:
        lines = script.split("\n")
        where = lines[e.lineno - 1] if e.lineno and e.lineno <= len(lines) else ""
        detail = e.msg
        if where:
            detail += "\n        %s\n        %s^" % (where.strip(), " " * max(0, (e.offset or 1) - 1 - (len(where) - len(where.lstrip()))))
        add("ERROR", e.lineno or 0, "syntax error: " + detail)
        return out

    widgets = {}
    for scr in design.get("screens", []):
        for w in scr.get("widgets", []):
            widgets[w["id"]] = w

    # ---- names the script binds, and how Runtime is imported
    bound = set(dir(builtins))
    star = False
    aliases = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            bound.add(node.name)
            a = node.args
            for arg in a.posonlyargs + a.args + a.kwonlyargs + ([a.vararg] if a.vararg else []) + ([a.kwarg] if a.kwarg else []):
                bound.add(arg.arg)
        elif isinstance(node, ast.ClassDef):
            bound.add(node.name)
        elif isinstance(node, ast.Name) and isinstance(node.ctx, (ast.Store, ast.Del)):
            bound.add(node.id)
        elif isinstance(node, ast.ExceptHandler) and node.name:
            bound.add(node.name)
        elif isinstance(node, (ast.Global, ast.Nonlocal)):
            bound.update(node.names)
        elif isinstance(node, ast.Import):
            for al in node.names:
                bound.add(al.asname or al.name.split(".")[0])
                if al.name == "Runtime":
                    aliases.add(al.asname or "Runtime")
        elif isinstance(node, ast.ImportFrom):
            for al in node.names:
                if al.name == "*":
                    if node.module == "Runtime":
                        star = True
                else:
                    bound.add(al.asname or al.name)
    if star:
        bound |= API | set(widgets)
    if not star and not aliases:
        add("WARNING", 1, "the script does not import the Runtime (add 'from Runtime import *' at the top)")

    def widget_of(expr):
        """The design widget an expression stands for (label1, or gui.label1 with 'import Runtime as gui'), or None."""
        if isinstance(expr, ast.Name) and star and expr.id in widgets:
            return expr.id
        if isinstance(expr, ast.Attribute) and isinstance(expr.value, ast.Name) and expr.value.id in aliases \
                and expr.attr in widgets:
            return expr.attr
        return None

    # ---- 2. names that are never defined anywhere (a NameError waiting to happen)
    reported = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load) and node.id not in bound and node.id not in reported:
            reported.add(node.id)
            hint = suggest(node.id, set(widgets) | API) if (star or aliases) else ""
            add("ERROR", node, "name '%s' is not defined%s" % (node.id, hint))

    # ---- 3. properties of widgets: spelling and kind of value
    for node in ast.walk(tree):
        if isinstance(node, ast.Attribute):
            wid = widget_of(node.value)
            if wid is None:
                continue
            w = widgets[wid]
            prop = node.attr.lower()
            allowed = set(w) | METHODS.get(w["widget"], set())
            if prop not in allowed:
                add("ERROR", node, "%s is a %s and has no property '%s'%s" %
                    (wid, w["widget"], node.attr, suggest(prop, allowed)))
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign) and isinstance(node.value, ast.Constant):
            for tgt in node.targets:
                if isinstance(tgt, ast.Attribute) and widget_of(tgt.value):
                    w = widgets[widget_of(tgt.value)]
                    prop = tgt.attr.lower()
                    if prop not in w:
                        continue
                    old, new = w[prop], node.value.value
                    if isinstance(old, bool):
                        ok = isinstance(new, bool)
                    elif isinstance(old, (int, float)):
                        ok = isinstance(new, (int, float)) and not isinstance(new, bool)
                    elif isinstance(old, str):
                        ok = isinstance(new, str)
                    else:
                        ok = True
                    if not ok:
                        add("WARNING", node, "%s.%s is %s in the design but you assign %s (%r)%s" %
                            (widget_of(tgt.value), tgt.attr, type(old).__name__, type(new).__name__, new,
                             "; use str() to show a number" if isinstance(old, str) else ""))

    # ---- 4. handlers: <widget id>_<event>
    seen = {}
    for node in tree.body:
        if not isinstance(node, ast.FunctionDef):
            continue
        if node.name in seen:
            add("WARNING", node, "handler '%s' is defined twice (line %d and here): only the last one is used"
                % (node.name, seen[node.name]))
        seen[node.name] = node.lineno
        base, _, event = node.name.rpartition("_")
        if event not in EVENT_WIDGETS or not base:
            continue
        if base not in widgets:
            add("ERROR", node, "handler '%s': there is no widget '%s' in the design%s" %
                (node.name, base, suggest(base, set(widgets))))
            continue
        w = widgets[base]
        if w["widget"] not in EVENT_WIDGETS[event]:
            kinds = [e for e, ws in EVENT_WIDGETS.items() if w["widget"] in ws]
            add("ERROR", node, "handler '%s': a %s never sends '%s' (it sends: %s)" %
                (node.name, w["widget"], event, ", ".join(kinds) or "nothing"))
            continue
        if event in NEEDS_LISTED and event not in w.get("events", []):
            add("ERROR", node, "handler '%s' will never be called: '%s' is not in the events list of %s in the design"
                % (node.name, event, base))
        if event == "input" and not w.get("input_event"):
            wrote = any(isinstance(n, ast.Attribute) and n.attr == "input_event" for n in ast.walk(tree))
            if not wrote:
                add("WARNING", node, "handler '%s' is only called if input_event is true for %s" % (node.name, base))
        a = node.args
        n_args = len(a.posonlyargs) + len(a.args) - len(a.defaults)
        if not a.vararg and n_args != ARGS[event]:
            add("ERROR", node, "handler '%s' must take %d argument(s) (it takes %d)%s" %
                (node.name, ARGS[event], n_args, "" if ARGS[event] == 0 else ": def %s(value):" % node.name))

    # ---- 5. run() should be the last statement
    for i, node in enumerate(tree.body):
        if isinstance(node, ast.Expr) and isinstance(node.value, ast.Call) and \
                getattr(node.value.func, "id", getattr(node.value.func, "attr", "")) == "run":
            if i < len(tree.body) - 1:
                add("WARNING", tree.body[i + 1], "this code comes after run() and will never run: put run() last")
            break

    out.sort(key=lambda t: (t[1], t[0]))
    return out


def report(problems, design_name, script_name):
    print("Checked: design %s, script %s (both read from the board)" % (design_name, script_name))
    if not problems:
        print("No problems found.")
        return 0
    errors = sum(1 for p in problems if p[0] == "ERROR")
    for sev, line, msg in problems:
        print("  %-7s %s line %d: %s" % (sev, script_name, line, msg))
    print("%d error(s), %d warning(s)." % (errors, len(problems) - errors))
    return 1 if errors else 0


def read_from_board():
    """(design_name, design_dict, script_name, script_text) from the board; exits with a message if something is missing."""
    import boardlink
    dt = boardlink.cat("design.txt")
    if dt is None:
        sys.exit("design.txt is not on the board: it names the design to load.")
    design_name = dt.split("\n")[0].strip()
    main = boardlink.cat("main.py") or ""
    m = re.search(r'PROJECT\s*=\s*["\']([^"\']+)["\']', main)
    script_name = (m.group(1) if m else "Project_1") + ".py"
    dtext = boardlink.cat(design_name)
    if dtext is None:
        sys.exit("the design '%s' named in design.txt is not on the board." % design_name)
    try:
        design = json.loads(dtext)
    except ValueError as e:
        sys.exit("the design '%s' on the board is not valid JSON: %s" % (design_name, e))
    script = boardlink.cat(script_name)
    if script is None and boardlink.cat("demo.py") is not None:        # main.py starts the demo when there is no script of your own
        script_name = "demo.py"
        script = boardlink.cat(script_name)
    if script is None:
        sys.exit("the script '%s' (named in main.py) is not on the board." % script_name)
    return design_name, design, script_name, script


def check_board(restart=True, halt=True):
    """Stops the board (unless halt=False: already stopped), reads its files and checks them. Returns 1 if there
    are errors, else 0. Restarts the board afterwards if restart=True."""
    import boardlink
    if halt:
        boardlink.halt()
    try:
        design_name, design, script_name, script = read_from_board()
        code = report(analyse(design, script, script_name), design_name, script_name)
    finally:
        if restart:
            boardlink.restart()
    return code


if __name__ == "__main__":
    sys.exit(check_board())
