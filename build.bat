@echo off
rem Build a standalone HotkeyTimer.exe (no Python needed on the target PC)
rem Output: dist\HotkeyTimer.exe
cd /d "%~dp0"
python -m pip install --quiet -r requirements.txt pyinstaller
python -m PyInstaller --noconfirm --clean --onefile --windowed ^
    --name HotkeyTimer ^
    --hidden-import pynput.keyboard._win32 ^
    --hidden-import pynput.mouse._win32 ^
    hotkey_timer.py
echo.
echo Done: %~dp0dist\HotkeyTimer.exe
pause
