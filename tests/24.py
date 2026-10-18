# Test 24 -- message(): a pop-up the user must answer. It returns the label of the tapped button.
from Runtime import *

def button1_click():
    message("Saved!")                                  # one button, "OK" by default
    label1.text = "info closed"

def button2_click():
    answer = message("Reset the counter?", "Yes", "No")
    label1.text = "you chose " + answer

def button3_click():
    answer = message("What now?", "Save", "Discard", "Cancel")
    label1.text = "you chose " + answer

def button4_click():
    message("This is a longer message that needs several lines of text to be shown properly on the small screen.")
    label1.text = "long text closed"

run()
