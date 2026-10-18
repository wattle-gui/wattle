# Test 26 -- a mistake that stops the script from STARTING is shown on the screen too.
from Runtime import *

label1.text = "starting"
x = undefined_function()                 # NameError while the script is being loaded

run()
