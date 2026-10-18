#!/bin/bash
# get_wattle.sh -- the ONE-LINE STARTER for Wattle (Linux). A user opens a terminal (Ctrl+Alt+T) and pastes one line that runs this:
#
#       curl -fsSL https://raw.githubusercontent.com/wattle-gui/wattle/main/get_wattle.sh | bash
#
# It downloads the Wattle package, unpacks it into the folder  Wattle  in the user's home folder, moves into that folder and runs
# ./install.sh there. So the user never downloads, unzips, searches for a folder or opens a second terminal: nothing is left to choose.
# (You are welcome to read this file before you run it: it is short, and it only does what is written here.)
#
# For testing without the internet:   WATTLE_ZIP=/path/to/Wattle-0.9.zip  bash get_wattle.sh
# Other settings:  WATTLE_DIR=/where/to/put/it  (default: ~/Wattle)    Everything after the script name is passed on to install.sh.

WATTLE_URL="${WATTLE_URL:-https://github.com/wattle-gui/wattle/releases/latest/download/Wattle-0.9.zip}"
DIR="${WATTLE_DIR:-$HOME/Wattle}"

say()  { printf '\n\033[1m%s\033[0m\n' "$*"; }
fail() { printf '  \033[31mSTOP\033[0m %s\n' "$*"; exit 1; }

say "Wattle: getting the package"
command -v python3 >/dev/null || fail "python3 is not installed. Install it first (Ubuntu / Zorin / Mint:  sudo apt install python3 python3-venv)."
TMP=$(mktemp -d) || fail "cannot make a temporary folder"
trap 'rm -rf "$TMP"' EXIT

if [ -n "$WATTLE_ZIP" ]; then
    [ -f "$WATTLE_ZIP" ] || fail "WATTLE_ZIP names a file that does not exist: $WATTLE_ZIP"
    cp "$WATTLE_ZIP" "$TMP/wattle.zip"
else
    case "$WATTLE_URL" in
        *"to be filled in"*) fail "this starter is not connected to a download address yet (Wattle has not been published).";;
    esac
    echo "  Downloading $WATTLE_URL ..."
    python3 -c 'import sys, urllib.request as u; u.urlretrieve(sys.argv[1], sys.argv[2])' "$WATTLE_URL" "$TMP/wattle.zip" \
        || fail "the download failed. Check your internet connection and try again."
fi

python3 -c 'import sys, zipfile; zipfile.ZipFile(sys.argv[1]).extractall(sys.argv[2])' "$TMP/wattle.zip" "$TMP/unpacked" \
    || fail "the downloaded file is not a valid package."
SRC=$(dirname "$(find "$TMP/unpacked" -name install.sh | head -1)")
[ -f "$SRC/install.sh" ] || fail "the package does not contain install.sh."

if [ -e "$DIR" ]; then
    OLD="$DIR-previous-$(date +%Y%m%d-%H%M%S)"
    mv "$DIR" "$OLD" && echo "  An older Wattle folder was found. It was kept as: $OLD"
fi
mv "$SRC" "$DIR" || fail "could not create $DIR"
chmod +x "$DIR/install.sh" "$DIR/wattle" "$DIR/tools/reset.sh" 2>/dev/null
echo "  Wattle is in: $DIR"

cd "$DIR" || exit 1
# When this script is piped from curl, its standard input is the pipe; the installer must read the keyboard.
if { true < /dev/tty; } 2>/dev/null; then exec bash ./install.sh "$@" < /dev/tty; else exec bash ./install.sh "$@"; fi
