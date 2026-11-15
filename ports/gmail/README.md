## Notes

Thanks to the [pygame](https://www.pygame.org) community for pygame-ce, the toolkit this client is drawn with, and to the [PortMaster](https://portmaster.games) project for the runtime and the packaging rules this port follows.

Gmail here is an independent IMAP/SMTP client written for OddHub. It is not a Google product, ships no Google code or artwork, and works with any provider that speaks IMAP and SMTP, Gmail included. Messages are read and sent straight from your own account over the standard mail protocol, so nothing goes through a browser and there is no account lock-in.

The whole interface is drawn at 640x480 and scaled to the screen, which keeps the same readable layout on a 480x320 device and on a 1280x720 one. There is a demo mode with sample messages that needs no account and no network, so the port can be tried before any credential is typed in.

## Controls

| Key | Action |
|--|--|
| D-Pad | Move selection |
| A | Open email / activate |
| B | Back |
| X | Toggle star |
| Y | Next folder |
| L1 / R1 | Scroll list / message |
| L2 | Toggle on-screen keyboard |
| R2 | Delete email (asks first) |
| Start | Settings |
| Select+Start | Quit |

## Dependencies

The port runs on the PortMaster `python_3.11` runtime and needs pygame. Two ways to get pygame on the device:

1. Copy the `pygame-ce_*.squashfs` runtime into `/opt/system/Tools/PortMaster/libs/`. The launcher mounts it automatically and uses its interpreter.
2. Without that runtime, generate the wheel on a PC with `python fetch_deps.py` and copy the resulting `site-packages/` folder into `ports/gmail/gmail/`.

No other dependency is used: IMAP and SMTP come from the Python standard library.
