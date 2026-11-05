#!/bin/bash
# Launcher do port PortMail (OddHub) para PortMaster.

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
XDG_DATA_HOME=${XDG_DATA_HOME:-$HOME/.local/share}

if [ -d "/opt/system/Tools/PortMaster/" ]; then
  controlfolder="/opt/system/Tools/PortMaster"
elif [ -d "/opt/tools/PortMaster/" ]; then
  controlfolder="/opt/tools/PortMaster"
elif [ -d "$XDG_DATA_HOME/PortMaster/" ]; then
  controlfolder="$XDG_DATA_HOME/PortMaster"
else
  controlfolder="/roms/ports/PortMaster"
fi

if [ -f "$controlfolder/control.txt" ]; then
  source "$controlfolder/control.txt"
else
  : "${ESUDO:=}"
  : "${directory:=$(dirname "$SCRIPT_DIR")}"
  get_controls() { :; }
fi
[ -f "${controlfolder}/mod_${CFW_NAME}.txt" ] && source "${controlfolder}/mod_${CFW_NAME}.txt" 2>/dev/null
get_controls 2>/dev/null || true

GAMEDIR="$SCRIPT_DIR/gmail"
CONFDIR="$SCRIPT_DIR/conf"
mkdir -p "$GAMEDIR" "$CONFDIR" "$CONFDIR/data" 2>/dev/null

cd "$GAMEDIR" || { echo "Nao foi possivel entrar em $GAMEDIR"; sleep 5; exit 1; }

> "$CONFDIR/log.txt" 2>/dev/null && exec > >(tee "$CONFDIR/log.txt") 2>&1

echo "=== OddHub PortMail launch ==="
echo "SCRIPT_DIR=$SCRIPT_DIR"
echo "GAMEDIR=$GAMEDIR"
echo "controlfolder=$controlfolder"

if [ ! -f "$GAMEDIR/main.py" ]; then
  echo "PortMail: arquivos do port nao encontrados em $GAMEDIR"
  sleep 6
  exit 1
fi

# Dados persistentes
export GMAIL_DATA="${GMAIL_DATA:-$CONFDIR/data}"

# Runtime python_3.11 do PortMaster
PYTHON_BIN=""
PYHOME=""
PYLIBPATH="$GAMEDIR:$GAMEDIR/site-packages"
runtime="python_3.11"

if [ -f "$controlfolder/libs/${runtime}.squashfs" ] && [ "${PM_CAN_MOUNT:-Y}" != "N" ]; then
  PYHOME="/tmp/oddhub_portmail_python"
  mkdir -p "$PYHOME"
  $ESUDO umount "$PYHOME" 2>/dev/null || true
  if $ESUDO mount "$controlfolder/libs/${runtime}.squashfs" "$PYHOME" 2>/dev/null; then
    for cand in python3 python3.11 python; do
      if [ -x "$PYHOME/bin/$cand" ]; then PYTHON_BIN="$PYHOME/bin/$cand"; break; fi
    done
    [ -n "$PYTHON_BIN" ] && export PYTHONHOME="$PYHOME"
  else
    echo "Falha ao montar $runtime."
    PYHOME=""
  fi
fi

if [ -z "$PYTHON_BIN" ]; then
  for cand in python3 python python3.11; do
    if command -v "$cand" >/dev/null 2>&1; then PYTHON_BIN="$(command -v "$cand")"; break; fi
  done
  PYLIBPATH="$GAMEDIR:$GAMEDIR/site-packages"
fi

if [ -z "$PYTHON_BIN" ]; then
  echo "Nenhum python encontrado."
  sleep 5
  exit 1
fi

export LD_LIBRARY_PATH="$controlfolder/libs.${DEVICE_ARCH}:/usr/lib/aarch64-linux-gnu:/lib/aarch64-linux-gnu:$GAMEDIR/libs.${DEVICE_ARCH}:$GAMEDIR/site-packages:${LD_LIBRARY_PATH:-}"
export PYTHONPATH="$PYLIBPATH:${PYTHONPATH:-}"
export SDL_GAMECONTROLLERCONFIG="${sdl_controllerconfig:-}"
export SDL_KMSDRM_REQUIRE_DRM_MASTER=0
export PYTHONUNBUFFERED=1

echo "PYTHON_BIN=$PYTHON_BIN"
"$PYTHON_BIN" --version 2>&1
echo "--- teste de import pygame ---"
"$PYTHON_BIN" -c "import pygame; print('pygame', pygame.version.ver, pygame.__file__)" 2>&1
RC=$?
echo "import pygame RC=$RC"
if [ $RC -ne 0 ]; then
  echo "pygame nao encontrado para este python."
  [ -n "$PYHOME" ] && $ESUDO umount "$PYHOME" 2>/dev/null || true
  sleep 8
  exit 1
fi

# Backend: 'imap' se configurado, senao demo.
if [ -z "${GMAIL_BACKEND:-}" ]; then
  if [ -f "$GAMEDIR/conf/data/config.json" ]; then
    GMAIL_BACKEND="imap"
  else
    GMAIL_BACKEND="demo"
  fi
fi
export GMAIL_BACKEND

EXTRA_ARGS=""
if [ "${GMAIL_WINDOWED:-0}" != "1" ]; then
  EXTRA_ARGS="--fullscreen"
fi

if type pm_platform_helper >/dev/null 2>&1; then
  pm_platform_helper "$PYTHON_BIN" 2>/dev/null || true
fi

"$PYTHON_BIN" "$GAMEDIR/main.py" --backend "$GMAIL_BACKEND" $EXTRA_ARGS
RC=$?

[ -n "$PYHOME" ] && $ESUDO umount "$PYHOME" 2>/dev/null || true
if type pm_finish >/dev/null 2>&1; then pm_finish 2>/dev/null || true; fi
exit $RC
