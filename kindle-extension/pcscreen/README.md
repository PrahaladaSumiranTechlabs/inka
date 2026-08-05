# PC Second Screen — Kindle 4 / older-device extension

A KUAL extension that turns a **jailbroken older Kindle** (Kindle 4, Keyboard, Touch, basic PW)
into a **fullscreen** second display for your PC — **no browser, no chrome**.

It pulls a frame from the Screen Mirror Server (running on your PC) and paints it directly
to the e-ink screen with `eips`. The PC resizes each frame to your Kindle's exact resolution,
so it fills the whole screen automatically.

## Why this instead of the browser?
The old Kindle browser can't do WebSocket, shows its own toolbars, and can't go truly
fullscreen. Painting the framebuffer with `eips` gives an edge-to-edge, chrome-free image —
the classic "Kindle dashboard" technique.

## Requirements
- A **jailbroken** Kindle with **KUAL** installed.
- `eips` (present on essentially all Kindles) — or `fbink` if you've installed it.
- The **Screen Mirror Server** running on your PC (this project's `ScreenMirrorServer.exe`),
  set to **Screen Mirror** or **Window** capture (image mode — the extension reads `/frame`).
- Both devices on the **same Wi-Fi**.

## Install
1. Connect the Kindle to your PC by USB (it shows up as a drive).
2. Copy the whole **`pcscreen`** folder into the Kindle's **`extensions`** folder:
   `<KindleDrive>/extensions/pcscreen/`
3. Open **`pcscreen/config`** in a text editor and set:
   - `IP` = your PC's IP (e.g. `192.168.0.189`) — a **static IP / DHCP reservation** is best.
   - `WIDTH` / `HEIGHT` = your Kindle's resolution (Kindle 4 = `600` x `800`).
   - `INTERVAL` = seconds between refreshes (10–20 is comfortable on e-ink).
4. **Eject** the Kindle.
5. Open **KUAL** → you'll see **"PC Screen: START"** and **"PC Screen: STOP"**.

## Use
- On the PC: run the Screen Mirror Server, pick what to stream (a window, or the screen).
- On the Kindle: **KUAL → PC Screen: START**. The PC image appears fullscreen and refreshes
  every `INTERVAL` seconds.
- To stop: **KUAL → PC Screen: STOP** (or just reboot the Kindle).

## Tuning
- **Rotation**: use the **Rotation** control in the PC app (it rotates the actual frame),
  then set `WIDTH`/`HEIGHT` to match how you hold the Kindle (e.g. `800` x `600` for landscape).
- **Cleaner display**: once it works, set `STOP_FRAMEWORK=1` in `config` to hide the Kindle UI
  while streaming. Start with `0` (safer) on the first try.

## Troubleshooting (older devices vary a lot)
- **Blank screen / nothing shows**: set `STOP_FRAMEWORK=0`. Some models don't have
  `stop lab126_gui`; the script also tries `framework` and `killall cvm`, but if the UI
  won't stop, run with it off.
- **"PC not reachable"**: check the IP in `config`, that the PC app is running, and that
  Windows Firewall allows port 8000. Test `http://<IP>:8000/simple` in the Kindle browser first.
- **Image looks stretched or off-size**: fix `WIDTH`/`HEIGHT` to your exact screen resolution.
- **`eips` not found**: your firmware may use a different path; try installing `fbink`.
- A **reboot always restores** the normal Kindle UI, so it's safe to experiment.

> Note: `eips`/framework commands differ across Kindle generations. This is a starting point
> tuned for the Kindle-4 era; you may need to tweak `bin/start.sh` for your exact model.
