#!/bin/bash

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

GAMEDIR="$SCRIPT_DIR/cavo"
CONFDIR="$GAMEDIR/conf"
mkdir -p "$GAMEDIR" "$CONFDIR" "$GAMEDIR/site-packages" "$GAMEDIR/deps" "$CONFDIR/.cavo" 2>/dev/null

cd "$GAMEDIR" || { echo "Nao foi possivel entrar em $GAMEDIR"; sleep 5; exit 1; }

> "$GAMEDIR/log.txt" 2>/dev/null && exec > >(tee "$GAMEDIR/log.txt") 2>&1

echo "=== CaVo launch ==="
echo "SCRIPT_DIR=$SCRIPT_DIR"
echo "GAMEDIR=$GAMEDIR"
echo "controlfolder=$controlfolder"
echo "PM_CAN_MOUNT=${PM_CAN_MOUNT:-?}"

if [ ! -f "$GAMEDIR/main.py" ]; then
  echo "CaVo: arquivos do jogo nao encontrados em $GAMEDIR"
  sleep 6
  exit 1
fi

export XDG_DATA_HOME="$CONFDIR"
if type bind_directories >/dev/null 2>&1; then
  bind_directories ~/.cavo "$CONFDIR/.cavo" 2>/dev/null || echo "bind_directories falhou (ignorado)"
fi

# Runtime: prefere pygame-ce-runtime (compativel com Mali fbdev) sobre wheel
RUNTIME_PGCE=""
for dir in "$controlfolder/libs" "$GAMEDIR/libs.${DEVICE_ARCH}" "$GAMEDIR"; do
  [ -d "$dir" ] || continue
  RUNTIME_PGCE=$(find "$dir" -maxdepth 1 -name "pygame-ce_*.squashfs" 2>/dev/null | head -1)
  [ -n "$RUNTIME_PGCE" ] && break
done

PYTHON_BIN=""
PYHOME=""
PYLIBPATH="$GAMEDIR:$GAMEDIR/site-packages"   # padrao (fallback wheel)
PGCE_MOUNTED=""

if [ -n "$RUNTIME_PGCE" ] && [ "${PM_CAN_MOUNT:-Y}" != "N" ]; then
  echo "pygame-ce runtime: $RUNTIME_PGCE"
  PGCE_MOUNTED="/tmp/cavo_pgce_runtime"
  mkdir -p "$PGCE_MOUNTED"
  $ESUDO umount "$PGCE_MOUNTED" 2>/dev/null || true
  # Tenta todas as imagens disponiveis (xz e gzip): o kernel pode nao ter xz.
  PGCE_IMAGES="$RUNTIME_PGCE"
  PGCE_GZIP=$(find "$(dirname "$RUNTIME_PGCE")" -maxdepth 1 -name "pygame-ce_*_gzip.squashfs" 2>/dev/null | head -1)
  [ -n "$PGCE_GZIP" ] && PGCE_IMAGES="$PGCE_IMAGES $PGCE_GZIP"
  MOUNT_ERR=""
  for img in $PGCE_IMAGES; do
    echo "tentando montar: $img"
    MOUNT_ERR=$($ESUDO mount -t squashfs "$img" "$PGCE_MOUNTED" 2>&1)
    if [ $? -eq 0 ]; then
      echo "montado OK: $img"
      RUNTIME_PGCE="$img"
      break
    fi
    echo "mount falhou: $MOUNT_ERR"
  done
  if [ -f "$PGCE_MOUNTED/bin/python3" ] || [ -f "$PGCE_MOUNTED/bin/python" ]; then
    for cand in python3 python; do
      if [ -x "$PGCE_MOUNTED/bin/$cand" ]; then PYTHON_BIN="$PGCE_MOUNTED/bin/$cand"; break; fi
    done
    if [ -n "$PYTHON_BIN" ]; then
      PYHOME="$PGCE_MOUNTED"
      export PYTHONHOME="$PYHOME"
      # stdlib do runtime + deps (requests) + gamedir; NAO inclui site-packages (wheel)
      PYLIBPATH="$GAMEDIR:$GAMEDIR/deps:$PGCE_MOUNTED/lib/python3.12"
    fi
  else
    echo "pygame-ce runtime: montagem inutilizavel (sem bin/python)."
    PGCE_MOUNTED=""
  fi
