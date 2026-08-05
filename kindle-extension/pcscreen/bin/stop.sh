#!/bin/sh
# PC Second Screen - STOP
# Stops the refresh loop and restores the normal Kindle UI.

BASE="$(cd "$(dirname "$0")/.." && pwd)"
[ -f "$BASE/config" ] && . "$BASE/config"
: ${STOP_FRAMEWORK:=0}

LOG=/mnt/us/pcscreen.log
echo "=========== STOP $(date 2>/dev/null) ===========" >> "$LOG"

# Kill the loop (by pidfile, plus a name-based fallback).
if [ -f /tmp/pcscreen.pid ]; then
    kill "$(cat /tmp/pcscreen.pid)" 2>/dev/null
    rm -f /tmp/pcscreen.pid
fi
pkill -f "pcscreen/bin/loop.sh" 2>/dev/null

# Allow the screensaver again.
lipc-set-prop com.lab126.powerd preventScreenSaver 0 2>/dev/null

# Resume/restart the Kindle UI (try every method; harmless ones just log).
killall -CONT cvm           >> "$LOG" 2>&1
killall -CONT framework     >> "$LOG" 2>&1
start lab126_gui            >> "$LOG" 2>&1
start framework            >> "$LOG" 2>&1
initctl start framework     >> "$LOG" 2>&1
/etc/init.d/framework start >> "$LOG" 2>&1

# Clear the screen.
/usr/sbin/eips -c 2>/dev/null || eips -c 2>/dev/null
echo "stopped." >> "$LOG"
