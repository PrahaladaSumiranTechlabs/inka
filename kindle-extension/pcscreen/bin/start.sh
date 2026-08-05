#!/bin/sh
# PC Second Screen - START
# This firmware's shell has no nohup/setsid/command, so we detach the loop with
# a plain background subshell, and use only basic shell features.
LOG=/mnt/us/pcscreen.log

BASE="$(cd "$(dirname "$0")/.." && pwd)"
[ -f "$BASE/config" ] && . "$BASE/config"
: ${STOP_FRAMEWORK:=0}

{
    echo "=========== START $(date 2>/dev/null) ==========="
    echo "BASE=$BASE"
} >> "$LOG" 2>&1

# Stop any previous loop.
if [ -f /tmp/pcscreen.pid ]; then
    kill "$(cat /tmp/pcscreen.pid)" 2>/dev/null
    rm -f /tmp/pcscreen.pid
fi

# Keep awake (ignore failures on models without lipc).
lipc-set-prop com.lab126.powerd preventScreenSaver 1 2>/dev/null

# NOTE: the UI is frozen by loop.sh only AFTER the first successful frame, so a
# wrong IP / unreachable PC can never lock you out of the Kindle.

# Detach the loop with a double-background subshell (no nohup/setsid needed).
( sh "$BASE/bin/loop.sh" </dev/null >> "$LOG" 2>&1 & )

echo "loop launched (background subshell)" >> "$LOG"
