# boardlink.py -- DESKTOP helper used by deploy.py and check_script.py: talking to the board over USB.
#   halt()      stop whatever the board is running (works even when it sleeps in LOW_POWER mode)
#   restart()   hard reset: the board starts main.py again
#   cat(path)   text of a file on the board, or None if it is not there
#   put(local, remote)   copy a file to the board
import os, subprocess, sys, time

import wattle_port
PORT = wattle_port.PORT                      # ESP_PORT, or wattle.port, or the plugged-in board
MPREMOTE = wattle_port.MPREMOTE


def halt():
    """Reset the board and send Ctrl-C again and again while it boots, so it stops at the prompt BEFORE the
    project (maybe a sleeping LOW_POWER one) starts."""
    import serial
    ser = serial.Serial(PORT, 115200, timeout=0.05)
    ser.dtr = False
    ser.rts = True              # EN low = reset
    time.sleep(0.1)
    ser.rts = False
    t0 = time.time()
    while time.time() - t0 < 3.0:
        ser.write(b"\x03")
        ser.read(200)
        time.sleep(0.03)
    ser.close()


def restart():
    import serial
    ser = serial.Serial(PORT, 115200, timeout=0.05)
    ser.dtr = False
    ser.rts = True
    time.sleep(0.1)
    ser.rts = False
    ser.close()


def _mp(*args):
    return subprocess.run(MPREMOTE + ["connect", PORT] + list(args), capture_output=True, text=True)


def cat(path):
    r = _mp("fs", "cat", ":" + path)
    return r.stdout if r.returncode == 0 else None


def put(local, remote=None):
    r = _mp("fs", "cp", local, ":" + (remote or os.path.basename(local)))
    if r.returncode != 0:
        sys.exit("could not copy %s to the board: %s" % (local, r.stderr.strip()))
