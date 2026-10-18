# wattle_port.py -- which serial port the desktop tools use. In this order:
#   1. the environment variable ESP_PORT (Windows: set ESP_PORT=COM5)
#   2. the first line of the file wattle.port next to this file (install.sh writes it)
#   3. /dev/ttyUSB0
import os

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))     # the Wattle folder (this file is in tools/)


def _saved():
    try:
        with open(os.path.join(HERE, "wattle.port")) as f:
            return f.readline().strip()
    except OSError:
        return ""


PORT = os.environ.get("ESP_PORT") or _saved() or "/dev/ttyUSB0"
