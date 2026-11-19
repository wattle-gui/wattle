# hello.py -- the browser demo: a title and a button that counts the taps.
from Runtime import *

taps = 0


def button1_click():
    global taps
    taps += 1
    label2.text = "Taps: %d" % taps


run()
