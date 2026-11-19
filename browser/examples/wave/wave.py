# wave.py -- one live sine wave: a steady load, handy for measuring the board's current.
import math
from Runtime import *

phase = 0


def tick():
    global phase
    phase += 0.3
    wave1.add(50 + 40 * math.sin(phase))


def show_board():
    info1.text = "%s  %s\nfree %d bytes, Wi-Fi %d dBm\nphone %d x %d" % (board.name, board.ip, board.free, board.rssi, phone.width, phone.height)


every(300, tick)
every(2000, show_board)
Screen("main")
run()
