# remove_wattle.py -- DESKTOP: start again from the beginning. Run it with  ./wattle remove
#   1. optionally empties the board (every file except boot.py), so it is like a new board with only MicroPython
#   2. optionally removes Wattle from the computer (the package and the folder ~/Wattle; your own projects are not in them)
# It asks before it does anything, and says what it will do.
import glob, os, shutil, subprocess, sys

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(HERE, "tools"))

WIPE = """
import os
def rm(d):
    for n in os.listdir(d):
        p = d.rstrip('/') + '/' + n
        if p == '/boot.py':
            continue
        try:
            os.remove(p)
        except OSError:
            rm(p)
            os.rmdir(p)
rm('/')
print('board emptied')
"""


def yes(question):
    return input(question + " [y/N] ").strip().lower() in ("y", "yes")


def empty_board():
    import wattle_port
    port = wattle_port.PORT
    if subprocess.run(["fuser", port], capture_output=True).returncode == 0:
        print("Another program (Thonny?) is using %s. Close it and run  ./wattle remove  again." % port)
        return False
    import boardlink
    print("Stopping the board and deleting its files ...")
    boardlink.halt()
    r = subprocess.run(["mpremote", "connect", port, "exec", WIPE], capture_output=True, text=True)
    print((r.stdout + r.stderr).strip())
    return r.returncode == 0


def remove_computer():
    home = os.path.expanduser("~")
    mine = os.path.join(home, "Wattle")
    if subprocess.run(["dpkg", "-s", "wattle"], capture_output=True).returncode == 0:
        print("Removing the package (your password may be asked) ...")
        subprocess.run(["sudo", "apt", "remove", "-y", "wattle"])
    if os.path.realpath(HERE) == os.path.realpath(mine):
        os.chdir(home)
        for old in glob.glob(os.path.join(home, "Wattle-previous-*")) + [mine]:
            shutil.rmtree(old, ignore_errors=True)
        print("Deleted the folder %s" % mine)
    else:
        print("This copy of Wattle is not in %s, so its folder was left alone." % mine)


def start_installation():
    """Opens the downloaded package, as a double-click in the Downloads folder would."""
    debs = sorted(glob.glob(os.path.expanduser("~/Downloads/wattle_*_all.deb")))
    if debs:
        print("Starting the installation again ...")
        subprocess.Popen(["xdg-open", debs[-1]], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        print("A window opens: carry on at step 4 of chapter 2 (Click Run anyway).")
    else:
        print("To install again: download wattle_0.9_all.deb (chapter 2, step 2), then double-click it.")


def main():
    only_computer = "--no-board" in sys.argv
    print("""START AGAIN
This helps when an installation went wrong, or when you want to try it again from the beginning. It will:
  1. empty the board (delete the files on it, so it is like a new board with only MicroPython on it),
  2. remove Wattle from this computer (the program package and the folder ~/Wattle), and
  3. start the installation again.
Your own projects are not in those places, so they stay.
""")
    if not yes("Start again?"):
        print("\nNothing was changed.")
        return
    if not only_computer and not empty_board():
        print("\nNothing was removed from the computer. Fix the problem above and run  ./wattle remove  again.")
        print("(No board plugged in? Then use  ./wattle remove --no-board  to remove Wattle from the computer only.)")
        return
    remove_computer()
    start_installation()


main()
