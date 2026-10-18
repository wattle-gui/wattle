# Test 09 -- the full keyboard. The keyboard widget is not drawn with the screen; the script
# opens it with show(). The typed text goes into the widget named in "target" (memo1).
from Runtime import *

def button1_click():
    keyboard1.show()        # waits here until Enter (text sent to the target) or Esc (cancel)

run()
