# Runtime.py (browser flavour) -- a Wattle Runtime whose screen is a WEB PAGE. Runs ON THE BOARD, no display.
# It offers a script the same names as Runtime.py: the widgets as global variables (label1, button1 ...), Screen(), every(), run(),
# backlight(), waveform.add(); and it calls the handlers the script defines (button1_click ...).
# The board serves the page (webui.html), the design (design.json) and a live event stream (Server-Sent Events: one long connection,
# the board pushes every change); a tap in the browser comes back as  POST /ev?id=button1&e=click .
# main.py makes this module answer to  import Runtime  (sys.modules), so the script itself needs no change.
import binascii
import gc
import hashlib
import json
import machine
import os
import socket
import sys
import time

import wnet

SCRIPT = "demo"                     # the script's module name: its handlers are looked up there
DESIGN = "design.json"
UI = "webui.html"

_w = {}                             # widget id -> its properties (the design, with the script's changes written in)
_over = {}                          # widget id -> {property: value} the script changed (the browser needs only these)
_data = {}                          # waveform id -> list of values added so far
_pend = {}                          # (id, property) -> value, waiting to be sent
_adds = []                          # (id, value) waveform points waiting to be sent
_clr = []                           # waveform ids that were emptied
_ph = []                            # phone commands waiting to be sent: [name, argument ...]
_pin = None                         # the PIN / password from pin.dat (None: no lock)
_keys = []                          # keys given out after a correct PIN (gone when the board restarts)
_nonces = []                        # challenges given out and not yet used
_fails = 0                          # wrong answers in a row
_lock_until = 0                     # ticks_ms until which no answer is accepted
_scr = None                         # a screen change waiting to be sent
_clients = []                       # open event streams
_cwid = {}                          # id(stream) -> the id of the browser on it (each browser keeps its own, so devices can be told apart)
_seen = {}                          # browser id -> (width, height, pixel ratio) it last reported
_joined = {}                        # browser id -> the code it was added with (the Editor's "Add a device": QR address or the Add button)
_offer = ""                         # while the Editor waits for a new device it offers a code: every page then shows "Add this device?"
_offer_until = 0
_timers = []                        # [ms, function, last run]
_act = [0]                          # ticks_ms of the last page visit or touch (autosleep counts from here)
_auto = None                        # autosleep(): (awake ms, sleep s, wake_pin, level, touch pin)
_pin_h = []                         # on_pin(): (handler, flag, pin)
_cur = None
_req = 0
_dlg = None                         # the dialog open in the browsers (keyboard or message), or None
_NOANSWER = object()
_answer = _NOANSWER
_waiting = None                     # id the script waits for while a dialog is open

with open(DESIGN) as _f:
    _design = json.load(_f)
_cur = _design["screens"][0]["id"]
for _s in _design["screens"]:
    for _x in _s["widgets"]:
        _w[_x["id"]] = _x


class Widget:

    def __init__(self, widget_id):
        object.__setattr__(self, "_id", widget_id)

    def __getattr__(self, name):
        data = _w[self._id]
        key = name.lower()
        if key in data:
            return data[key]
        raise AttributeError(name)

    def __setattr__(self, name, value):
        key = name.lower()
        _w[self._id][key] = value
        _over.setdefault(self._id, {})[key] = value
        _pend[(self._id, key)] = value

    def add(self, value):
        """waveform only: appends a value (the oldest drops out when it is full)."""
        n = _w[self._id].get("points", 40)
        d = _data.setdefault(self._id, [])
        d.append(value)
        if len(d) > n:
            del d[0]
        _adds.append((self._id, value))

    def show(self):
        """keyboard only: opens the keyboard in the browser and waits for Enter (returns the text) or Cancel (None)."""
        k = _w[self._id]
        return _dialog(self._id, {"kb": self._id, "secret": bool(k.get("secret")), "max": k.get("max_length", 0),
                                  "numeric": k.get("layout") == "numeric"})

    def clear(self):
        """waveform / barchart: empties the chart (a barchart: all bars to min)."""
        data = _w[self._id]
        if data.get("widget") == "waveform":
            _data[self._id] = []
            _clr.append(self._id)
        else:
            self.values = [data.get("min", 0)] * len(data.get("values", []))

    def set(self, index, value):
        """barchart only: sets bar number `index` (0 = the first)."""
        v = list(_w[self._id].get("values", []))
        v[index] = value
        self.values = v


