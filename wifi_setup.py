# wifi_setup.py -- kept for  ./wattle wifi.  It is the same as:   python3 install_wattle.py --wifi
# (A user needs only install_wattle.py: the installer offers the Wi-Fi step itself at the end, and `--wifi` runs just that step.)
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import install_wattle

if __name__ == "__main__":
    install_wattle.main(["--wifi"] + sys.argv[1:])
