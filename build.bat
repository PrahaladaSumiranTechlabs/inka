@echo off
rem Build a standalone Inka.exe with PyInstaller.
rem IMPORTANT: build with Python 3.12 (NOT 3.14 — 3.14 embeds Tcl in the DLL and
rem PyInstaller can't package it, so the exe crashes on startup).
setlocal
echo Installing build dependencies (Python 3.12)...
py -3.12 -m pip install --upgrade pip
py -3.12 -m pip install pyinstaller pillow websockets pywin32
echo Building Inka.exe...
py -3.12 -m PyInstaller --noconfirm --onefile --windowed --name=Inka ^
  --add-data "mirrorindex.html;." ^
  --hidden-import=PIL --hidden-import=websockets --hidden-import=asyncio ^
  --hidden-import=win32gui --hidden-import=win32ui --hidden-import=win32api ^
  --hidden-import=win32con --hidden-import=pywintypes ^
  inka.py
rmdir /s /q build 2>nul
del /q Inka.spec 2>nul
echo.
echo Done. See dist\Inka.exe
endlocal