for _i in _w:
    globals()[_i] = Widget(_i)


def Screen(name):
    global _cur, _scr
    _cur = name
    _scr = name


def every(ms, function):
    _timers.append([ms, function, time.ticks_ms()])


def stop(function):
    """Stops a task started with every()."""
    for t in _timers:
        if t[1] is function:
            _timers.remove(t)
            return


# ---------------------------------------------------------------- the clock (the same names as the CYD Runtime)
# The ESP32 has no battery clock: its time is wrong after each start until ntp() sets it. The board's Wi-Fi stays on (the phone needs it).

_tz = 0                             # hours from UTC used by now()


def ntp():
    """Sets the clock from the internet (pool.ntp.org). Returns True if it worked."""
    try:
        import ntptime
        ntptime.settime()
        return True
    except Exception as e:
        wnet.log("ntp: %r" % (e,))
        return False


def timezone(hours):
    """Hours from UTC used by now() (10 = Sydney standard time; the script handles summer time)."""
    global _tz
    _tz = hours


def now():
    """The local time (see timezone()): (year, month, day, hour, minute, second, weekday, yearday)."""
    return time.localtime(time.time() + int(_tz * 3600))


class _Phone:
    """The viewer's phone (or any browser): sounds, buzz, speech, and its screen size. Every open page obeys; the page asks for one tap first."""
    width = 0                       # the browser window right now (bars come and go, so this changes)
    height = 0
    dpr = 1.0
    screen_width = 0                # the device's real screen (does not change with bars or keyboards)
    screen_height = 0

    @property
    def landscape(self):
        return self.width > self.height

    def vibrate(self, ms=200):
        _ph.append(["vibrate", ms])

    def beep(self, freq=880, ms=300):
        _ph.append(["beep", freq, ms])

    def speak(self, text):
        _ph.append(["speak", str(text)])

    def stay_awake(self, on=True):
        _ph.append(["awake", bool(on)])

    _fs = None                  # None: the script did not say; the page then goes full screen by itself on a touch screen

    def fullscreen(self, on=True):
        self._fs = bool(on)
        _ph.append(["full", bool(on)])


phone = _Phone()


class _Board:
    """This board, for scripts that want to show it: board.name, board.ip, board.free (memory, bytes), board.rssi (Wi-Fi signal, dBm)."""
    name = wnet.NAME

    @property
    def ip(self):
        return wnet.sta.ifconfig()[0]

    @property
    def free(self):
        gc.collect()
        return gc.mem_free()

    @property
    def rssi(self):
        try:
            return wnet.sta.status("rssi")
        except Exception:
            return 0


board = _Board()


def backlight(level):
    pass                            # a browser has no backlight


def _dialog(wait_id, dlg):
    global _dlg, _answer, _waiting
    _dlg = dlg
    _pend[("_dlg", "x")] = dlg
    _answer = _NOANSWER
    _waiting = wait_id
    while _answer is _NOANSWER:
        _step()
    _waiting = None
    _dlg = None
    _pend[("_dlg", "x")] = None
    return _answer


def message(text, *buttons):
    """Shows a pop-up box with the text and one button per label (default "OK"); waits and returns the tapped label."""
    return _dialog("_msg", {"msg": text, "btns": list(buttons) or ["OK"]})


# ---------------------------------------------------------------- sending to the browsers

def _drop(c):
    try:
        c.close()
    except OSError:
        pass
    if c in _clients:
        _clients.remove(c)
    _cwid.pop(id(c), None)


