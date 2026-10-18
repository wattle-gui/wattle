# Test 01 -- change a button's colour and text from the script.
from Runtime import *

def button1_click():
    # Property names are the JSON names: .background, .text, .color ...
    # The widget redraws itself as soon as you set one.
    button1.background = "red" if button1.background != "red" else "green"

def button2_click():
    if button2.text == "OFF":
        button2.text = "ON"
        button2.background = "blue"
    else:
        button2.text = "OFF"
        button2.background = "gray"

run()
