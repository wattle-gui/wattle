#!/bin/bash
# install.sh -- Wattle: one script that takes you from "just unpacked" to "something running on the board".
#
#   ./install.sh              the full guided installation (asks before it does anything important)
#   ./install.sh --check      only looks (Python, tools, port, MicroPython) and changes nothing
#   ./install.sh --yes        no questions: takes every default answer (never erases the board: that default is "no")
#   ./install.sh --no-demo    do not load the small demo     (--with-picker is still accepted and does nothing: PyQt6 is now always installed)
#
# It will: 1) check Python  2) make a private tool folder (.venv) and install mpremote, esptool, pillow into it
#          3) find the board's USB port  4) check MicroPython on the board (and install it, if you agree, then carry on)
#          5) copy the Wattle files to the board  6) (Wi-Fi: only a note)  7) show a demo so you can see it work.
# The only question it asks in the normal case is whether to install MicroPython, when the board has none (that erases the board).
# Press Enter to accept the answer in [brackets]. Nothing leaves your computer except the downloads you agree to.
# Linux only in version 0.10.

cd "$(dirname "$0")" || exit 1
CHECK=0
YES=0
TOOLS_ONLY=0
WITH_PICKER=0
DEMO=1
for a in "$@"; do
    [ "$a" = "--check" ] && CHECK=1
    [ "$a" = "--yes" ] && YES=1
    [ "$a" = "--with-picker" ] && WITH_PICKER=1
    [ "$a" = "--no-demo" ] && DEMO=0
    [ "$a" = "--tools-only" ] && TOOLS_ONLY=1
done

say()  { printf '\n\033[1m%s\033[0m\n' "$*"; }
ok()   { printf '  \033[32mOK\033[0m  %s\n' "$*"; }
warn() { printf '  \033[33m!!\033[0m  %s\n' "$*"; }
fail() { printf '  \033[31mSTOP\033[0m %s\n' "$*"; exit 1; }
ask()  { # ask "question" default(y|n)  -> returns 0 for yes
    local def="$2" a
    [ "$CHECK" = 1 ] && return 1
    if [ "$YES" = 1 ]; then [ "$def" = y ]; return; fi
    if [ "$def" = y ]; then read -r -p "  $1 [Y/n] " a; a=${a:-y}; else read -r -p "  $1 [y/N] " a; a=${a:-n}; fi
    case "$a" in y|Y|yes|YES) return 0 ;; *) return 1 ;; esac
}

say "Wattle installer (version 0.10, for the CYD board)"
[ "$CHECK" = 1 ] && echo "  (check only: nothing will be changed)"

# ---------------------------------------------------------------- 1. Python
say "Python"
command -v python3 >/dev/null || fail "python3 is not installed. Install it with your package manager (for example: sudo apt install python3 python3-venv)."
if ! python3 -c 'import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)'; then
    fail "Python $(python3 -V 2>&1 | cut -d' ' -f2) is too old. Wattle needs Python 3.10 or newer."
fi
ok "$(python3 -V)"
if ! python3 -c 'import venv, ensurepip' 2>/dev/null; then
    warn "Python's venv module is missing (it is needed for the private tool folder)."
    if command -v apt-get >/dev/null && ask "Install it now with 'sudo apt-get install -y python3-venv'?" y; then
        sudo apt-get install -y python3-venv || fail "the installation of python3-venv failed"
        python3 -c 'import venv, ensurepip' 2>/dev/null || fail "python3-venv is still missing"
    else
        fail "please install it (Ubuntu/Debian/Zorin:  sudo apt install python3-venv) and run ./install.sh again."
    fi
fi

# ---------------------------------------------------------------- 2. tools
say "The tools (in a private folder, .venv: nothing is installed system-wide)"
if [ -x .venv/bin/mpremote ] && [ -x .venv/bin/esptool ] && .venv/bin/python -c 'import PIL, serial, PyQt6' 2>/dev/null; then
    ok "already installed"
elif [ "$CHECK" = 1 ]; then
    warn "not installed yet (the full installation will do it)"
