# lib.py -- helpers to write test designs in the designer's JSON format.
# Used only to GENERATE the tests/NN.json files; the JSON files are the real tests.
import copy, json, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
import picker

_common = {"visible": True, "enabled": True}
_text = {"font_type": "default", "font_size": "default", "bold": False, "italic": False}

TEMPLATES = {
    "label": dict(_common, background="black", color="white", border={"color": "black", "width": 0},
                  text="Label", alignment="left", **_text),
    "button": dict(_common, background="green", color="white", border={"color": "black", "width": 1},
                   text="Button", alignment="center", accepts_input=False, events=["click"], **_text),
    "memo": dict(_common, background="white", color="black", border={"color": "#ffaa00", "width": 2},
                 text="", alignment="left", accepts_input=True, events=[], **_text),
    "switch": dict(_common, background="transparent", color="white", text="Switch", value=False,
                   events=["changed"], **_text),
    "checkbox": dict(_common, background="transparent", color="white", text="Checkbox", value=False,
                     events=["changed"], **_text),
    "slider": dict(_common, background="gray", color="green", min=0, max=100, value=50, step=1,
                   events=["changed"]),
    "progressbar": {"visible": True, "background": "gray", "color": "green", "max": 100, "value": 40},
    "image": dict(_common, background="gray", source="", scale="fit", transparent=True, events=[]),
    "line": {"visible": True, "color": "white", "thickness": 2},
    "choice": dict(_common, style="radio", orientation="vertical", items=["Item 1", "Item 2", "Item 3"],
                   selected=0, background="black", color="white",
                   border={"color": "gray", "width": 1}, events=["changed"], **_text),
    "tree": dict(_common, items=[], selected="", background="black", color="white",
                 border={"color": "gray", "width": 1}, events=["selected"], **_text),
    "gauge": {"visible": True, "background": "gray", "color": "red", "min": 0, "max": 100, "value": 0, "text": "",
              "show_value": True, "ticks": 10, "diameter": 0, "sweep": 270, "show_ticks": True, "font_size": "default"},
    "stepper": dict(_common, background="transparent", color="green", min=0, max=100, value=0, step=1,
                    events=["changed"], **_text),
    "waveform": {"visible": True, "background": "black", "color": "green", "min": 0, "max": 100, "points": 60,
                 "style": "line", "grid": True, "title": "", "update_ms": 50, "font_size": "default"},
    "barchart": {"visible": True, "background": "black", "color": "green", "min": 0, "max": 100, "bars": 5, "grid": True,
                 "title": "", "labels": [], "values": [], "show_values": False, "update_ms": 0, "font_size": "default"},
    "keyboard": dict(_common, background="gray", color="black", border={"color": "black", "width": 1},
                     layout="full", target="", secret=False, max_length=0, input_event=False,
                     hide_on_enter=True, linefeed=False, events=[]),
}


def widget(kind, id, x, y, w, h, **kw):
    d = {"widget": kind, "id": id, "x": x, "y": y, "w": w, "h": h}
    d.update(copy.deepcopy(TEMPLATES[kind]))
    d.update(kw)
    return d


def screen(id, widgets, background="black"):
    return {"id": id, "orientation": "landscape", "width": 320, "height": 240,
            "background": background, "widgets": widgets}


def save(num, name, screens):
    """Writes tests/NN.json (with the picker's CYD target block)."""
    cat = picker.load_catalogue()
    target = picker.preset_target(cat, picker.boards(cat)["board_cyd"])
    design = {"app": {"name": name, "purpose": "test %02d" % num, "version": "1.0", "version_date": ""},
              "target": target, "screens": screens}
    path = os.path.join(HERE, "%02d.json" % num)
    with open(path, "w") as f:
        json.dump(design, f, indent=2)
        f.write("\n")
    return path
