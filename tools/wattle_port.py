# wattle_port.py -- which serial port the desktop tools use, and how they talk to the board. The port, in this order:
#   1. the environment variable ESP_PORT (Linux: ESP_PORT=/dev/ttyUSB1, Windows: set ESP_PORT=COM5)
#   2. the first line of the file wattle.port next to this file (the installer writes it)
#   3. Linux and macOS: /dev/ttyUSB0.  Windows: the USB-serial chip that is plugged in (CH340, CP210x ...), else COM3.
import os
import sys

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))     # the Wattle folder (this file is in tools/)

# mpremote is started through this Python, so it needs no PATH entry (on Windows there is none)
MPREMOTE = [sys.executable, "-m", "mpremote"]

# USB-serial chips that ESP32 boards use: CH340/CH9102 (1A86), CP210x (10C4), FTDI (0403)
_VIDS = (0x1A86, 0x10C4, 0x0403)


def candidates():
    """The serial ports of plugged-in USB-serial chips, e.g. ['COM3']. [] if none (or pyserial is missing)."""
    try:
        from serial.tools import list_ports
        return sorted(p.device for p in list_ports.comports() if p.vid in _VIDS)
    except Exception:
        return []


def in_use(port):
    """True if another program is using the port (Thonny, a serial monitor ...)."""
    if sys.platform.startswith("win"):
        try:
            import serial
            serial.Serial(port).close()          # Windows refuses a second open: PermissionError
            return False
        except Exception as e:
            return "PermissionError" in repr(e) or "Access is denied" in str(e)
    import subprocess
    try:
        return subprocess.run(["fuser", port], capture_output=True).returncode == 0
    except OSError:
        return False


def _saved():
    try:
        with open(os.path.join(HERE, "wattle.port")) as f:
            return f.readline().strip()
    except OSError:
        return ""


def _default():
    if sys.platform.startswith("win"):
        found = candidates()
        return found[0] if found else "COM3"
    return "/dev/ttyUSB0"


PORT = os.environ.get("ESP_PORT") or _saved() or _default()
