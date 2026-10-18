#!/usr/bin/env bash
# Wattle Editor (the screen designer for Wattle).
set -u
ROOT="$(cd "$(dirname "$(readlink -f "$0" 2>/dev/null || echo "$0")")" && pwd)"
cd "$ROOT" || exit 1

LOG="${HOME}/.cache/esp32_editor/launch.log"
mkdir -p "$(dirname "$LOG")" 2>/dev/null || true

export QT_QPA_PLATFORM="${QT_QPA_PLATFORM:-xcb}"
export GTK_MODULES="${GTK_MODULES:-}"

notify_error() {
  local message="$1"
  echo "$message" >&2
  if command -v zenity >/dev/null 2>&1; then
    zenity --error --title="Wattle Editor" --text="${message}" --width=420 2>/dev/null || true
  elif command -v notify-send >/dev/null 2>&1; then
    notify-send "Wattle Editor" "${message}" 2>/dev/null || true
  fi
}

# The Wattle installer puts PyQt6 into the private .venv folder next to this Editor folder: use that Python first.
PY="$ROOT/../.venv/bin/python"
[ -x "$PY" ] || PY=python3

if ! "$PY" -c "from PyQt6.QtWidgets import QApplication" 2>/dev/null; then
  notify_error "The Wattle Editor needs PyQt6, and it is missing.

Run the Wattle installer once more (it installs PyQt6):
  open the Wattle folder and run ./install.sh
or, in a terminal:
  pip install PyQt6"
  exit 1
fi

{
  echo "$(date '+%Y-%m-%d %H:%M:%S') Starting Wattle Editor"
} >>"$LOG" 2>/dev/null || true

"$PY" -X faulthandler "$ROOT/ESP32_Editor.py" >>"$LOG" 2>&1
status=$?
{
  echo "$(date '+%Y-%m-%d %H:%M:%S') python exit ${status}"
} >>"$LOG" 2>/dev/null || true

if [[ "${status}" -eq 0 ]]; then
  exit 0
fi
notify_error "Wattle Editor did not start (exit ${status}).

See:
  ${LOG}"
exit "$status"
