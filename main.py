# main.py -- starts the project at power-up.
# Change PROJECT to run a different USER script. (Project_1 does not
# need run() when started this way; the loop works either way.)
# Until you have put a script of your own on the board, the demo (demo.py) runs instead.
PROJECT = "Project_1"

import os
import Runtime
try:
    os.stat(PROJECT + ".py")
except OSError:
    try:
        os.stat(PROJECT + ".mpy")
    except OSError:
        PROJECT = "demo"
try:
    mod = __import__(PROJECT)
except Exception as e:
    Runtime.fatal(e)            # shows the error on the screen (and the serial port)
Runtime.run(mod)
