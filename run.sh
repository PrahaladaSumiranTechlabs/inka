#!/usr/bin/env bash
# Launch Inka on macOS / Linux.
#   chmod +x run.sh   (once)
#   ./run.sh
#
# Needs Python 3 and: pip install pillow websockets mss pyautogui
# (On Linux, screen capture needs an X11/Wayland session; grant Accessibility +
#  Screen Recording permission on macOS for capture and control to work.)
cd "$(dirname "$0")"
exec python3 inka.py
