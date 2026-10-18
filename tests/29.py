# Test 29 -- long press. A widget that lists "longpress" in its events gets  <id>_longpress()  when it is held
# for about 0.7 seconds (Runtime.LONG_PRESS_MS). If it also lists "click", a short tap still gives <id>_click().
from Runtime import *

short = 0
long_ = 0

def show():
    label1.text = "short: %d   long: %d" % (short, long_)

def button1_click():
    global short
    short += 1
    show()

def button1_longpress():
    global long_
    long_ += 1
    show()

def button2_longpress():
    global long_
    long_ += 1
    show()
    button2.text = "Hold only: held %d x" % long_

def button3_click():
    global short
    short += 1
    show()

run()
