"""The devices a design can be made for (the Device menu): the CYD board, an Android phone or tablet, a laptop, and any the user adds.

The only ready-made one is the CYD board (hardware/devices.json): its screen is fixed. Your own phones, tablets and computers are
sections [device.NAME] in editor.ini, made by Settings from the size a phone reports to its board. The choice is
stored in the design as target.device, so it travels with the file."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

_ROOT = Path(__file__).resolve().parent.parent
_HW = _ROOT.parent / "hardware" if (_ROOT.parent / "hardware").is_dir() else _ROOT / "hardware"
BROWSER = "board_browser"
CYD = "board_cyd"
DEFAULT = "cyd"

_FALLBACK = [
    {"id": "cyd", "name": "CYD 2.8\" board", "board": CYD, "width": 320, "height": 240},
]


def load_devices(settings=None) -> list[dict[str, Any]]:
    """The ready-made devices, then the user's own. Entries that are wrong are left out (settings.notes says which)."""
    out: list[dict[str, Any]] = []
    try:
        data = json.loads((_HW / "devices.json").read_text(encoding="utf-8"))
        out = [d for d in data if isinstance(d, dict) and d.get("id") and d.get("width") and d.get("height")]
    except (OSError, ValueError, TypeError):
        pass
    if not out:
        out = [dict(d) for d in _FALLBACK]
    if settings is not None:
        for sec in settings.sections("device."):
            dev_id = sec[len("device."):].strip()
            try:
                w, h = int(settings.get(sec, "width")), int(settings.get(sec, "height"))
                if not (dev_id and 40 <= w <= 8000 and 40 <= h <= 8000):
                    raise ValueError
            except ValueError:
                settings.notes.append(f"[{sec}] in editor.ini needs a width and a height (numbers): ignored.")
                continue
            board = settings.get(sec, "board", BROWSER)
            out = [d for d in out if d["id"] != dev_id]                # your own [device.cyd] replaces the built-in CYD
            out.append({"id": dev_id, "name": settings.get(sec, "name", dev_id) or dev_id,
                        "board": board if board in (BROWSER, CYD) else BROWSER, "width": w, "height": h})
    return out


def find(devices: list[dict[str, Any]], dev_id: str) -> dict[str, Any] | None:
    return next((d for d in devices if d["id"] == dev_id), None)


def device_of(data: dict[str, Any], devices: list[dict[str, Any]]) -> str:
    """The device a design is for: target.device when it is known, else worked out from target.board (older designs)."""
    target = data.get("target") or {}
    named = str(target.get("device") or "")
    if find(devices, named):
        return named
    board = BROWSER if str(target.get("board") or "") == BROWSER else CYD
    screens = data.get("screens") or []
    if screens:
        w, h = int(screens[0].get("width") or 0), int(screens[0].get("height") or 0)
        for d in devices:                           # the exact size first (a phone upright and the same phone on its side are two entries)
            if d.get("board") == board and (int(d["width"]), int(d["height"])) == (w, h):
                return d["id"]
        for d in devices:                           # an older design made for a turned device
            if d.get("board") == board and (int(d["width"]), int(d["height"])) == (h, w):
                return d["id"]
        return ""                                   # a size of its own: no device in the menu is ticked
    return "" if board == BROWSER else DEFAULT


def target_for(device: dict[str, Any], old: dict[str, Any] | None = None) -> dict[str, Any]:
    """The design's target block for a device. The fonts the design already has are kept."""
    old = old or {}
    fonts = old.get("fonts") or [{"name": "default", "sizes": [8, 16, 24], "styles": ["bold", "italic"]}]
    w, h = int(device["width"]), int(device["height"])
    if device["board"] == BROWSER:
        return {
            "model": "Browser (any ESP32 with Wi-Fi, no screen needed)", "processor": "ESP32", "board": BROWSER, "device": device["id"],
            "display": {"model": "Browser", "width": w, "height": h, "interface": "Wi-Fi (web page)", "driver": "(none: the browser draws)"},
            "touch": {"model": "Browser", "type": "finger or mouse", "interface": "Wi-Fi (web page)",
                      "driver": "(none: the browser sends the taps)"},
            "fonts": fonts,
        }
    return {
        "model": "CYD 2.8 (ESP32 + ILI9341 + XPT2046)", "processor": "ESP32", "board": CYD, "device": device["id"],
        "display": {"model": "ILI9341", "width": w, "height": h, "interface": "SPI", "driver": "ili9341.py"},
        "touch": {"model": "XPT2046", "type": "resistive", "interface": "SPI", "driver": "touch_xpt2046.py"},
        "fonts": fonts,
    }


def orientation_for(width: int, height: int) -> str:
    return "portrait" if height > width else "landscape"


