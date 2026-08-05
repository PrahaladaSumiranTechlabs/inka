#!/bin/sh
# PC Second Screen - background refresh loop.
# Uses only basic shell features; finds eips/wget by full path (no which/command).
LOG=/mnt/us/pcscreen.log
echo "$(date 2>/dev/null) loop.sh RUNNING pid=$$" >> "$LOG"
echo $$ > /tmp/pcscreen.pid

BASE="$(cd "$(dirname "$0")/.." && pwd)"
[ -f "$BASE/config" ] && . "$BASE/config"
: ${IP:=192.168.0.189}
: ${PORT:=8000}
: ${INTERVAL:=5}
: ${WIDTH:=600}
: ${HEIGHT:=800}
: ${EXIT_AFTER:=10}   # consecutive failed checks before auto-releasing the UI

IMG=/tmp/pcscreen.png
URL="http://$IP:$PORT/frame?png=1&w=$WIDTH&h=$HEIGHT"
IDURL="http://$IP:$PORT/frameid"

# Locate eips (fullscreen paint) by common paths, then bare name as a fallback.
EIPS=""
for p in /usr/sbin/eips /usr/bin/eips /usr/local/bin/eips; do
    [ -x "$p" ] && { EIPS="$p"; break; }
done
[ -z "$EIPS" ] && EIPS="eips"

# Locate wget (or busybox wget).
WGET=""
for p in /usr/bin/wget /bin/wget /usr/local/bin/wget /usr/sbin/wget; do
    [ -x "$p" ] && { WGET="$p"; break; }
done
if [ -z "$WGET" ]; then
    for b in /usr/bin/busybox /bin/busybox; do
        [ -x "$b" ] && { WGET="$b wget"; break; }
    done
fi
[ -z "$WGET" ] && WGET="wget"

echo "$(date 2>/dev/null) tools: EIPS=$EIPS  WGET=$WGET" >> "$LOG"

log()   { echo "$(date 2>/dev/null) $*" >> "$LOG"; }
paint() { $EIPS -g "$1" >> "$LOG" 2>&1; }
msg()   { $EIPS 1 1 "$1" >> "$LOG" 2>&1; }

# Freeze the Kindle UI so it stops redrawing over our image. Called ONCE, only
# after the first successful frame - so an unreachable PC never locks you out.
freeze_ui() {
    log "freezing Kindle UI (reboot to exit)..."
    stop lab126_gui            >> "$LOG" 2>&1
    stop framework             >> "$LOG" 2>&1
    initctl stop framework     >> "$LOG" 2>&1
    /etc/init.d/framework stop >> "$LOG" 2>&1
    killall -STOP cvm          >> "$LOG" 2>&1
    killall -STOP framework    >> "$LOG" 2>&1
}

restore_ui() {
    log "restoring Kindle UI..."
    killall -CONT cvm           >> "$LOG" 2>&1
    /etc/init.d/framework start >> "$LOG" 2>&1
    start lab126_gui            >> "$LOG" 2>&1
}

msg "PC Screen: connecting to $IP:$PORT ..."

LASTID=""
FROZEN=""
FAILS=0
while true; do
    # Keep the device/Wi-Fi awake (powerd can re-enable sleep after freeze).
    lipc-set-prop com.lab126.powerd preventScreenSaver 1 2>/dev/null
    lipc-set-prop com.lab126.cmd wirelessEnable 1 2>/dev/null

    ID="$($WGET -q -O - "$IDURL" 2>>"$LOG")"
    if [ -z "$ID" ]; then
        FAILS=$((FAILS + 1))
        log "no frameid ($FAILS/$EXIT_AFTER) - PC app running? firewall? right IP?"
        [ -z "$FROZEN" ] && msg "PC not reachable at $IP:$PORT"
    elif [ "$ID" != "$LASTID" ]; then
        rm -f "$IMG"   # busybox wget refuses to overwrite an existing file
        if $WGET -q -O "$IMG" "$URL" 2>>"$LOG" && [ -s "$IMG" ]; then
            paint "$IMG"
            LASTID="$ID"
            FAILS=0
            log "painted id=$ID"
            # After the first good frame, freeze the UI so the image persists.
            if [ "$STOP_FRAMEWORK" = "1" ] && [ -z "$FROZEN" ]; then
                sleep 1
                freeze_ui
                FROZEN=1
                paint "$IMG"   # repaint in case the UI flashed while stopping
            fi
        else
            FAILS=$((FAILS + 1))
            log "frame fetch failed ($FAILS/$EXIT_AFTER)"
        fi
    else
        FAILS=0   # reachable, just no change
    fi

    # Auto-release: if the PC stays unreachable, restore the Kindle UI and exit,
    # so you can quit just by closing the PC app (no reboot needed).
    if [ "$FROZEN" = "1" ] && [ "$FAILS" -ge "$EXIT_AFTER" ]; then
        log "PC unreachable for $FAILS checks - releasing Kindle and exiting."
        restore_ui
        rm -f /tmp/pcscreen.pid
        exit 0
    fi

    sleep "$INTERVAL"
done
