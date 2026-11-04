#!/bin/bash
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
GAMEDIR="$SCRIPT_DIR/whatsapp"
cd "$GAMEDIR" || exit 1
export PYTHONPATH="$GAMEDIR:$GAMEDIR/core:${PYTHONPATH:-}"
python3 "$GAMEDIR/main.py"
