# Test 13 -- "hide_on_enter": false -> Enter SENDS the text but the keyboard stays open
# (like a chat box). Esc closes it. keyboard1_enter(text) is called for every Enter, and
# show() returns the last text that was sent (None if nothing was sent).
from Runtime import *

sent = 0

def keyboard1_enter(text):
    global sent
    sent += 1
    # the main screen is hidden while the keyboard is open; this shows when it returns

def button1_click():
    last = keyboard1.show()
    label1.text = "sent: %d  last: %s" % (sent, last)

run()
