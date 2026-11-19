# pin_setup.py -- kept for  wattle pin.  It is the same as:   python3 install_wattle.py --pin
# (browser boards: puts a sealed PIN or password on the board; with --status: says whether there is one; with --remove: deletes it)
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import install_wattle

if __name__ == "__main__":
    install_wattle.main(["--pin"] + sys.argv[1:])