def _send_all(text):
    b = text.encode()
    for c in _clients[:]:
        try:
            c.write(b)
        except OSError:
            _drop(c)


def _set_offer(code):
    global _offer, _offer_until
    changed = code != _offer
    if changed and code:
        _joined.clear()                                          # a new registration starts clean
    _offer = code
    _offer_until = time.ticks_add(time.ticks_ms(), 300000)       # an offer lapses after 5 minutes
    if changed and _clients:
        _send_all("data: " + json.dumps({"jn": code}) + "\n\n")


def _flush():
    global _scr
    if _offer and time.ticks_diff(time.ticks_ms(), _offer_until) > 0:
        _set_offer("")
    if _clients and (_pend or _adds or _scr or _clr or _ph):
        msg = {"s": _scr, "set": [[k[0], k[1], v] for k, v in _pend.items()], "add": _adds, "clr": _clr, "ph": _ph}
        _send_all("data: " + json.dumps(msg) + "\n\n")
    _pend.clear()
    del _adds[:]
    del _clr[:]
    del _ph[:]
    _scr = None


def _full(c):
    a, d = os.stat(UI), os.stat(DESIGN)
    msg = {"full": 1, "s": _cur, "over": _over, "data": _data, "dlg": _dlg, "fs": phone._fs, "jn": _offer, "ui": "%d-%d-%d-%d" % (a[6], a[8], d[6], d[8])}
    c.write(("data: " + json.dumps(msg) + "\n\n").encode())


# ---------------------------------------------------------------- deep sleep, saving, pins
# After a deep sleep the ESP32 starts again from the top (main.py, then the script): variables are gone, so keep what matters with
# save() / load(). The pages show "asleep" meanwhile and join again by themselves when the board is back.

def _data_file(name):
    return "data_" + "".join(c for c in str(name) if c.isalpha() or c.isdigit() or c == "_") + ".json"


def save(name, data):
    """Stores data (numbers, text, True/False, lists, dictionaries) in the file data_<name>.json on the board.
    Flash memory wears out after very many writes: save when something really changed, not every second."""
    with open(_data_file(name), "w") as f:
        json.dump(data, f)


def load(name, default=None):
    """Returns what save(name, ...) stored, or `default` if nothing was saved yet (or the file is damaged)."""
    try:
        with open(_data_file(name)) as f:
            return json.load(f)
    except (OSError, ValueError):
        return default


def woke_by():
    """Why the script is running: "timer", "touch" (a touch pad), "pin" (a wake pin), "other" (a wake the board did not name),
    or "power" (power-on or reset: not a wake from deep sleep)."""
    if machine.reset_cause() != machine.DEEPSLEEP_RESET:
        return "power"
    w = machine.wake_reason()
    if w == getattr(machine, "TIMER_WAKE", -1):
        return "timer"
    if w == getattr(machine, "TOUCHPAD_WAKE", -1):
        return "touch"
    if w in (getattr(machine, "EXT0_WAKE", -1), getattr(machine, "EXT1_WAKE", -1), getattr(machine, "PIN_WAKE", -1)):
        return "pin"
    return "other"


