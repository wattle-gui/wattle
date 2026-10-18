# Test 12 -- keyboard events.
#   input_event: true     -> keyboard1_input(text) is called after EVERY key
#   events: ["enter"]     -> keyboard1_enter(text) is called once, when Enter closes the keyboard
from Runtime import *

keys = 0

def keyboard1_input(text):        # text = everything typed so far
    global keys
    keys += 1
    label1.text = "keys: %d (len %d)" % (keys, len(text))

def keyboard1_enter(text):
    label2.text = "enter: " + text

def button1_click():
    keyboard1.show()

run()
