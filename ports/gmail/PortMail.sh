#!/bin/bash
# PORTMASTER: gmail.zip, PortMail.sh

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

source $controlfolder/control.txt
[ -f "${controlfolder}/mod_${CFW_NAME}.txt" ] && source "${controlfolder}/mod_${CFW_NAME}.txt"
get_controls

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
GAMEDIR="$SCRIPT_DIR/gmail"
cd "$GAMEDIR" || exit 1

> "$GAMEDIR/log.txt" && exec > >(tee "$GAMEDIR/log.txt") 2>&1

mkdir -p "$GAMEDIR/conf/gmail" 2>/dev/null
bind_directories "${XDG_DATA_HOME:-$HOME/.local/share}/oddhub/gmail" "$GAMEDIR/conf/gmail" 2>/dev/null || true

# Runtime com pygame (preferido): pygame-ce empacotado em squashfs.
PYTHON_BIN=""
PYHOME=""
PYLIBPATH="$GAMEDIR:$GAMEDIR/site-packages"

RUNTIME_PGCE=""
for dir in "$controlfolder/libs" "$GAMEDIR/libs.${DEVICE_ARCH}" "$GAMEDIR"; do
  [ -d "$dir" ] || continue
  RUNTIME_PGCE=$(find "$dir" -maxdepth 1 -name "pygame-ce_*.squashfs" 2>/dev/null | head -1)
  [ -n "$RUNTIME_PGCE" ] && break
done

if [ -n "$RUNTIME_PGCE" ] && [ "${PM_CAN_MOUNT:-Y}" != "N" ]; then
  PGCE_MOUNTED="/tmp/portmail_pgce"
  mkdir -p "$PGCE_MOUNTED"
  $ESUDO umount "$PGCE_MOUNTED" 2>/dev/null || true
  for img in "$RUNTIME_PGCE" "$(dirname "$RUNTIME_PGCE")/$(basename "$RUNTIME_PGCE" .squashfs)_gzip.squashfs"; do
    [ -f "$img" ] || continue
    if $ESUDO mount -t squashfs "$img" "$PGCE_MOUNTED" 2>/dev/null; then
      for cand in python3 python; do
        if [ -x "$PGCE_MOUNTED/bin/$cand" ]; then PYTHON_BIN="$PGCE_MOUNTED/bin/$cand"; break; fi
      done
      [ -n "$PYTHON_BIN" ] && export PYTHONHOME="$PGCE_MOUNTED"
      break
    fi
  done
  [ -z "$PYTHON_BIN" ] && PGCE_MOUNTED=""
fi

# Fallback: runtime python_3.11 do PortMaster.
if [ -z "$PYTHON_BIN" ]; then
  runtime="python_3.11"
  if [ ! -f "$controlfolder/libs/${runtime}.squashfs" ]; then
    $ESUDO $controlfolder/harbourmaster --quiet --no-check runtime_check "${runtime}.squashfs"
  fi
  if [ -f "$controlfolder/libs/${runtime}.squashfs" ] && [ "${PM_CAN_MOUNT:-Y}" != "N" ]; then
    PYHOME="/tmp/portmail_python"
    mkdir -p "$PYHOME"
    $ESUDO umount "$PYHOME" 2>/dev/null || true
    if $ESUDO mount "$controlfolder/libs/${runtime}.squashfs" "$PYHOME" 2>/dev/null; then
      for cand in python3 python3.11 python; do
        if [ -x "$PYHOME/bin/$cand" ]; then PYTHON_BIN="$PYHOME/bin/$cand"; break; fi
      done
      [ -n "$PYTHON_BIN" ] && export PYTHONHOME="$PYHOME"
    else
      PYHOME=""
    fi
  fi
fi

if [ -z "$PYTHON_BIN" ]; then
  for cand in python3 python; do
    if command -v "$cand" >/dev/null 2>&1; then PYTHON_BIN="$(command -v "$cand")"; break; fi
  done
fi

if [ -z "$PYTHON_BIN" ]; then
  pm_show_error "Nenhum interpretador Python encontrado. Instale o runtime python_3.11 do PortMaster." --title "Python ausente"
  exit 1
fi

export PYTHONPATH="$PYLIBPATH:${PYTHONPATH:-}"
export LD_LIBRARY_PATH="$controlfolder/libs.${DEVICE_ARCH}:$GAMEDIR/site-packages:$GAMEDIR/site-packages/pygame_ce.libs:${LD_LIBRARY_PATH:-}"
export SDL_GAMECONTROLLERCONFIG="${sdl_controllerconfig:-}"
export SDL_KMSDRM_REQUIRE_DRM_MASTER=0
export PYTHONUNBUFFERED=1

"$PYTHON_BIN" -c "import pygame; print('pygame', pygame.version.ver)" 2>&1
if [ $? -ne 0 ]; then
  pm_show_error "pygame nao encontrado. Copie a pasta site-packages gerada por fetch_deps.py para o port." --title "pygame ausente"
  exit 1
fi

$GPTOKEYB2 "portmail" -c "$GAMEDIR/gmail.ini" > /dev/null 2>&1 &

pm_platform_helper "$PYTHON_BIN" 2>/dev/null || true

"$PYTHON_BIN" -m portmail
RC=$?

[ -n "$PYHOME" ] && [ "$PYHOME" != "$PGCE_MOUNTED" ] && $ESUDO umount "$PYHOME" 2>/dev/null || true
[ -n "$PGCE_MOUNTED" ] && $ESUDO umount "$PGCE_MOUNTED" 2>/dev/null || true
pm_finish
exit $RC
