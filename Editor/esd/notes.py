"""On-screen notes for every component and property. Not written into the design JSON."""

from __future__ import annotations

from esd.catalogue import spec_for

_DEFAULT = "Select a component to see what it does.\nDrag it onto the screen to place it."

COMPONENTS = {
    "design": (
        "The design holds the screens and the target board. "
        "Name, purpose, and version describe the program. "
        "The target fields are filled in by the board picker."
    ),
    "screen": (
        "One screen of the program. Width and height are the size the device draws. "
        "Orientation follows that size."
    ),
    "button": (
        "A button the user can touch. The face shows Text. "
        "Tick click so the script runs when it is pressed."
    ),
    "label": "Text drawn on the screen. A label is not touched.",
    "memo": (
        "Several lines of text. It can be touched. "
        "Tick click so the script runs when it is pressed."
    ),
    "keyboard": (
        "Keys that type into the Target widget. Press Call to try it here. "
        "Tick enter so the script runs when Enter is pressed."
    ),
    "switch": "On or off, with a caption. Tick changed so the script runs when it is flipped.",
    "checkbox": "A tick box with a caption. Tick changed so the script runs when it is flipped.",
    "choice": (
        "One item chosen from a list, shown as radio buttons or a dropdown. "
        "Tick changed so the script runs when the choice changes."
    ),
    "tree": (
        "Groups and items. Touching an end item selects it. "
        "Tick selected so the script receives the path, such as Network/WiFi."
    ),
    "slider": (
        "A slider the user drags between the lowest and highest value. "
        "changed runs when it is released. changing runs while it is dragged."
    ),
    "progressbar": (
        "A bar that fills up to the highest value. It is not touched. "
        "The script sets the value."
    ),
    "image": "A picture from a file. Tick click so the script runs when it is pressed.",
    "line": (
        "A straight line. It is not touched. "
        "Width and height are the line's span, and either one may be 0."
    ),
    "gauge": (
        "A round dial with a needle. It is not touched. "
        "The script moves the needle with gauge1.value. "
        "The scale starts at the lower left, runs clockwise over the top, and is centred on the top."
    ),
    "stepper": (
        "A minus button, a number, and a plus button. One tap adds or subtracts Step. "
        "Tick changed so the script runs with the new value. "
        "The buttons work even if changed is not ticked."
    ),
    "waveform": (
        "A moving trace, like a slow oscilloscope. It is not touched and starts empty. "
        "The script adds numbers with waveform1.add. "
        "The curve in the editor is only a sample and is not saved."
    ),
    "barchart": (
        "A stationary chart of vertical bars. It is not touched. "
        "Type the bar heights and the text under them here, or change them from the script. "
        "An empty chart shows sample bars in the editor. Those bars are not saved."
    ),
}

PROPERTIES = {
    "id": "The name used in the script. Letters, digits, and underscore. It must be unique.",
    "events": "Tick an event to call it from the script. Leave them all off and the widget still works.",
    "x": "Distance from the left of the screen, in pixels.",
    "y": "Distance from the top of the screen, in pixels.",
    "w": "Width in pixels.",
    "h": "Height in pixels.",
    "visible": "When off, the widget is hidden on the device.",
    "enabled": "When off, a touch widget is shown dimmed and does not respond.",
    "background": "Fill colour behind the widget.",
    "color": "The main colour of this widget.",
    "border": "Outline colour and thickness. A width of 0 draws no outline.",
    "text": "The words shown on the widget.",
    "font_type": "The typeface. Default is the built-in font.",
    "font_size": "Default, or 8, 16, or 24. Gauge, waveform, and bar chart use only the built-in font.",
    "alignment": "Where the text sits: left, center, or right.",
    "bold": "Draw the text bold, when the chosen font allows it.",
    "italic": "Draw the text italic, when the chosen font allows it.",
    "accepts_input": "When on, a keyboard can type into this widget.",
    "layout": "Full is the letter keyboard. Numeric is the number pad.",
    "target": "The id of the widget the keyboard types into.",
    "secret": "When on, the keyboard hides the characters, as for a password.",
    "max_length": "The most characters the keyboard will accept. 0 means no limit.",
    "input_event": "When on, the script is told about each key, not only Enter.",
    "hide_on_enter": "When on, the keyboard hides after Enter.",
    "linefeed": "When on, the full keyboard has a key that starts a new line.",
    "value": "The value shown when the screen opens. The script can change it later.",
    "style": "Picks one of the ways this widget can be drawn.",
    "orientation": "vertical stacks the choices. horizontal lays them in a row.",
    "items": "The choices, one on each line. Indent a tree by two spaces for each level.",
    "selected": "Which item starts selected. 0 is the first. For a tree, this is a path such as Network/WiFi.",
    "min": "Lowest value. It must be smaller than the highest value.",
    "max": "Highest value. It must be larger than the lowest value.",
    "step": "How much one tap, or one slider movement, adds or subtracts.",
    "source": "Path of the picture file.",
    "scale": "fit keeps the shape inside the box. fill covers the box. stretch uses the whole box.",
    "transparent": "When on, the picture's empty areas let the screen show through.",
    "thickness": "How thick the line is, in pixels.",
    "show_value": "When on, the number is drawn inside the dial.",
    "show_ticks": "When on, the marks are drawn around the scale.",
    "points": "How many values are kept across the width. The oldest drops off the left.",
    "grid": "When on, three faint horizontal lines are drawn.",
    "title": "Words at the top left. Leave this empty for none.",
    "app.name": "Name of the program.",
    "app.purpose": "What the program is for.",
    "app.version": "Version text, such as 1.0.",
    "app.version_date": "The date of this version.",
    "width": "Screen width in pixels.",
    "height": "Screen height in pixels.",
}

