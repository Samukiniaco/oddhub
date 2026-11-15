## Notes

Thanks to the [pygame](https://www.pygame.org) community for pygame-ce, the toolkit this manager is drawn with, and to the [PortMaster](https://portmaster.games) project for the runtime and the packaging rules this port follows.

OddHub is the front door of the OddHub collection: it lists every port of the collection that is installed on the device, says which ones are there and which are not, and launches the one you pick. It reads the port metadata the same way PortMaster does, so the list stays in sync with whatever is actually on the card.

The interface is drawn at 640x480 and scaled to the screen, and the whole thing runs on the PortMaster `python_3.11` runtime.

## Controls

| Key | Action |
|--|--|
| D-Pad | Move selection |
| A | Open port |
| Y | Details |
| B | Back / quit |
| Select+Start | Quit |

## Dependencies

The port runs on the PortMaster `python_3.11` runtime and needs pygame. Two ways to get pygame on the device:

1. Copy the `pygame-ce_*.squashfs` runtime into `/opt/system/Tools/PortMaster/libs/`. The launcher mounts it automatically and uses its interpreter.
2. Without that runtime, generate the wheel on a PC and copy the result into the port folder:

```bash
cd oddhub
python fetch_deps.py
```

Then copy the generated `site-packages/` folder to `ports/oddhub/oddhub/` on the device.
