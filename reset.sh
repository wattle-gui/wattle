#!/bin/bash
# Hard-resets the board over USB (pulses RTS/DTR) -- works even when the
# board is stuck in lightsleep. Usage: ./reset.sh [port]
HERE="$(cd "$(dirname "$0")" && pwd)"
SAVED="$(head -n 1 "$HERE/wattle.port" 2>/dev/null)"
esptool --port "${1:-${ESP_PORT:-${SAVED:-/dev/ttyUSB0}}}" --after hard_reset chip_id
