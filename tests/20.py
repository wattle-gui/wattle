# Test 20 -- radio groups ("choice" widget, style "radio"): one item is selected at a time.
# The event gets the NUMBER of the chosen item (0 = first); the texts are in .items.
from Runtime import *

def choice1_changed(index):
    label1.text = choice1.items[index]          # show the chosen colour name

def choice2_changed(index):
    label2.text = choice2.items[index]

def button1_click():                            # a script can select an item too
    choice1.selected = 0
    choice2.selected = 0
    label1.text = choice1.items[0]
    label2.text = choice2.items[0]

run()
