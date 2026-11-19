# Complicated.py -- the script for the design Complicated.json (four screens, 320 x 240, landscape).
#
#   Screen_1  a clock (date, hour:minute, seconds), a bar chart of the week's temperatures and a gauge that shows their average.
#             The button gets new temperatures.
#   Screen_2  the same clock, a moving "MAIN POWER" trace, and a bar that shows how high the last value is.
#   Screen_3  SETTINGS: an alarm switch, "Log to memo", a choice of what the trace shows, an alarm limit (slider),
#             and the screen brightness (stepper).
#   Screen_4  LOG / ABOUT: the memo is the log; "Rename" opens the keyboard and renames the dashboard (kept over a restart).
#
# The list at the left of every screen (a "tree") switches screens. "Quit" blanks the screen and ends the script.
import math
import random
from Runtime import *

timezone(10)                      # hours from UTC for the clock: 10 = Sydney standard time. Change it for your place.

DAYS = ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")
MONTHS = ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")

# What the trace on Screen_2 can show: name -> (title, lowest, highest, middle, swing)
TRACES = {
    "Voltage": ("MAIN VOLTAGE", 216, 264, 240, 20),
    "Current": ("MAIN CURRENT", 0, 20, 10, 8),
    "Power": ("MAIN POWER", 0, 5000, 2500, 2000),
}
trace = "Power"                   # which trace is showing now
phase = 0.0                       # the moving trace
current = "Screen_1"              # the screen that is showing


# ---------------------------------------------------------------- the log (the memo on Screen_4)

def log(text):
    """Add a line to the memo, but only while "Log to memo" is ticked. The memo keeps its last 8 lines."""
    if not checkbox1.value:
        return
    lines = (memo1.text.split("\n") if memo1.text else []) + [text]
    memo1.text = "\n".join(lines[-8:])


# ---------------------------------------------------------------- the screens and the list on them

def go(name):
    """Show a screen and mark it in its own list."""
    global current
    current = name
    Screen(name)
    log("Screen: " + name)


def chosen(path):
    """A list item was tapped on any screen. The lines of dashes do nothing."""
    if path in ("Screen_1", "Screen_2", "Screen_3", "Screen_4"):
        if path != current:
            go(path)
    elif path == "Quit":
        if message("Quit?", "Yes", "No") == "Yes":
            quit()                         # blanks the screen and ends the script
    # whatever happened, the list shows the screen we are on
    tree1.selected = tree2.selected = tree3.selected = tree4.selected = current


def tree1_selected(path):
    chosen(path)

def tree2_selected(path):
    chosen(path)

def tree3_selected(path):
    chosen(path)

def tree4_selected(path):
    chosen(path)


# ---------------------------------------------------------------- Screen_1: clock, bar chart, gauge

shown_date = shown_hm = shown_sec = ""      # what the clock labels show now: a label is only set when its text really changes


def clock():
    """Called every second. The seconds change every time; the hour:minute only once a minute; the date only once a day."""
    global shown_date, shown_hm, shown_sec
    t = now()
    sec = ":%02d" % t[5]
    if sec != shown_sec:
        shown_sec = sec
        Seconds1.text = Seconds2.text = sec
    hm = "%02d:%02d" % (t[3], t[4])
    if hm != shown_hm:
        shown_hm = hm
        HourMinute1.text = HourMinute2.text = hm
    date = "%s %02d %s %d" % (DAYS[t[6]], t[2], MONTHS[t[1] - 1], t[0])
    if date != shown_date:
        shown_date = date
        Date1.text = Date2.text = date


def average():
    values = barchart1.values
    return sum(values) / len(values)


def new_temperatures():
    barchart1.values = [random.randint(15, 30) for _ in range(5)]
    gauge1.value = average()


def button1_click():
    new_temperatures()
    log("New temperatures, average %.1f" % average())
    if switch1.value and max(barchart1.values) > slider1.value:
        message("Alarm! A day is above %d" % slider1.value, "OK")


# ---------------------------------------------------------------- Screen_2: the moving trace

def show_trace():
    """Apply the choice made on Screen_3 (what the trace shows)."""
    global trace
    trace = TRACES_ORDER[choice1.selected]
    title, low, high, middle, swing = TRACES[trace]
    waveform2.min = low
    waveform2.max = high
    waveform2.title = title
    waveform2.clear()

TRACES_ORDER = ("Voltage", "Current", "Power")          # the same order as the items of choice1


def sample():
    """Called ten times a second: the next point of the trace, and the bar under it."""
    global phase
    if current != "Screen_2":      # nobody is looking at the trace: save the effort
        return
    phase += 0.15
    title, low, high, middle, swing = TRACES[trace]
    value = middle + swing * (0.6 * math.sin(phase) + 0.3 * math.sin(phase * 2.7)) + random.randint(-100, 100) * swing / 1500
    value = min(high, max(low, value))
    waveform2.add(value)
    progressbar1.value = int(100 * (value - low) / (high - low))


# ---------------------------------------------------------------- Screen_3: settings

def switch1_changed(value):
    log("Alarm " + ("on" if value else "off"))


def checkbox1_changed(value):
    if value:
        log("Log to memo: on")


def choice1_changed(index):
    show_trace()
    log("Trace: " + trace)


def slider1_changed(value):
    log("Alarm limit: %d" % value)


def stepper1_changed(value):
    backlight(value)
    BrightnessLabel1.text = "Brightness: %d" % value
    log("Brightness: %d" % value)


# ---------------------------------------------------------------- Screen_4: log and about

def button2_click():
    keyboard1.show()               # Enter puts the text in CustomTitle1 (the keyboard's target), then keyboard1_enter() runs


def keyboard1_enter(text):
    save("title", text)            # kept over a restart
    log("Renamed: " + text)


# ---------------------------------------------------------------- start

tree1.selected = "Screen_1"       # each list marks its own screen
tree2.selected = "Screen_2"
tree3.selected = "Screen_3"
tree4.selected = "Screen_4"
CustomTitle1.text = load("title", "My Dashboard")
BrightnessLabel1.text = "Brightness: %d" % stepper1.value
backlight(stepper1.value)
show_trace()
new_temperatures()
import gc
gc.collect()                      # Wi-Fi needs a big free block of memory; this tidies the memory first
try:
    if wifi() and ntp():          # the clock needs the real time: Wi-Fi once, then the radio is off again
        wifi_off()
except Exception as e:            # no Wi-Fi, or not enough memory: the dashboard still runs, the clock may be wrong
    print("clock: Wi-Fi did not start:", e)
clock()
every(1000, clock)
every(100, sample)
run()