def deepsleep(seconds=0, wake_pin=None, level=1, touch=None):
    """Tells the open pages, then puts the ESP32 into deep sleep. It wakes after `seconds` (0: only a wake pin or touch wakes it),
    when `wake_pin` (a pin number, or a list of them) goes high (level=1) or low (level=0), or when the touch pad `touch` (a pin
    number such as 32) is touched. The script then starts again from the top: see woke_by(), save(), load().
    A touch pad that cannot sense a touch on this board is not used; if nothing else could wake the board it does NOT sleep."""
    import esp32
    if touch is not None:
        pad = machine.TouchPad(machine.Pin(touch))               # untouched value now; a touch lowers it: wake at four fifths of it
        base = sum(pad.read() for _ in range(8)) // 8
        if base < 150:                                           # a pin with something else on it reads about 0 and can never wake the board
            wnet.log("touch pad %d reads %d untouched: it cannot sense a touch on this board, so it is not used" % (touch, base))
            touch = None
        else:
            pad.config(base * 4 // 5)
            wnet.log("touch pad %d: untouched %d, wakes below %d" % (touch, base, base * 4 // 5))
    if not seconds and wake_pin is None and touch is None:
        wnet.log("not sleeping: nothing could wake the board again")
        return
    if touch is not None:
        esp32.wake_on_touch(True)
    if wake_pin is not None:
        pins = [machine.Pin(p, machine.Pin.IN) for p in (wake_pin if isinstance(wake_pin, (list, tuple)) else [wake_pin])]
        how = esp32.WAKEUP_ANY_HIGH if level else esp32.WAKEUP_ALL_LOW
        if len(pins) == 1:
            esp32.wake_on_ext0(pins[0], how)
        else:
            esp32.wake_on_ext1(pins, how)
    _send_all("data: " + json.dumps({"zz": int(seconds)}) + "\n\n")
    time.sleep_ms(400)                                           # let the pages receive it
    for c in _clients[:]:
        _drop(c)
    try:                                                         # for the quick Wi-Fi join after the wake (see wnet.connect)
        machine.RTC().memory(json.dumps({"s": wnet.SSID, "n": list(wnet.sta.ifconfig()), "t": int(seconds)}))
    except Exception:
        pass
    wnet.log("deep sleep %d s" % seconds)
    if seconds:
        machine.deepsleep(int(seconds * 1000))
    machine.deepsleep()


def autosleep(awake, sleep=0, wake_pin=None, level=1, touch=None):
    """Stay awake `awake` seconds after the last page visit or touch, then deepsleep(sleep, ...). autosleep(0) switches it off."""
    global _auto
    _auto = (awake * 1000, sleep, wake_pin, level, touch) if awake else None
    _act[0] = time.ticks_ms()


def on_pin(pin, edge, handler, pull=None):
    """Calls handler() when the pin changes: edge is "rising", "falling" or "both". The handler runs in the normal loop, so it may
    change widgets (a plain MicroPython interrupt may not). pull: machine.Pin.PULL_UP or PULL_DOWN for a bare button."""
    flag = bytearray(1)
    p = machine.Pin(pin, machine.Pin.IN, pull)
    trig = {"rising": machine.Pin.IRQ_RISING, "falling": machine.Pin.IRQ_FALLING}.get(edge, machine.Pin.IRQ_RISING | machine.Pin.IRQ_FALLING)
    p.irq(lambda _p: flag.__setitem__(0, 1), trig)
    _pin_h.append((handler, flag, p))


# ---------------------------------------------------------------- the lock (PIN / password)
# pin.dat holds the PIN sealed (wattle pin). With a PIN set, the page `/` and the two /auth routes are open and everything else needs a key.
# The PIN never travels: the board hands out a random number n, the page answers sha256(n + ":" + PIN), and a correct answer earns a random key.
# Three wrong answers in a row lock the answering for 30 s, the next ones for twice as long each time (up to about 32 min).
# This keeps out guests and curious neighbours. It does not hide the traffic from someone who can read your Wi-Fi (the page is plain http).

def _load_pin():
    global _pin
    try:
        line = open("pin.dat").read().split("\n")[0]
    except OSError:
        return
    import wifi_cipher
    _pin = wifi_cipher.unseal(line)
    if _pin is None:                                 # pin.dat is there but unreadable: stay locked, never open
        _pin = binascii.hexlify(os.urandom(8)).decode()
        wnet.log("pin.dat unreadable: locked until wattle pin is run again")


def _rand(n):
    return binascii.hexlify(os.urandom(n)).decode()


def _reply(c, code, body=b"", kind=b"text/plain"):
    c.write(b"HTTP/1.0 " + code + b"\r\nContent-Type: " + kind + b"\r\nContent-Length: " + str(len(body)).encode() +
            b"\r\nCache-Control: no-store\r\nConnection: close\r\n\r\n" + body)


def _auth(c, path, q):
    """/auth/nonce (GET): a challenge.  /auth (POST n=..&r=..): the answer; replies with the key or says why not."""
    global _fails, _lock_until
    now = time.ticks_ms()
    if path == "/auth/nonce":
        n = _rand(8)
        _nonces.append(n)
        if len(_nonces) > 4:
            del _nonces[0]
        _reply(c, b"200 OK", json.dumps({"n": n, "lock": _pin is not None}).encode(), b"application/json")
        return
    wait = time.ticks_diff(_lock_until, now)
    if wait > 0:
        _reply(c, b"429 Too Many Requests", str(wait // 1000 + 1).encode())
        return
    n = q.get("n", "")
    if _pin is None or n not in _nonces:
        _reply(c, b"403 Forbidden", b"expired")
        return
    _nonces.remove(n)
    want = binascii.hexlify(hashlib.sha256((n + ":" + _pin).encode()).digest()).decode()
    got = q.get("r", "")
    diff = len(want) ^ len(got)
    for a, b in zip(want, got):
        diff |= ord(a) ^ ord(b)                      # compared without stopping at the first difference
    if diff:
        _fails += 1
        if _fails >= 3:
            _lock_until = time.ticks_add(now, 30000 << min(_fails - 3, 6))
            wnet.log("wrong PIN %d times: locked" % _fails)
        _reply(c, b"403 Forbidden", b"wrong")
        return
    _fails = 0
    k = _rand(16)
    _keys.append(k)
    if len(_keys) > 6:
        del _keys[0]
    wnet.log("PIN accepted")
    _reply(c, b"200 OK", json.dumps({"k": k}).encode(), b"application/json")


# ---------------------------------------------------------------- the web server

def _file(c, path, kind):
    n = os.stat(path)[6]
    c.write(b"HTTP/1.0 200 OK\r\nContent-Type: " + kind + b"\r\nContent-Length: " + str(n).encode() +
            b"\r\nCache-Control: no-store\r\nConnection: close\r\n\r\n")
    with open(path, "rb") as f:
        while True:
            chunk = f.read(1024)
            if not chunk:
                break
            c.write(chunk)


def _unq(s):
    s = s.replace("+", " ")
    out = bytearray()
    i = 0
    while i < len(s):
        if s[i] == "%" and i + 2 < len(s) + 0 and i + 2 <= len(s) - 1 + 0:
            out.append(int(s[i + 1:i + 3], 16))
            i += 3
        else:
            out.extend(s[i].encode())
            i += 1
    return out.decode()


def _oops(where, e, keep=False):
    """A mistake in the script: the diary gets one line, and the open pages get a pop-up (SCRIPT ERROR, where, what, and the line in your
    file), like the red screen of the CYD. keep=True (the script failed while starting): the box is shown on every page until it is fixed."""
    global _dlg
    try:
        import io
        out = io.StringIO()
        sys.print_exception(e, out)
        lines = [l.strip() for l in out.getvalue().split("\n") if l.strip()]
    except Exception:
        lines = [repr(e)]
    last = lines[-1] if lines else repr(e)
    mine = [l for l in lines if l.startswith("File") and SCRIPT + ".py" in l]
    wnet.log("%s: %s %s" % (where, last, mine[-1] if mine else ""))
    text = "SCRIPT ERROR\n" + where + "\n\n" + last
    if mine:
        text += "\n\n" + "\n".join(mine[-2:])
    if keep:
        text += "\n\nFix the script, run the check on your computer (wattle check), then deploy it again."
    dlg = {"msg": text[:700], "btns": ["OK"]}
    if keep:
        _dlg = dlg                                           # a page that opens later is shown it too (_full)
    if _dlg is None or keep:
        _pend[("_dlg", "x")] = dlg
    if _clients:
        _flush()


def _event(widget_id, event, v=None):
    """A browser event. v (text) is the new value of a switch, checkbox, slider or stepper, the item number of a choice,
    the typed text of a keyboard, or the label of a pop-up button."""
    global _answer
    if widget_id == "_phone" and event == "join":    # the Add button of the page: "code,browser id"
        a = _unq(v or "").split(",")
        if len(a) == 2 and _offer and a[0] == _offer:
            _joined[a[1][:12]] = a[0][:12]
        return
    if widget_id == "_phone":                        # the page reports its size: "width,height,pixel-ratio"
        a = _unq(v or "").split(",")
        if len(a) in (3, 4, 5, 7):
            phone.width, phone.height, phone.dpr = int(a[0]), int(a[1]), float(a[2])
            if len(a) >= 4:
                if len(_seen) > 12:                              # a browser without a stored id makes a new one at every load: do not pile up
                    for w in [w for w in _seen if w not in _cwid.values()]:
                        del _seen[w]
                phone.screen_width, phone.screen_height = (int(a[5]), int(a[6])) if len(a) == 7 else (phone.width, phone.height)
                _seen[a[3][:12]] = (phone.width, phone.height, phone.dpr, phone.screen_width, phone.screen_height)
                if len(a) >= 5 and a[4]:
                    _joined[a[3][:12]] = a[4][:12]
            handler = getattr(sys.modules.get(SCRIPT), "phone_resized", None)
            if handler:
                try:
                    handler()
                except Exception as e:
                    _oops("in handler phone_resized", e)
        return
    if widget_id == "_msg":
        _answer = _unq(v or "")
        return
    w = _w.get(widget_id)
    if w is None:
        return
    kind = w.get("widget")
    if kind == "memo":                               # typed into directly in the browser (no echo back: it would reset the cursor)
        text = _unq(v or "")
        w["text"] = text
        _over.setdefault(widget_id, {})["text"] = text
        handler = getattr(sys.modules.get(SCRIPT), widget_id + "_changed", None)
        if handler:
            try:
                handler(text)
            except Exception as e:
                _oops("in handler %s_changed" % widget_id, e)
        return
    if kind == "keyboard":
        text = _unq(v) if v is not None else None
        if _waiting == widget_id:                    # the script is waiting in keyboard.show()
            _answer = text if event == "enter" else None
            return
        if event == "enter" and text is not None:    # a keyboard placed on the screen: the text goes to its target
            t = w.get("target", "")
            if t in _w:
                setattr(globals()[t], "text", text)
            handler = getattr(sys.modules.get(SCRIPT), widget_id + "_enter", None)
            if handler:
                try:
                    handler(text)
                except Exception as e:
                    _oops("in handler %s_enter" % widget_id, e)
        return
    arg = None
    if kind == "tree":                               # v is the text path of the chosen item, e.g. "Display/Theme/Dark"
        arg = _unq(v or "")
        setattr(globals()[widget_id], "selected", arg)
        handler = getattr(sys.modules.get(SCRIPT), widget_id + "_selected", None)
        if handler:
            try:
                handler(arg)
            except Exception as e:
                _oops("in handler %s_selected" % widget_id, e)
        return
    if v is not None:
        if kind in ("switch", "checkbox"):
            arg = v == "1"
        elif "." in v:
            arg = float(v)
        else:
            arg = int(v)
        setattr(globals()[widget_id], "selected" if kind in ("choice", "tree") else "value", arg)
    module = sys.modules.get(SCRIPT)
    handler = getattr(module, widget_id + "_" + event, None) if module else None
    if handler:
        try:
            handler() if v is None else handler(arg)
        except Exception as e:
            _oops("in handler %s_%s" % (widget_id, event), e)


def _http(c):
    global _req
    keep = False
    ev = None
    try:
        c.settimeout(0.5)                            # a browser often opens a spare connection and sends nothing: do not make the board wait long for it
        line = c.recv(700).split(b"\r\n")[0].decode()
        c.settimeout(2)
        parts = line.split(" ")
        if len(parts) < 2:                           # the browser closed its spare connection without asking for anything
            return
        _req += 1
        path, _, query = parts[1].partition("?")
        q = dict(p.split("=", 1) for p in query.split("&") if "=" in p)
        if path in ("/auth", "/auth/nonce"):
            _auth(c, path, q)
        elif path == "/size":                        # the size the phone last reported (the Editor reads it); not secret, so no PIN
            _reply(c, b"200 OK", ("%d,%d,%s" % (phone.width, phone.height, phone.dpr)).encode())
        elif path == "/join":                        # the Editor offers (or withdraws, code empty) a code for adding a device
            _set_offer(q.get("code", "")[:12])
            _reply(c, b"200 OK", b"ok")
        elif path == "/info":                        # who this board is and what size its phone reported (the Editor looks for this); not secret
            _reply(c, b"200 OK", json.dumps({"wattle": 1, "name": board.name, "ip": board.ip, "width": phone.width, "height": phone.height,
                                             "dpr": phone.dpr, "free": board.free, "viewers": len(_clients),
                                             "devices": [{"id": w, "width": _seen[w][0], "height": _seen[w][1], "dpr": _seen[w][2], "join": _joined.get(w, ""),
                                                          "screen_w": _seen[w][3], "screen_h": _seen[w][4]}
                                                         for w in set(_cwid.values()) if w in _seen]}).encode())
        elif path != "/" and _pin is not None and q.get("k") not in _keys:
            _reply(c, b"401 Unauthorized")           # no key (or an old one): the page then asks for the PIN
        elif path == "/ping":
            _reply(c, b"200 OK", b"ok")
        elif path == "/events":
            c.settimeout(1)
            c.write(b"HTTP/1.0 200 OK\r\nContent-Type: text/event-stream\r\nCache-Control: no-store\r\nConnection: keep-alive\r\n\r\n")
            _full(c)
            _act[0] = time.ticks_ms()
            _clients.append(c)
            if q.get("w"):
                _cwid[id(c)] = q["w"][:12]
            if len(_clients) > 3:
                _drop(_clients[0])
            keep = True
        elif path == "/log":
            _file(c, "wattle_log.txt", b"text/plain")
        elif path.startswith("/f/pictures/") and ".." not in path:      # the design's pictures: the browser decodes them itself
            kind = {"jpg": b"image/jpeg", "jpeg": b"image/jpeg", "png": b"image/png", "gif": b"image/gif"}.get(path.rsplit(".", 1)[-1].lower())
            try:
                if kind is None:
                    raise OSError
                _file(c, path[3:], kind)
            except OSError:
                c.write(b"HTTP/1.0 404 Not Found\r\nContent-Length: 0\r\nConnection: close\r\n\r\n")
        elif path == "/design.json":
            _file(c, DESIGN, b"application/json")
        elif path == "/ev" and parts[0] == "POST":
            c.write(b"HTTP/1.0 200 OK\r\nContent-Length: 2\r\nConnection: close\r\n\r\nok")   # answer first: the handler may wait for a dialog
            if not q.get("id", "").startswith("_"):
                _act[0] = time.ticks_ms()                    # a touch counts as activity, the page's own reports do not
            ev = (q.get("id", ""), q.get("e", "click"), q.get("v"))
        elif path == "/":
            _file(c, UI, b"text/html")
        else:
            c.write(b"HTTP/1.0 404 Not Found\r\nContent-Length: 0\r\nConnection: close\r\n\r\n")
    except OSError as e:
        if not e.args or e.args[0] != 116:            # 116 = the spare connection sent nothing in time: normal, not worth a line in the diary
            wnet.log("request failed %r" % (e,))
    except ValueError:
        pass                                         # not a readable request: ignore it, keep the board running
    finally:
        if not keep:
            c.close()
    if ev:
        _event(ev[0], ev[1], ev[2])


_srv = None
_wdt = None
_t = [0, 0, 0, True]                # last flush, last heartbeat, last status line, wifi was up


def _step():
    """One turn of the server: watchdog, Wi-Fi watch, the script's timers, sending changes, one new connection."""
    _wdt.feed()
    now = time.ticks_ms()
    if not wnet.sta.isconnected():
        if _t[3]:
            wnet.log("wifi LOST")
            _t[3] = False
        try:
            wnet.sta.connect(*wnet.read_credentials())
        except Exception as e:
            wnet.log("reconnect failed %r" % (e,))
        time.sleep(2)
        return
    if not _t[3]:
        wnet.log("wifi back")
        _t[3] = True
    for t in _timers:
        if time.ticks_diff(now, t[2]) >= t[0]:
            t[2] = now
            try:
                t[1]()
            except Exception as e:
                if t in _timers:
                    _timers.remove(t)                            # a task that failed is stopped, so that it does not fail again every second
                _oops("in periodic task %s (stopped)" % getattr(t[1], "__name__", "?"), e)
                break
    for h in _pin_h:
        if h[1][0]:
            h[1][0] = 0
            try:
                h[0]()
            except Exception as e:
                _oops("in on_pin handler", e)
    if _auto is not None and time.ticks_diff(now, _act[0]) >= _auto[0]:
        a = _auto
        autosleep(0)                                             # once: if the board could not sleep (nothing to wake it), it stays awake
        deepsleep(a[1], a[2], a[3], a[4])
    if time.ticks_diff(now, _t[0]) >= 100:
        _t[0] = now
        _flush()
    if time.ticks_diff(now, _t[1]) >= 5000:
        _t[1] = now
        _send_all(": hb\n\n")
    if time.ticks_diff(now, _t[2]) >= 60000:
        _t[2] = now
        gc.collect()
        wnet.log("ok free %d requests %d streams %d wifi rssi %s" % (gc.mem_free(), _req, len(_clients), wnet.sta.status("rssi")))
    try:
        c, _ = _srv.accept()
    except OSError:
        return
    _http(c)


def run():
    """Serves the browser and runs the script's timers. Does not return."""
    global _srv, _wdt
    _wdt = machine.WDT(timeout=30000)
    _srv = socket.socket()
    _srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    _srv.bind(("0.0.0.0", 80))
    _srv.listen(3)
    _srv.settimeout(0.03)
    _load_pin()
    if _pin is not None:
        wnet.log("PIN lock is on")
    now = time.ticks_ms()
    _t[0] = _t[1] = _t[2] = now
    print("open  http://%s/" % wnet.sta.ifconfig()[0])
    try:
        start = getattr(sys.modules.get(SCRIPT), "on_start", None)   # optional User-Function: runs once, before the first page is served
        if start is not None:
            try:
                start()
            except Exception as e:
                _oops("in on_start", e)
        while True:
            _step()
    finally:
        _srv.close()
        for c in _clients[:]:
            _drop(c)
        machine.WDT(timeout=600000)                  # stopped (Ctrl-C from a tool): the 30 s watchdog must not reset the board while it is being worked on


def quit():
    """Ends the app: calls the script's on_exit() (if it has one), tells the open pages, closes the server and stops at the prompt.
    Call it from a User-Function, for example a Quit button's button1_click(). Press the board's RST button to start the app again."""
    h = getattr(sys.modules.get(SCRIPT), "on_exit", None)
    if h is not None:
        try:
            h()
        except Exception as e:
            _oops("in on_exit", e)
    _pend[("_dlg", "x")] = {"msg": "The app has ended. This page no longer works. To start it again, press the RST button on the ESP32, then reload this page.", "btns": ["OK"]}
    _flush()
    time.sleep_ms(400)                                           # let the pages receive it
    wnet.log("the app has ended (quit)")
    raise KeyboardInterrupt        # not an Exception, so run() and main.py let it through: the server closes and the board stops at the prompt