BY_TYPE = {
    "gauge": {
        "background": "Colour of the ring.",
        "color": "Colour of the needle and the marks.",
        "min": "Value at the first mark, on the lower left.",
        "max": "Value at the last mark, on the lower right. It must be greater than the lowest value.",
        "value": "Where the needle starts. The script can change it. A value outside the scale is kept, with a warning.",
        "text": "Caption under the number. Leave this empty for none.",
        "ticks": "Number of intervals between the marks. 10 gives 11 marks.",
        "diameter": "Circle size in pixels. 0 draws the largest circle that fits the box. 1 to 19 are refused.",
        "sweep": "Angle of the whole scale, in degrees. 270 is three quarters of a circle. 180 is a half circle.",
        "font_size": "Size of the number and the caption. Default, or 8, 16, or 24.",
    },
    "stepper": {
        "background": "Colour behind the number. transparent leaves the screen showing through.",
        "color": "Colour of the minus button and the plus button.",
        "min": "The value stops here. It must be smaller than the highest value.",
        "max": "The value stops here. It must be greater than the lowest value.",
        "value": "The number shown at the start. It must lie between the lowest and highest value.",
        "step": "Amount added or subtracted by one tap. It must be greater than 0.",
        "font_size": "Size of the number. Default, or one of the sizes of the chosen font.",
    },
    "waveform": {
        "background": "Colour behind the trace.",
        "color": "Colour of the line, or of the bars.",
        "min": "Bottom of the trace. It must be smaller than the highest value.",
        "max": "Top of the trace. It must be greater than the lowest value.",
        "style": "line joins the values. bars draws one vertical bar for each value.",
        "title": "Words at the top left. Leave this empty for none.",
        "update_ms": (
            "Shortest time in milliseconds between two redraws. 0 redraws on every value. "
            "Very small values can make the rest of the program slow."
        ),
        "font_size": "Size of the title. Default, or 8, 16, or 24.",
    },
    "barchart": {
        "background": "Colour behind the bars.",
        "color": "Colour of the bars.",
        "min": "The bottom of every bar. It must be smaller than the highest value.",
        "max": "The top of the chart. It must be greater than the lowest value.",
        "bars": (
            "How many bars there are, from 1 to 64. The starting default of 5 is not a limit. "
            "Labels and Values below have one row per bar. "
            "Lowering this keeps the extra rows, with a warning, instead of deleting them."
        ),
        "title": "Words at the top left. Leave this empty for none.",
        "labels": "Text under each bar, from left to right, one row per bar. Leave a row empty for no label on that bar.",
        "values": "Height of each bar, from left to right. A missing entry counts as the lowest value. Leave the list empty for an empty chart.",
        "show_values": "When on, each number is printed above its bar.",
        "update_ms": (
            "Shortest time in milliseconds between two redraws. 0 redraws on every change. "
            "Very small values can make the rest of the program slow."
        ),
        "font_size": "Size of the title, the text under the bars, and the numbers. Default, or 8, 16, or 24.",
    },
    "slider": {
        "min": "Lowest value of the slider.",
        "max": "Highest value of the slider.",
        "value": "Where the slider starts. It must lie between the lowest and highest value.",
        "color": "Colour of the slider knob.",
        "background": "Colour of the slider track.",
    },
    "progressbar": {
        "max": "The value that fills the bar.",
        "value": "How full the bar is at the start, from 0 up to the highest value.",
        "color": "Colour of the filled part.",
        "background": "Colour of the empty part.",
    },
    "choice": {
        "style": "radio shows every option. dropdown shows the chosen one, and opens the list when touched.",
        "items": "One choice on each line.",
        "selected": "0 is the first choice. -1 means none.",
    },
    "line": {
        "color": "Colour of the line.",
        "w": "Horizontal span. 0 is allowed when the height is not 0.",
        "h": "Vertical span. 0 is allowed when the width is not 0.",
    },
    "keyboard": {
        "x": "Stored with the design. The device places the keyboard, so these numbers are not its touch area.",
        "y": "Stored with the design. The device places the keyboard, so these numbers are not its touch area.",
        "w": "Stored with the design. The device places the keyboard, so these numbers are not its touch area.",
        "h": "Stored with the design. The device places the keyboard, so these numbers are not its touch area.",
    },
    "screen": {
        "id": "Name of this screen.",
        "orientation": "landscape is wider than tall. portrait is taller than wide.",
        "background": "Colour of the screen behind the widgets.",
    },
}


def component_note(kind: str | None) -> str:
    if not kind:
        return _DEFAULT
    text = COMPONENTS.get(str(kind))
    if text:
        return text
    return _DEFAULT


def property_note(key: str | None, kind: str | None = None) -> str:
    if not key:
        return component_note(kind)
    name = str(key)
    widget = str(kind or "")
    if name.startswith("target."):
        return "Filled in by the board picker. It cannot be edited here."
    typed = (BY_TYPE.get(widget) or {}).get(name)
    if typed:
        return typed
    if name == "events":
        lines = [f"{ev}: {desc}" for ev, desc in (spec_for(widget).get("events") or [])]
        if lines:
            return "Tick an event to call it from the script.\n" + "\n".join(lines)
        return "This widget has no events."
    text = PROPERTIES.get(name)
    if text:
        return text
    return component_note(kind)
