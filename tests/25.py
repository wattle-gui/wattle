# Test 25 -- save() and load(): data that survives a restart. Stored in a file on the board (data_count.json).
from Runtime import *

count = load("count", 0)                 # 0 if nothing was saved yet
label1.text = "count: %d" % count

def button1_click():
    global count
    count += 1
    label1.text = "count: %d" % count
    save("count", count)                 # save only when something really changed (flash wears out)

def button2_click():
    global count
    count = 0
    label1.text = "count: 0"
    save("count", 0)

run()
