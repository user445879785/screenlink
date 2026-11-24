# screenlink: project memory

ScreenLink: see and control the Windows PC from the iPhone over the local network, no internet.
PC side `pc/` (Python server, built to an .exe by PyInstaller), iPhone side `ios/` (SwiftUI + WKWebView
showing `pc/viewer.html` served by the PC). See README.md.

## Rules from the user (always)
- Always merge changes into `main` (not left in a branch or PR): a push to `main` builds and publishes.
- Every release file ends with its version: `ScreenLink-<version>.ipa`, `ScreenLink-PC-<version>.exe`.
- Bump `VERSION` and add a line on top of RELEASE_NOTES.md for each release.

## Notes
- No Swift compiler in the cloud sessions: check Swift changes with the workflow (workflow_dispatch on a branch).
- The server runs on Linux for testing (`xvfb-run python3 pc/screenlink.py --console`); input is a no-op there.
- Port 8765, PIN in %APPDATA%\ScreenLink\settings.json. `/hello` needs no PIN (used by the iPhone scan).
