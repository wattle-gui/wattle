# main.py -- starts the project at power-up.
# Change PROJECT to run a different USER script. (Project_1 does not
# need run() when started this way; the loop works either way.)
PROJECT = "Project_1"

import Runtime
try:
    mod = __import__(PROJECT)
except Exception as e:
    Runtime.fatal(e)            # shows the error on the screen (and the serial port)
Runtime.run(mod)