else
    echo "  This downloads mpremote, esptool, pillow and PyQt6 (the window library of the Wattle Editor) from the internet (about 110 MB)."
    python3 -m venv .venv || fail "could not create the .venv folder"
    echo "  Please wait: this takes a minute or two. Nothing is wrong if it seems quiet."
    .venv/bin/pip install --quiet --disable-pip-version-check --upgrade pip
    .venv/bin/pip install --quiet --disable-pip-version-check mpremote esptool pillow || fail "the download failed. Check your internet connection and run ./install.sh again."
    # PyQt6 is what the Wattle Editor is made with. Without it the board still works, but the Editor cannot start.
    .venv/bin/pip install --quiet --disable-pip-version-check PyQt6 || warn "PyQt6 could not be installed: the Wattle Editor will not start. Check your internet connection and run ./install.sh again."
    ok "installed"
fi
# From here on the tools are found first in .venv
export PATH="$PWD/.venv/bin:$PATH"
PY="$PWD/.venv/bin/python"
[ -x "$PY" ] || PY=python3

# ---------------------------------------------------------------- the Editor icon (step 7; also the last step of --tools-only)
make_editor_icon() {
EDITOR_SH="$PWD/Editor/ESP32_Editor.sh"
if [ "$CHECK" = 1 ]; then
    [ -f "$EDITOR_SH" ] && ok "the Editor is here: $EDITOR_SH" || warn "the Editor folder is missing"
elif [ ! -f "$EDITOR_SH" ]; then
    warn "the Editor folder is missing, so no icon was made"
else
    ENTRY="[Desktop Entry]
Version=1.0
Type=Application
Name=Wattle Editor
Comment=Design the screens of your Wattle program
Exec=/bin/bash \"$EDITOR_SH\"
Path=$PWD/Editor
Icon=applications-electronics
Terminal=false
Categories=Development;Electronics;
StartupNotify=true"
    mkdir -p "$HOME/.local/share/applications"
    printf '%s\n' "$ENTRY" > "$HOME/.local/share/applications/wattle-editor.desktop"
    DESK=$(xdg-user-dir DESKTOP 2>/dev/null); [ -n "$DESK" ] || DESK="$HOME/Desktop"
    if [ -d "$DESK" ]; then
        printf '%s\n' "$ENTRY" > "$DESK/Wattle Editor.desktop"
        chmod +x "$DESK/Wattle Editor.desktop"
        gio set "$DESK/Wattle Editor.desktop" metadata::trusted true 2>/dev/null || true
        ok "a Wattle Editor icon is on your Desktop and in the applications menu"
    else
        ok "a Wattle Editor entry is in the applications menu"
    fi
fi
}

# --tools-only: the computer side only (tools and the Editor icon); no ESP32 is looked at or changed
if [ "$TOOLS_ONLY" = 1 ]; then
    say "The Wattle Editor icon"
    make_editor_icon
    say "ALL DONE"
    echo "  Wattle is now in your home folder (here: $PWD), and the Editor icon is on your Desktop."
    echo "  Next: set up an ESP32. Open the applications menu and click  Set up an ESP32 with Wattle."
    exit 0
fi

# ---------------------------------------------------------------- 3. port
# The board: only ONE may be connected. This step says nothing at all while that is so.
PORT_HEADING=0
port_heading() { PORT_HEADING=1; }          # only remembers that there was a problem (no heading is printed)
find_ports() { ls /dev/ttyUSB* /dev/ttyACM* 2>/dev/null; }
socket_of() {   # the physical USB socket of a port, for example "7" or "10.4" (it does not change when a board is replugged)
    local l
    for l in /dev/serial/by-path/*; do
        [ "$(readlink -f "$l" 2>/dev/null)" = "$1" ] && basename "$l" | sed -n 's/.*usb-0:\([0-9.]*\):.*/\1/p' && return
    done
}
PORTS=$(find_ports)
if [ -n "$ESP_PORT" ]; then
    PORTS="$ESP_PORT"; echo "  (using ESP_PORT=$ESP_PORT)"
fi
if [ -z "$PORTS" ]; then
    port_heading
    warn "no board found. Plug the CYD in with a USB cable that carries data (many cables only charge)."
    if [ "$CHECK" = 1 ]; then exit 0; fi
    [ "$YES" = 1 ] && fail "plug the board in and run ./install.sh --yes again."
    read -r -p "  Press Enter when the board is plugged in (or Ctrl-C to give up) " _
    sleep 2
    PORTS=$(find_ports)
    [ -n "$PORTS" ] || fail "still no port. Try another cable or another USB socket, then run ./install.sh again."
