# sleep.py -- the live wave with two buttons that put the board into deep sleep: one wakes it after 30 seconds, the other only when pin 14 is touched.
# After a wake the script starts again from the top: the counter below survives because it is saved.
import math
from Runtime import *

wakes = load("wakes", 0) + 1
save("wakes", wakes)
phase = 0


def tick():
    global phase
    phase += 0.3
    wave1.add(50 + 40 * math.sin(phase))


def show_board():
    info1.text = "wake %d by %s\nWi-Fi %d dBm, free %d bytes" % (wakes, woke_by(), board.rssi, board.free)


def button_timer_click():
    deepsleep(30)                                   # wakes by itself after 30 seconds


def button_touch_click():
    deepsleep(0, touch=14)                          # wakes only when pin 14 is touched
    message("Not asleep: pin 14 cannot sense a touch on this board.")     # only reached when the board refused to sleep


every(300, tick)
every(2000, show_board)
show_board()
Screen("main")
run()