def widgets_outside(data: dict[str, Any], width: int, height: int) -> int:
    """How many widgets would stick out of a screen of this size."""
    n = 0
    for sc in data.get("screens") or []:
        for w in sc.get("widgets") or []:
            try:
                if int(w.get("x", 0)) + int(w.get("w", 0)) > width or int(w.get("y", 0)) + int(w.get("h", 0)) > height:
                    n += 1
            except (TypeError, ValueError):
                continue
    return n


def apply_device(data: dict[str, Any], device: dict[str, Any]) -> None:
    """Make an existing design (a dict) belong to the device: the target block, and every screen's size and orientation."""
    data["target"] = target_for(device, data.get("target"))
    w, h = int(device["width"]), int(device["height"])
    for sc in data.get("screens") or []:
        sc["width"], sc["height"], sc["orientation"] = w, h, orientation_for(w, h)


def new_design(device: dict[str, Any]) -> dict[str, Any]:
    from esd.model import empty_design

    data = empty_design()
    apply_device(data, device)
    return data


def _ask_info(host: str, timeout: float) -> dict[str, Any] | None:
    """The /info answer of a Wattle board at this address, or None when nothing there is a Wattle board."""
    import urllib.request
    try:
        with urllib.request.urlopen(f"http://{host}/info", timeout=timeout) as r:
            data = json.loads(r.read(600).decode("utf-8", "replace"))
    except (OSError, ValueError):
        return None
    if not isinstance(data, dict) or data.get("wattle") != 1:
        return None
    try:
        width, height = int(data.get("width") or 0), int(data.get("height") or 0)
        viewers = int(data.get("viewers", 1))                        # pages open right now (an older board does not say: assume one)
        if isinstance(data.get("devices"), list):                    # one entry per browser that has the page open right now
            devices = [{"id": str(d.get("id") or ""),
                        # the device's real SCREEN size (steady), not its browser window (bars come and go); an older board only has the window
                        "width": int(d.get("screen_w") or d.get("width") or 0), "height": int(d.get("screen_h") or d.get("height") or 0),
                        "dpr": float(d.get("dpr") or 1.0), "join": str(d.get("join") or "")}
                       for d in data["devices"] if isinstance(d, dict)]
        else:                                                        # an older board: only the last size, no browser ids
            devices = [{"id": "", "width": width, "height": height, "dpr": float(data.get("dpr") or 1.0), "join": ""}] if width >= 40 and viewers > 0 else []
        return {"address": str(data.get("ip") or host), "name": str(data.get("name") or ""), "width": width, "height": height,
                "dpr": float(data.get("dpr") or 1.0), "viewers": viewers, "devices": [d for d in devices if d["width"] >= 40 and d["height"] >= 40]}
    except (TypeError, ValueError):
        return None


def local_prefix() -> str | None:
    """The first three numbers of this computer's address on the Wi-Fi/LAN (192.168.1), or None when it is offline."""
    import socket
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("10.255.255.255", 9))                  # nothing is sent: it only makes the system pick the right network
            ip = s.getsockname()[0]
    except OSError:
        return None
    return ip.rsplit(".", 1)[0] if ip.count(".") == 3 and not ip.startswith("127.") else None


def scan_boards(timeout: float = 0.8) -> list[dict[str, Any]]:
    """Look for running Wattle boards on this computer's network (every address x.y.z.1-254 is asked, 64 at a time).
    Each board found: address, name, and the width/height/dpr its phone reported (0 when no phone has the page open)."""
    from concurrent.futures import ThreadPoolExecutor
    prefix = local_prefix()
    if not prefix:
        return []
    with ThreadPoolExecutor(max_workers=64) as pool:
        found = list(pool.map(lambda n: _ask_info(f"{prefix}.{n}", timeout), range(1, 255)))
    return [b for b in found if b]


def look_for_boards(addresses=(), names=()) -> list[dict[str, Any]]:
    """Find Wattle boards the quick way first: the addresses we saw before, and the boards' names (name.local follows an address that
    the router has changed). Only when none of those answers, every address on the network is tried (scan_boards)."""
    from concurrent.futures import ThreadPoolExecutor
    hosts = list(dict.fromkeys([a for a in addresses if a] + [f"{n}.local" for n in names if n]))
    found: list[dict[str, Any]] = []
    if hosts:
        with ThreadPoolExecutor(max_workers=8) as pool:
            found = [b for b in pool.map(lambda h: _ask_info(h, 2.0), hosts) if b]
    if not found:
        found = scan_boards()
    seen: set[str] = set()
    return [b for b in found if not (b["address"] in seen or seen.add(b["address"]))]


def offer_join(address: str, code: str, timeout: float = 3.0) -> bool:
    """Ask the ESP32 to offer a registration code to every open page ("Add this device to the Wattle Editor?"); an empty code withdraws it."""
    import urllib.parse
    import urllib.request
    try:
        url = f"http://{address}/join?code={urllib.parse.quote(code)}"
        with urllib.request.urlopen(urllib.request.Request(url, data=b""), timeout=timeout):
            return True
    except (OSError, ValueError):
        return False
