# remove_wattle.py -- DESKTOP: start again from the beginning. Run it with  ./wattle remove
#   1. optionally empties the board (every file except boot.py), so it is like a new board with only MicroPython
#   2. optionally removes Wattle from the computer (the package and the Wattle folder; the folder projects inside it stays)
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
    import wattle_port
    if wattle_port.in_use(port):
        print("Another program (Thonny?) is using %s. Close it and run  ./wattle remove  again." % port)
        return False
    import boardlink
    print("Stopping the board and deleting its files ...")
    boardlink.halt()
    r = subprocess.run(boardlink.MPREMOTE + ["connect", port, "exec", WIPE], capture_output=True, text=True)
    print((r.stdout + r.stderr).strip())
    return r.returncode == 0


def remove_computer():
    if sys.platform.startswith("win"):
        print("To remove Wattle from this computer: open Windows Settings, Apps, find Wattle, click Uninstall.")
        return
    home = os.path.expanduser("~")
    mine = os.path.realpath(HERE)                      # the folder this copy of Wattle is in (not always ~/Wattle)
    if subprocess.run(["dpkg", "-s", "wattle"], capture_output=True).returncode == 0:
        print("Removing the package (your password may be asked) ...")
        if subprocess.run(["sudo", "apt", "remove", "-y", "wattle"]).returncode:
            print("The package could not be removed. Type   sudo apt remove wattle   and enter your password.")
    saved = os.path.join(home, ".config", "wattle", "folder")      # where the installation put Wattle (default: ~/Wattle)
    installed = os.path.join(home, "Wattle")
    if os.path.isfile(saved):
        first = open(saved, encoding="utf-8").readline().strip()
        if first:
            installed = first
    if os.path.realpath(installed) != mine:
        print("This copy of Wattle is not the installed one (%s), so its folder was left alone." % installed)
        return
    os.chdir(home)
    for old in glob.glob(mine + "-previous-*"):        # older copies: kept when they hold projects of the person
        proj = os.path.join(old, "projects")
        has_work = os.path.isdir(proj) and any(n != "README.txt" for n in os.listdir(proj))
        if has_work:
            print("Kept %s: it holds projects." % old)
        else:
            shutil.rmtree(old, ignore_errors=True)
    for name in os.listdir(mine):                      # everything of Wattle, but NEVER the projects folder
        if name == "projects":
            continue
        path = os.path.join(mine, name)
        if os.path.isdir(path) and not os.path.islink(path):
            shutil.rmtree(path, ignore_errors=True)
        else:
            try:
                os.remove(path)
            except OSError:
                pass
    proj = os.path.join(mine, "projects")
    if os.path.isdir(proj) and any(n != "README.txt" for n in os.listdir(proj)):
        print("Wattle is removed from %s. Your projects are still in %s" % (mine, proj))
    else:
        shutil.rmtree(mine, ignore_errors=True)
        print("Deleted the folder %s" % mine)


def uninstall():
    """Only take Wattle off this computer: the package, the Wattle folder and the Editor icons. Your projects folder and the ESP32 stay as they are."""
    print("""REMOVE WATTLE
This removes Wattle from this computer: the program, the Wattle folder and the Wattle Editor icons.
The folder  projects  inside it, with your own designs and scripts, stays. The ESP32 stays as it is.
""")
    if sys.platform.startswith("win"):
        print("On Windows: open Windows Settings, Apps, find Wattle, click Uninstall.")
        return
    if not yes("Remove Wattle from this computer?"):
        print("\nNothing was changed.")
        return
    home = os.path.expanduser("~")
    for entry in (os.path.join(home, ".local/share/applications/wattle-editor.desktop"), os.path.join(home, ".local/share/applications/wattle-setup.desktop"),
                  os.path.join(home, ".local/share/applications/wattle-manuals.desktop"), os.path.join(home, ".local/share/applications/wattle-terminal.desktop")):
        if os.path.exists(entry):
            os.remove(entry)
    desk = subprocess.run(["xdg-user-dir", "DESKTOP"], capture_output=True, text=True).stdout.strip() or os.path.join(home, "Desktop")
    for name in ("Wattle Editor", "Set up an ESP32 with Wattle", "Wattle Manuals", "Wattle Terminal"):
        icon = os.path.join(desk, name + ".desktop")
        if os.path.exists(icon):
            os.remove(icon)
            print("Removed the icon  %s  from the Desktop." % name)
    remove_computer()
    print("\nWattle is removed.")


def start_installation():
    """Opens the downloaded package, as a double-click in the Downloads folder would."""
    if sys.platform.startswith("win"):
        print("To put Wattle on the board again, run  wattle install  (or double-click the Wattle Setup file again).")
        return
    debs = sorted(glob.glob(os.path.expanduser("~/Downloads/wattle_*_all.deb")))
    if debs:
        print("Starting the installation again ...")
        subprocess.Popen(["xdg-open", debs[-1]], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        print("A window opens: carry on at step 4 of chapter 2 (Click Run anyway).")
    else:
        print("To install again: download wattle_0.10_all.deb (chapter 2, step 2), then double-click it.")


def main():
    if "--uninstall" in sys.argv:
        return uninstall()
    only_computer = "--no-board" in sys.argv
    print("""START AGAIN
This helps when an installation went wrong, or when you want to try it again from the beginning. It will:
  1. empty the board (delete the files on it, so it is like a new board with only MicroPython on it),
  2. remove Wattle from this computer (the program package and the Wattle folder), and
  3. start the installation again.
The folder  projects  inside the Wattle folder, with your own designs and scripts, stays.
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