fi
N=$(printf '%s\n' "$PORTS" | grep -c .)
# Exactly ONE board must be connected: the installer waits until that is so (a wrong board must never be changed by mistake).
while [ "$N" -ne 1 ]; do
    port_heading
    if [ "$N" -gt 1 ]; then
        echo
        echo "  You have more than one ESP32 board connected! Please remove ALL the other boards before you are able to continue!"
        [ "$YES" = 1 ] && fail "more than one board is connected; with --yes I will not guess. Run:  ESP_PORT=/dev/ttyUSB1 ./install.sh --yes   (use the right port)"
    else
        echo
        echo "  No ESP32 board is connected! Please plug in the board you want to set up."
        [ "$YES" = 1 ] && fail "plug the board in and run ./install.sh --yes again."
    fi
    [ "$CHECK" = 1 ] && exit 0
    read -r -p "  Press Enter when exactly one board is connected (or Ctrl-C to give up) " _
    sleep 2
    PORTS=$(find_ports)
    N=$(printf '%s\n' "$PORTS" | grep -c .)
done
PORT="$PORTS"
[ "$PORT_HEADING" = 1 ] && ok "found $PORT"
if ! [ -r "$PORT" ] || ! [ -w "$PORT" ]; then
    warn "you are not allowed to use $PORT (the group 'dialout' is needed)."
    if ask "Fix it now with 'sudo usermod -aG dialout $USER'? (you must log out and in again afterwards)" y; then
        sudo usermod -aG dialout "$USER" && warn "Done. Now LOG OUT and LOG IN again (this is needed once). Then double-click the Wattle Terminal icon on your Desktop, type  ./install.sh  and press Enter." && exit 0
    fi
    fail "without access to the port nothing can be copied."
fi
if fuser "$PORT" >/dev/null 2>&1; then
    warn "another program is using $PORT (Thonny? a serial monitor?). Close it. Then double-click the Wattle Terminal icon on your Desktop, type  ./install.sh  and press Enter."
    [ "$CHECK" = 1 ] || exit 1
fi
[ "$CHECK" = 1 ] || echo "$PORT" > wattle.port          # the other tools use this port from now on
export ESP_PORT="$PORT"

# ---------------------------------------------------------------- 4. MicroPython
say "MicroPython on the board"
VER=$("$PY" - "$PORT" <<'EOF' 2>/dev/null
import subprocess, sys
r = subprocess.run(["mpremote", "connect", sys.argv[1], "exec", "import sys; print(sys.version)"],
                   capture_output=True, text=True, timeout=30)
print(r.stdout.strip() if r.returncode == 0 else "")
EOF
)
if [ -z "$VER" ]; then
    # a running program may block mpremote: stop it the same way Wattle's tools do, and try once more
    "$PY" -c 'import sys; sys.path.insert(0, "tools"); import boardlink; boardlink.halt()' 2>/dev/null
    VER=$(mpremote connect "$PORT" exec "import sys; print(sys.version)" 2>/dev/null)
fi
if echo "$VER" | grep -q "MicroPython"; then
    ok "$(echo "$VER" | tr -s ' ' | cut -c1-70)"
    echo "$VER" | grep -q "v1\.24" || warn "Wattle was built and tested with MicroPython 1.24; this is a different version (it may still work)."
else
    warn "MicroPython does not answer: the board is blank, or has something else on it."
    [ "$CHECK" = 1 ] && exit 0
    echo "  MicroPython can be installed now. This ERASES everything on the board."
    if ask "Install MicroPython 1.24.0 on the board?" n; then
        FW=ESP32_GENERIC-20241025-v1.24.0.bin
        if [ ! -f "$FW" ]; then
            ask "Download $FW (about 1.6 MB) from micropython.org?" y || fail "download it yourself from micropython.org/download (ESP32_GENERIC) and put it in this folder, then run ./install.sh again."
            "$PY" -c 'import sys, urllib.request as u; u.urlretrieve("https://micropython.org/resources/firmware/" + sys.argv[1], sys.argv[1])' "$FW" || fail "the download failed"
        fi
        ask "Last chance: erase the board and write $FW?" n || fail "cancelled; nothing was changed."
        esptool --chip esp32 --port "$PORT" erase_flash &&
        esptool --chip esp32 --port "$PORT" --baud 460800 write_flash -z 0x1000 "$FW" || fail "writing the firmware failed. Press the board's BOOT button while it starts, or try another cable, then run ./install.sh again."
        ok "MicroPython written."
        echo "  Waiting for the board to restart ..."
        VER=""
        for i in 1 2 3 4 5 6 7 8; do
            sleep 3
            VER=$(mpremote connect "$PORT" exec "import sys; print(sys.version)" 2>/dev/null)
            echo "$VER" | grep -q "MicroPython" && break
        done
        echo "$VER" | grep -q "MicroPython" || fail "the board does not answer yet. Unplug it, plug it in again, wait 5 seconds and run this installer again."
        ok "MicroPython is running on the board."
    fi
    echo "$VER" | grep -q "MicroPython" || fail "Wattle needs MicroPython on the board."
