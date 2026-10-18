# Wattle — Technical Reference (version 0.9, for the CYD)

A JSON-driven touch GUI for the ESP32 "CYD" (ESP32 + 2.8" ILI9341 display + XPT2046 resistive touch), in MicroPython.
You draw screens in the **Editor**, save them as a **design file** (JSON), and write a small **script** that says what
the application does. A **Runtime** on the board draws the design and calls your script.

This is the technical reference. The *Quick Guide* and the *User Manual* (folder `manual/`) are the friendlier
introductions; every property of every widget is also listed in `MASTER_schema.json`.

*Last updated: 2026-10-07 (tests 00–25, E20–E23 pass on the CYD).*

---

## 1. The pieces

| Piece | What it is | Where it runs |
|---|---|---|
| **Design file** (`*.json`) | Screens and widgets: position, size, colours, text, which events each widget reports. Written by the Editor. | read by the board |
| **`Runtime.py`** (or `Runtime.mpy`) | The engine: loads the design, draws every widget, detects touches, calls your handlers. No application logic. | board |
| **Your script** (`Project_1.py`) | The application: handler functions, nothing else. Ends with `run()`. | board |
| **`main.py`** | Starts the project at power-up (`PROJECT = "Project_1"`). | board |
| **Board profile** (`board_cyd.py`) + drivers | Pins, rotation, touch calibration; `ili9341.py` (display), `touch_xpt2046.py` (touch). | board |
| **Desktop tools** | `deploy.py`, `check_script.py`, `picker.py`, `make_fonts.py`, `make_images.py`, `make_mpy.py`, `reset.sh`, `calibrate_touch.py` / `calibrate_fit.py`, `tests/run_test.py`. | computer |

### Files on the board

```
main.py  Project_1.py  design.txt  <design>.json
Runtime.mpy (or Runtime.py)  ili9341.mpy (or .py)  board_cyd.py  touch_xpt2046.py
fonts/<name>_<size>.fnt ...      <image id>.raw ...      data_<name>.json ... (saved settings)
fonts/dejavusansmono_12.fnt  (the 12 px font of the on-screen error messages; without it they use the 8 px font)
```

> A `.py` file on the board always wins over a `.mpy` of the same name. If you change `Runtime.py`, delete
> `Runtime.mpy` (or rebuild it with `make_mpy.py`).

`design.txt` has one or two lines: line 1 = the design file to load, line 2 = the board profile (optional, default
`board_cyd`). If `design.txt` is missing the runtime falls back to the constant `JSON_FILE` in `Runtime.py`.

---

## 2. The design file

```json
{
  "app":    { "name": "...", "purpose": "...", "version": "1.0", "version_date": "" },
  "target": { "model": "...", "processor": "...", "board": "board_cyd",
              "display": {...}, "touch": {...}, "fonts": [ {"name": "Arial", "sizes": [12,16,20,24,32], "styles": [...]} ] },
  "screens": [
    { "id": "main", "orientation": "landscape", "width": 320, "height": 240, "background": "black",
      "widgets": [
        { "widget": "button", "id": "button1", "x": 168, "y": 64, "w": 120, "h": 40,
          "visible": true, "enabled": true, "background": "green", "color": "white",
          "border": { "color": "black", "width": 1 },
          "text": "Button1", "alignment": "center",
          "font_type": "default", "font_size": "default", "bold": false, "italic": false,
          "events": ["click"] }
      ] }
  ]
}
```

- **`target`** is written by `picker.py` (hardware and the fonts the board can draw). The runtime only reads
  `target.board`; the Editor reads `target.fonts` to offer font names and sizes.
- **Ids** are unique across the whole design: every screen and every widget has its own, and no two are equal.
- **Colours:** a name (`black white red green blue yellow cyan magenta gray`, any case) or `"#rrggbb"`. The background of
  label, button, memo, switch, checkbox, choice and tree may also be `"transparent"` (the screen colour); sliders, progress bars and images may not.
- **Common properties:** `x y w h visible enabled background color border{color,width} font_type font_size bold italic`
  (labels, buttons and memos also `text` and `alignment`: `left`, `center`, `right`).
- Every widget type, with every property and its allowed values: `MASTER_schema.json`. A complete example with real
  values: `MASTER.json`; the same with empty values: `MASTER_blank.json`.

### Widget types

`label` `button` `memo` `switch` `checkbox` `slider` `progressbar` `image` `line` `keyboard` `choice` `tree`
`gauge` `stepper` `waveform` `barchart` (section 12)
(the *Widget Reference* chapter of the manual describes each one).

### Several screens

One JSON holds all screens. The **first** one is shown at start-up. All screens of one design must have the **same size
and orientation**. `Screen("settings")` in the script clears the display and draws that screen. Only the showing screen
is drawn and touchable; a property set on a widget of a hidden screen is stored and drawn when that screen is next shown
(copying values between screens is the script's job).

### Orientation

The Editor writes a portrait screen as `"orientation": "portrait"`, `"width": 240`, `"height": 320`. The runtime takes the
size from the first screen and the board profile picks the display rotation from its shape (`height > width` = portrait).
In `board_cyd.py`: `PORTRAIT_ROTATION` (0 or 180; 180 = USB socket at the bottom) and `TOUCH_CAL_PORTRAIT`.

---

## 3. Events and handlers

A handler is a function named `<widget id>_<event>`; the runtime finds it in your script and calls it.

| Widget | Event name (in `events`) | Handler | Argument |
|---|---|---|---|
| label, memo, button, image | `click` | `button1_click()` | none |
| label, memo, button, image | `longpress` | `button1_longpress()` | none (held about 0.7 s: `Runtime.LONG_PRESS_MS`) |
| switch, checkbox | `changed` | `switch1_changed(value)` | `True` / `False` |
| slider | `changed` (on release) | `slider1_changed(value)` | integer |
| slider (optional, while dragging) | — | `slider1_changing(value)` | integer |
| choice (radio, dropdown) | `changed` | `choice1_changed(index)` | item number, 0 = first |
| tree | `selected` | `tree1_selected(path)` | `"Network/WiFi"` |
| keyboard | `enter` | `keyboard1_enter(text)` | the text |
| keyboard (if `input_event`) | — | `keyboard1_input(text)` | text so far, after every key |

**What the `events` list means**

- **switch, checkbox, slider, choice, tree** react to touch whenever they are `enabled`. Their `events` list only decides
  whether your script is *told*; without the event they still work on the screen and can be read from the script
  (`switch1.value`, `choice1.selected`, `tree1.selected`).
- **button, label, memo, image** are tappable only if `"click"` is in their `events`. (A tap on them changes nothing by itself.)
**Caution.** On a resistive panel such as the CYD's, the contact flickers under a steady finger, so a hold is not as reliable as a tap: now and then a hold is taken for a tap, or needs a second try. Use it only for convenience actions, never for something that is dangerous or hard to undo, and always offer a normal way to do the same thing (a second button, a confirmation with `message()`). If a widget lists both `click` and `longpress`, a short tap gives the click and a hold gives only the long press.
- **keyboard** widgets never catch taps on the normal screen; **progressbar** and **line** are never touchable.
- `enabled: false` ignores taps; `visible: false` hides the widget (it is erased, and what was behind it is redrawn).

---

## 4. The script API (`from Runtime import *`)

```python
from Runtime import *

def button1_click():
    button1.background = "red"        # any property: same name as in the JSON; redraws at once
    label1.text = "Tapped"

run()                                  # always the last line
```

- **Every widget is a name** in your script (also those of hidden screens). Its properties are attributes, lower-case,
  same as the JSON: `label1.text`, `slider1.value = 40`, `choice1.selected = 2`, `tree1.selected = "Network/WiFi"`
  (this also opens the branches above it), `choice1.items`. Setting one redraws the widget.
- **`run(module=None, poll_ms=150)`** — the event loop; never returns. `poll_ms` = how often the screen is checked for a touch.
- **`Screen("id")`** — show another screen.
- **`every(ms, function)`** / **`stop(function)`** — periodic tasks (see section 7).
- **`set_poll_ms(ms)`** — change the touch interval while running.
- **`set_longpress_ms(ms)`** — how long a touch must last to count as a long press (default 700).
- **`backlight(percent=None)`** — brightness 0–100 (returns the current value if called without argument); 0 blanks the screen.
  **`screensaver(seconds, dim=0)`** — after `seconds` without a touch the backlight goes to `dim` percent (0 = off); `screensaver(0)` switches it off.
  A touch that wakes the screen is not a click. **`power_button(True)`** — the BOOT button blanks / wakes the screen.
- **`wifi(timeout=15)`** → `True` when connected: the network name and password are read from the sealed file `wifi.dat` on the board (made by `wifi_setup.py`; older boards: `ID.dat` line 5 = name,
  line 6 = password; never printed). **`wifi_ip()`**, **`wifi_off()`**, **`ntp()`** (sets the clock from the internet),
  **`timezone(hours)`**, **`now()`** (local time tuple). Do not use Wi-Fi together with `LOW_POWER`.
  **`locality()`** → `(town, state, country, timezone_hours)` from `ID.dat` lines 7–10, or `None` if not set; the timezone
  hours are applied automatically at import (no `timezone()` call needed), the other three are for a human reading the
  file, not used by the Runtime. Daylight saving isn't automatic either way — update line 10 (or call `timezone()`)
  when the season changes.
- **`keyboard1.show()`** — open the keyboard (section 5); returns the text or `None`.
- **`message(text, "Yes", "No")`** — a pop-up box the user must answer; returns the label of the tapped button (default `"OK"`;
  any number of buttons that fit). It takes over the screen like the keyboard (timers pause), long text is wrapped (and shown smaller
  if it needs more than four lines), and the box is removed and what was under it restored afterwards. Taps outside the box do nothing.
- **`save(name, data)`** / **`load(name, default=None)`** — settings that survive a restart: `data` (numbers, text, `True`/`False`, lists,
  dictionaries) is stored in the file `data_<name>.json` on the board; `load` returns it, or `default` if nothing was saved (or the file
  is damaged). `name` may contain letters, digits and `_`. Flash memory wears out: save when something changed, not every second.
- **`fatal(exception)`** — used by `main.py` to show an error that stopped the script from starting.
- **`get_event()`** / **`wait_event(timeout_ms=None, poll_ms=150)`** — for scripts that want their own loop; they return
  `(widget_id, event, value)` tuples (or `None`). `redraw_widget(widget_id)` redraws after you changed `widgets[id][key]` directly.
- **`widgets`** — the raw widget dictionaries by id; **`widget_objs`** — the widget objects by id (useful with a string id).
- Settings you may change in the script: `Runtime.LOW_POWER`, `Runtime.LOW_POWER_GRACE_MS`.


### Mistakes in your script (the error screen)

An exception in a handler or in a periodic task is printed on the serial port **and** drawn on the display (dark red): the title
`SCRIPT ERROR` (centred), where it happened (`in handler button1_click`, `in periodic task tick (stopped)`), the error and its message,
and the place in your file in words (`File Project_1.py, line 7, in button1_click`), all in white, in the 12 px font if
`fonts/dejavusansmono_12.fnt` is on the board (else 8 px), broken at spaces. A tap continues (the other widgets still work); a failing timer is
stopped. A **syntax error**, or any error while the script is being loaded, is caught by `main.py` and shown the same way:
the line number goes at the end of the message (`SyntaxError: invalid syntax (line 3)`), `in file Project_1.py`, and the footer
`RUN CHECK_SCRIPT.PY ON THE PC`; the screen stays until the board is reset. (A `NameError` shows just the missing name.) `Ctrl-C` still works (only ordinary exceptions are caught).
MicroPython's own syntax messages are always just `invalid syntax`; `check_script.py` gives the real cause (section 10).

---

## 5. Keyboards

The keyboard widget is **not drawn with the screen**. `keyboard1.show()` takes over the whole screen (the widget's own
`x y w h` are ignored), shows a temporary memo on top and the keys below, and when it closes the screen is restored.

- **`layout`: `"full"`** — memo of 5 lines with a scroll bar (tap its top or bottom end to move one line, its middle to jump); keys `1–0`, `Q–P`, `A–L`, `Z–M`,
  `Bksp`, `Space`, `Esc`, `Enter`, and `LF` if `linefeed` is true.
- **`layout`: `"numeric"`** — a 2-line memo and a 4 × 4 keypad (keys 80 × 48 px on the 320 × 240 screen): `1 2 3 <-` / `4 5 6 Esc` / `7 8 9 OK` / `- 0 .`
  Only one `.` is accepted (a leading `.` becomes `0.`); `-` only as the first character; `OK` is ignored while the text is only `-`.
- `target` — the id of a widget that receives the text on Enter (empty = none). `show()` returns the text, or `None` after Esc.
- `secret` — the memo shows `*`. `max_length` — 0 = no limit. `input_event` — calls `<id>_input(text)` after every key.
- `hide_on_enter`: `true` (default) — Enter closes the keyboard. `false` — Enter *sends* the text (target updated,
  `<id>_enter(text)` called), clears the memo and the keyboard stays open until Esc; `show()` then returns the last text sent.
- The memo **always starts empty**; keep earlier values in your script (e.g. `memo1.text`).
- Periodic tasks pause while the keyboard (or an open dropdown) is on the screen.

---

## 6. choice and tree

**choice** (`"widget": "choice"`): `style` `"radio"` or `"dropdown"`; `orientation` `"vertical"`/`"horizontal"` (radio only);
`items` (list of texts); `selected` (number of the chosen item; 0 = first = default; -1 = none); `events` `["changed"]`.
The chosen item is marked in the text colour (radio: a filled dot; dropdown: an inverted row).
- *radio*: the widget area is divided equally between the items; a tap redraws only the two items that change.
- *dropdown*: the widget height is the height of the closed field **and** of every row of the list. The list opens over the
  other widgets (below the field, above it if there is no room), starts at the first item, shows as many rows as fit and has
  a scroll bar when needed; a tap outside cancels. The widgets under the list are redrawn when it closes.

**tree** (`"widget": "tree"`), a menu of up to **3 levels**: `items` is nested, `[{"text": "Display", "items": [{"text": "Brightness"}]},
{"text": "About"}]` (items have no ids); `selected` is the text path of the last end item chosen (`"Display/Brightness"`);
`events` `["selected"]`. Row height = character height + 12 px; each level indents 3 characters; `+`/`-` mark closed/open
parents; all branches start closed. Tapping a parent opens/closes it (no event); tapping an end item selects it
(inverted row) and sends its path. A scroll bar appears when the rows do not fit. The open/closed state is kept by the
runtime, not in the JSON.


**Scroll bars** (the tree, the drop-down list and the keyboard's memo all use the same one): a tap on the top or bottom
fifth of the bar moves one row up or down; a tap in the middle three fifths **jumps** to that place in the list (the start of the
middle zone is the very start of the list, its end the very end).

---

## 7. Time, power and speed

- **Periodic tasks:** `every(1000, tick)` calls `tick()` every second, without any touch; `stop(tick)` cancels it. Tasks run
  inside the event loop, so they never overlap handlers. A slow task only makes the next call late; an error inside a task
  is printed and the loop goes on. Registering the same function again changes its period.
- **Touch interval:** touch is **polled**, not interrupt-driven (`Pin.irq()` does not fire on this board's touch pin; a
  `machine.Timer` interrupt does work). `run(poll_ms=150)`: longer = less power, slower response (a tap is noticed within
  `poll_ms`). It is independent of the `every()` periods.

| `poll_ms` | feels like | use it for |
|---|---|---|
| 50 – 100 | very snappy | games, sliders, fast typing (more current) |
| 150 (default) | normal | most applications |
| 250 – 400 | slightly slow | settings screens, menus |
| 600 – 1500 | slow; quick taps may be lost | rarely touched, battery-powered panels |

Measured by hand on the CYD (test 19), pressing as fast as possible for 5 seconds per setting (rough, one run):

| `poll_ms` | 50 | 100 | 150 | 250 | 400 | 600 | 1000 |
|---|---|---|---|---|---|---|---|
| hits recognised | 5 | 7 | 3 | 4 | 2 | 3 | 1 |

Below about 250 ms the limit is the finger and the time the board needs to process each tap (about a tenth of a second);
there is little gain below ~100 ms, while above ~250 ms quick taps start to be lost.

- **`LOW_POWER`** (`Runtime.LOW_POWER = True` in the script, or the constant in `Runtime.py`): the processor sleeps between
  checks (`lightsleep`). It starts sleeping `LOW_POWER_GRACE_MS` (10 s) after start-up, so a computer can still connect after
  a reset. A sleeping board **cannot be stopped with Ctrl-C**: reset it (`./reset.sh`, or `tests/run_test.py`, which resets
  the board and sends Ctrl-C while it boots).
- **Speed:** start-up measured on the CYD: 5.0 s → 1.7 s (the first screen draws in about 0.3 s) by precompiling
  `Runtime.py` and `ili9341.py` (`make_mpy.py`; the board's MicroPython version and the compiler must match: MicroPython 1.24 →
  mpy-cross 1.24.1), keeping the fonts in a `fonts/` folder, a compiled letter-drawing loop, and bigger fill blocks in the display driver.

---

## 8. Fonts and pictures

**Text.** Each widget has `font_type`, `font_size`, `bold`, `italic`; text is drawn inside the border plus 1 px and is cut at the
pixel when it is too wide. The designer should warn when text does not fit.

- **Built-in font** (`font_type` `"default"`): an 8 × 8 bitmap font enlarged 1×, 2×, 3× (`font_size` 8, 16, 24; `"default"` = 8);
  character width 8 × scale (9 bold, 10 italic), height 8 × scale, line spacing 8 × scale + 2.
- **Typefaces** (Arial, Times New Roman, Comic Sans MS, DejaVu Sans / Sans Mono / Serif): anti-aliased bitmap fonts made on the
  computer by `make_fonts.py` (from the TrueType fonts installed on Linux; Arial = Liberation Sans, Times New Roman = Liberation
  Serif, Comic Sans MS = Comic Relief) in sizes 10, 12, 14, 16, 20, 24, 32, each with regular / bold / italic / bold-italic.
  A file is `fonts/<name>_<size>[b][i].fnt` on the board (name = lower-case letters and digits of the font name). The runtime
  loads the file with the nearest size; **if no file exists it falls back silently to the built-in font**.
  `python3 make_fonts.py` creates the files (and the catalogue entries in `hardware/`); `python3 make_fonts.py --upload design.json`
  copies only the files that design uses (all of them together are 2.4 MB).
- **Characters:** the typeface fonts cover ASCII 32–126; any other character is shown as `?`. The built-in font draws ASCII only.

**Pictures.** The board cannot decode JPEG or PNG. `python3 make_images.py design.json upload` converts every image widget into
`<widget id>.raw` (RGB565, exactly *w* × *h*) and copies it to the board. `scale`: `fit` (keeps the shape, empty space around),
`fill` (covers the box, crops), `stretch` (distorts). `transparent: true` paints the empty space in the screen colour, `false` in the
widget's own background. A missing `.raw` file shows an empty box.

---

## 9. Hardware: board profile and drivers

`Runtime.py` contains no pins or chip names. The board is chosen by `target.board` in the design, else line 2 of `design.txt`,
else `board_cyd`. A profile `board_<name>.py` provides `NAME`, `make_display(width, height)` and `make_touch(width, height)`
(`board_template.py` explains each).

- **Display object:** `fill_rectangle`, `block`, `clear`, `draw_line`, `draw_circle`/`fill_circle`, `draw_image`, `draw_text8x8` — the
  `ili9341.Display` class provides them all.
- **Touch object:** `pressed()` (True while touched; called often) and `read()` → `(x, y)` in *screen pixels*, or `None`.
- **CYD:** `board_cyd.py` holds the pins, the SPI buses, the rotation (landscape 90; portrait `PORTRAIT_ROTATION`) and the touch
  calibration (`TOUCH_CAL`, `TOUCH_CAL_PORTRAIT`: x = a·rx + b·ry + c, y = d·rx + e·ry + f from the raw readings).
- **Calibrating a resistive panel** (a new orientation or board): copy `calibrate_touch.py` to the board and run
  `mpremote run calibrate_touch.py`; tap the four crosses (TL, TR, BL, BR); it prints `RAW name x y rx ry`; fit the six numbers by least
  squares over the four points and put them in the board file (on the CYD the fit was within 0.7 px of the targets).
- **`picker.py`** (PyQt6) lists the hardware in `hardware/*.json` (processors, displays, touch chips, fonts, boards) and writes
  the design's `target` block (it keeps a `.bak` copy and can also write `design.txt`). Add entries by adding JSON files.

---

## 10. Tools and tests

| Tool | Purpose |
|---|---|
| `picker.py` | choose the hardware and fonts; writes the `target` block |
| `make_fonts.py` | TrueType → `.fnt` files; `--upload design.json` copies the ones a design uses |
| `make_images.py design.json [upload]` | pictures → `.raw` files |
| `make_mpy.py` | precompile `Runtime.py`, `ili9341.py` and copy them to the board |
| `reset.sh` | hard reset over USB (works on a sleeping board) |
| `calibrate_touch.py` | touch calibration (runs on the board) |
| `tests/compare_json.py A B` | lists every difference between two design files (also types and key order) |
| `tests/run_test.py N` | loads test *N* onto the board: cleans it, uploads design, script, fonts and pictures, restarts |
| `deploy.py design.json script.py` | stops the board, copies design + script + `design.txt` (+ the fonts and pictures the design uses), **checks the copies on the board**, and starts the board only if there are no errors (`--no-check` skips the check) |
| `check_script.py` | reads the design and the script **from the board** and checks them: Python syntax (with the real cause and a ^ under the spot), widget names that are not in the design (`lable1`), misspelt properties (`label1.txt`), handlers that match no widget or event, can never be called (event not in `events`) or take the wrong number of arguments, values of the wrong kind (`label1.text = 5`), code after `run()`. Restarts the board afterwards. It takes no file names. |
| `calibrate_fit.py raw.txt` | turns the four `RAW` lines of `calibrate_touch.py` into the six touch numbers |
| `boardlink.py` | helper of the tools: stop, restart, read and write files on the board |

The serial port is `/dev/ttyUSB0` unless the environment variable `ESP_PORT` says otherwise (Windows: `set ESP_PORT=COM5`).

**Test suite** (`tests/`): each test has `NN.json` (the design), `NN.py` (a short, commented script — these are the manual's
examples) and `NN.txt` (what to look at and what counts as a pass). `tests/RESULTS.md` logs the results per board; re-run the whole
list for every new board. `tests/E20…E23` are designs built in the Editor. Tests 23–27 cover the error screen, pop-ups, saving and the start-up errors. All tests pass on the CYD.

---

## 11. Known limitations

- All screens of a design must have the same size and orientation.
- Touch is polled (interrupts do not work on this board's touch pin); a tap is noticed within `poll_ms`.
- Keyboards and an open dropdown take over the loop: periodic tasks pause meanwhile.
- A tree has at most 3 levels and no ids; a choice cannot be given a default other than the first item in the design file
  (set `selected` from the script).
- `make_fonts.py` can only *create* fonts on a computer that has the TrueType files at the paths it knows (Linux); the
  `.fnt` files themselves are portable.
- Touch calibration is for resistive panels; a capacitive panel needs a different touch driver.

---

## 12. gauge, stepper, waveform, barchart

Four widgets added to the twelve of section 2 (the exact JSON of each is in `NEW_WIDGETS_SPEC.md`; every property in `MASTER_schema.json`).

- **gauge** (display only): a round dial. The scale starts at `min` at the lower left and ends with `max` after `sweep` degrees (default 270);
  `ticks` intervals, `diameter` in pixels (0 = fits the box). `gauge1.value = 40` redraws only the needle area (about 70-100 ms).
- **stepper**: `-` number `+`; `step`, `min`, `max`; event `changed(value)`.
- **waveform** (display only): a moving trace. `waveform1.add(v)`, `waveform1.clear()`; `points` values are kept; `style` `line` or `bars`;
  `update_ms` = shortest time between redraws (values that arrive sooner are drawn with the next redraw).
- **barchart** (display only): a stationary chart. `values` and `labels` come from the design; script: `barchart1.set(i, v)`, `.values = [..]`,
  `.clear()`.
- Drawing: charts and the gauge are drawn in bands of 12 rows into a `framebuf` and sent with one `block()` call each (a waveform of 40 bars
  takes about 50 ms). While a chart is drawn the board does nothing else; a very small `update_ms` makes taps and timers late.
- Colour names known to the Runtime: black, white, red, green, blue, yellow, cyan, magenta, gray/grey, orange, purple, pink, brown; or `#RRGGBB`.
