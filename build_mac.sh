#!/bin/sh
# Build HotkeyTimer.app on macOS (no Python needed on the target Mac)
# Output: dist/HotkeyTimer.app and dist/HotkeyTimer-mac-<arm64|intel>.zip
set -e
cd "$(dirname "$0")"

python3 -m venv .venv
. .venv/bin/activate
python -m pip install --quiet -r requirements.txt pyinstaller

python -m PyInstaller --noconfirm --clean --windowed \
    --name HotkeyTimer \
    --osx-bundle-identifier com.paosong789.hotkeytimer \
    --hidden-import pynput.keyboard._darwin \
    --hidden-import pynput.mouse._darwin \
    hotkey_timer.py

if [ "$(uname -m)" = "arm64" ]; then ARCH=arm64; else ARCH=intel; fi
ditto -c -k --keepParent dist/HotkeyTimer.app "dist/HotkeyTimer-mac-$ARCH.zip"
echo "Done: dist/HotkeyTimer-mac-$ARCH.zip"
