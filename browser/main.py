# main.py (browser flavour) -- starts the project at power-up. The screen is a web page that this board serves:
# open the address that the installer printed (or http://wattle.local) on a phone, tablet or PC.
# Change PROJECT to run a different script. Until you have put a script of your own on the board, the demo (demo.py) runs instead.
PROJECT = "Project_1"

import machine
import os
import time

import wnet

wnet.log("boot, reset cause %d" % machine.reset_cause())       # 1 power-on, 3 soft reset, 4 watchdog
if machine.reset_cause() != machine.DEEPSLEEP_RESET:
    time.sleep(3)                                                # a moment in which Ctrl-C can still stop the board (not after a deep sleep: that wake must be quick)
try:
    wnet.log("wifi ok " + wnet.connect())
    import Runtime
    try:
        os.stat(PROJECT + ".py")
    except OSError:
        PROJECT = "demo"
    Runtime.SCRIPT = PROJECT
    try:
        __import__(PROJECT)                                      # the script ends with run(), which serves the page
    except KeyboardInterrupt:
        raise
    except Exception as e:
        if Runtime._srv is not None:
            raise                                                # the page was already being served: the server itself failed, restart the board as before
        Runtime._oops("while your script was starting", e, keep=True)     # a mistake in the script: serve the page anyway and show the error on it
        Runtime.run()
    # Only a script that forgot run() gets here. Say so, and serve the page anyway, so that the phone shows the design and a box that explains.
    wnet.log("the script ended without run(): serving the page anyway")

    def _forgot():
        Runtime._timers[:] = [t for t in Runtime._timers if t[1] is not _forgot]      # once
        Runtime.message("Your script ended without calling run(). The buttons do nothing. Add run() as the very last line of the script.")
    Runtime.every(1500, _forgot)
    Runtime.run()
except KeyboardInterrupt:
    raise                                                        # let mpremote / Thonny stop the board
except BaseException as e:
    wnet.log("stopped: %r" % (e,))
    time.sleep(5)
    machine.reset()