fi

# ---------------------------------------------------------------- 5. files
# --check only looks: it must never go on to change the board.
if [ "$CHECK" = 1 ]; then
    say "Check finished: nothing was changed."
    exit 0
fi
say "Copying the Wattle files to the board"
WATTLE_FROM_INSTALLER=1 "$PY" tools/install_board.py || fail "copying failed. Read the message above, then run ./install.sh again."

# ---------------------------------------------------------------- a name for this board (so that several CYD boards can be told apart)
BOARD_NAME=""
if [ "$YES" != 1 ]; then
    say "A name for this board"
    echo "  Give each CYD board a name of its own, so that you can tell your boards apart."
    echo "  Rules for the name: letters, digits, - and _ . No spaces. At most 24 characters."
    echo "  Examples:  CYD_51    Workshop"
    NAME_OK=0
    while [ "$NAME_OK" != 1 ]; do
        BOARD_NAME=""
        while ! printf '%s' "$BOARD_NAME" | grep -Eq '^[A-Za-z0-9_-]{1,24}$'; do
            "$PY" -c 'import termios; termios.tcflush(0, termios.TCIFLUSH)' 2>/dev/null || true       # anything typed while the installer was busy is thrown away: it must not end up in the name
            read -r -p "  Name: " BOARD_NAME
            BOARD_NAME=$(printf '%s' "$BOARD_NAME" | tr -d '\r\n' | sed 's/^ *//; s/ *$//')
            printf '%s' "$BOARD_NAME" | grep -Eq '^[A-Za-z0-9_-]{1,24}$' || echo "  That name does not follow the rules. Please try again."
        done
        echo "  You typed the name: $BOARD_NAME"
        ask "Is that right?" y && NAME_OK=1 || echo "  Then type the name again."
    done
fi
if [ -n "$BOARD_NAME" ]; then
    NAMEFILE=$(mktemp); printf '%s\n' "$BOARD_NAME" > "$NAMEFILE"
    mpremote connect "$PORT" fs cp "$NAMEFILE" :board_name.txt >/dev/null 2>&1 && ok "this board is called: $BOARD_NAME" || warn "could not write the name to the board"
    rm -f "$NAMEFILE"
else
    mpremote connect "$PORT" fs rm :board_name.txt >/dev/null 2>&1 || true
fi
"$PY" tools/myboards.py add "${BOARD_NAME:-CYD}" board_cyd >/dev/null 2>&1 || true        # "My boards": the Editor lists it in File > New Design

# ---------------------------------------------------------------- 6. demo
say "The demo"
DEMO_OK=0
if [ "$DEMO" = 1 ]; then
    echo "  Loading the demo onto the board: please wait ..."
    if "$PY" tools/deploy.py hello_demo/hello.json hello_demo/demo.py --as demo >/dev/null 2>&1; then
        DEMO_OK=1; ok "The demo is on the board."
    else
        warn "the demo could not be loaded (the files are on the board; try: .venv/bin/python tools/deploy.py hello_demo/hello.json hello_demo/demo.py --as demo)"
    fi
fi

# ---------------------------------------------------------------- 7. the Editor icon
say "The Wattle Editor icon"
make_editor_icon

say "ALL DONE"
if [ "$DEMO" != 1 ] || [ "$DEMO_OK" = 1 ]; then
    echo "  Wattle is installed and the demo is running on the board's screen."
else
    echo "  Wattle is installed, but the demo could not be loaded (see the message above)."
fi
# KEEP THIS LINE IN STEP WITH the manual: the chapter after "Setting up an ESP32" is The Editor.
echo "  Now continue with the manual: the next chapter, The Editor."