else
  echo "pygame-ce runtime nao encontrado; usando python_3.11 + wheel."
fi

# Fallback: runtime python_3.11 do PortMaster
if [ -z "$PYTHON_BIN" ]; then
  runtime="python_3.11"
  if [ -f "$controlfolder/libs/${runtime}.squashfs" ] && [ "${PM_CAN_MOUNT:-Y}" != "N" ]; then
    PYHOME="/tmp/cavo_python"
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

export LD_LIBRARY_PATH="$controlfolder/libs.${DEVICE_ARCH}:/usr/lib/aarch64-linux-gnu:/lib/aarch64-linux-gnu:$GAMEDIR/libs.${DEVICE_ARCH}:$GAMEDIR/site-packages:$GAMEDIR/site-packages/pygame_ce.libs:${LD_LIBRARY_PATH:-}"
export PYTHONPATH="$PYLIBPATH:${PYTHONPATH:-}"
export SDL_GAMECONTROLLERCONFIG="${sdl_controllerconfig:-}"
export SDL_KMSDRM_REQUIRE_DRM_MASTER=0
export CAVO_PERF=1
export PYTHONUNBUFFERED=1

echo "PYTHON_BIN=$PYTHON_BIN"
echo "PYTHONPATH=$PYTHONPATH"
"$PYTHON_BIN" --version 2>&1
echo "--- teste de import pygame ---"
"$PYTHON_BIN" -c "import pygame; print('pygame', pygame.__version__, pygame.__file__)" 2>&1
RC=$?
echo "import pygame RC=$RC"
if [ $RC -eq 0 ]; then
  echo "--- SDL em uso ---"
  "$PYTHON_BIN" -c "import pygame; print('pygame.get_sdl_version:', pygame.get_sdl_version())" 2>&1
  if [ -z "$PGCE_MOUNTED" ]; then
    SOFILE=$(find "$GAMEDIR/site-packages/pygame" -name "*.so" 2>/dev/null | head -1)
    [ -n "$SOFILE" ] && ldd "$SOFILE" 2>&1 | grep -i "sdl" || true
  fi
fi

if [ $RC -ne 0 ]; then
  echo "pygame nao encontrado para este python."
  echo "Gere deps com: python fetch_deps.py (PC) e copie site-packages/ e deps/."
  [ -n "$PGCE_MOUNTED" ] && $ESUDO umount "$PGCE_MOUNTED" 2>/dev/null || true
  [ -n "$PYHOME" ] && [ "$PYHOME" != "$PGCE_MOUNTED" ] && $ESUDO umount "$PYHOME" 2>/dev/null || true
  sleep 8
  exit 1
fi

if [ -n "${GPTOKEYB:-}" ] && [ -x "$GPTOKEYB" ]; then
  "$GPTOKEYB" "$(basename "$PYTHON_BIN")" &
fi
if type pm_platform_helper >/dev/null 2>&1; then
  pm_platform_helper "$PYTHON_BIN" 2>/dev/null || true
fi

"$PYTHON_BIN" "$GAMEDIR/main.py"
RC=$?

[ -n "$PGCE_MOUNTED" ] && $ESUDO umount "$PGCE_MOUNTED" 2>/dev/null || true
[ -n "$PYHOME" ] && [ "$PYHOME" != "$PGCE_MOUNTED" ] && $ESUDO umount "$PYHOME" 2>/dev/null || true
if type pm_finish >/dev/null 2>&1; then pm_finish 2>/dev/null || true; fi
exit $RC