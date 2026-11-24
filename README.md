# ScreenLink

See and control your Windows PC from your iPhone over Wi-Fi. No internet needed, only the same network
(same Wi-Fi, or the PC joined to the iPhone's hotspot).

## Use it
1. On the PC run `ScreenLink-PC-<version>.exe`. A small window shows the address and a 6 digit PIN.
   If Windows asks about the firewall, tick **both** Private and Public (hotspots are often Public).
2. On the iPhone open ScreenLink, tap **Scan this network**, tap your PC and type the PIN.
   Without the app: open the address from the PC window in Safari.

## Controls
- Tap: click. Hold: right click. Two finger tap: right click.
- One finger drag: drag with the button shown on **Drag** (Left, Right, Middle for panning in Revit/AutoCAD, Hover).
- Pinch: zoom the view on the phone. **2F: Wheel** turns two finger up/down into the mouse wheel (zoom in Revit).
- **Keys** opens the keyboard; buttons for Save, Esc, Enter, Undo and more.

## Build
A push to `main` builds `ScreenLink-<version>.ipa` (unsigned, sign with ipakill or Sideloadly) and
`ScreenLink-PC-<version>.exe` and publishes them as a release. Bump `VERSION` and add a line on top
of RELEASE_NOTES.md for each release.

## Layout
- `pc/screenlink.py`: the PC server (Python, mss + Pillow, Windows SendInput for mouse and keys).
- `pc/viewer.html`: the viewer page served by the PC; the iPhone app shows it in a web view.
- `ios/`: SwiftUI app (XcodeGen), finds PCs by asking every address of the local network for `/hello`.
