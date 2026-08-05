# Inka

**Turn any device — even a decade-old tablet or a jailbroken Kindle — into a live second screen for your Windows PC, and control the PC (or an Android phone) right back from it.**

Inka is a tiny, self-hosted Windows app. It streams your whole screen, a single window, or a terminal to any device on your network through a plain web page — and, if you want, lets that device **tap and type to control the PC**. No accounts, no cloud, no app store.

It was built around one goal: **make cheap, old, and weird screens useful again** — Android 4.4 tablets, Fire 7s, e-ink Kindles — devices whose ancient browsers choke on modern screen-sharing tools.

---

## Highlights

- **Stream** the full screen, a **single window**, or a **WSL/terminal session** (as crisp text).
- **Works on ancient browsers** via a no-JavaScript `/simple` page — Android 4.4, Kindle Fire, old e-readers.
- **Realtime, no JavaScript** — an MJPEG `⚡ Live` mode that streams continuously with no page reloads (old browsers support it; modern Chrome dropped it).
- **Remote control** — tap the streamed view to click the PC; type text; Enter / Backspace / Esc / Tab / arrows. Works even on the no-JS page.
- **Park off-screen** — keep an app streaming while it's out of your way (don't minimize — minimized windows are blank; parked ones aren't).
- **Android via ADB** — scan/connect (incl. wireless), mirror the phone, tap-control it, or stream the **PC → phone over the USB/adb tunnel**. One-click **scrcpy** launch too.
- **e-ink friendly** — grayscale / dithered B&W, rotation, adjustable refresh, and **change-only** updates so e-ink doesn't flash.
- **Kindle-4-era extension** — a KUAL add-on paints the PC fullscreen with `eips` (no browser at all).

---

## Quick start

**Option A — run it (no build):**
1. Install Python 3 (the `py` launcher). `pillow`, `websockets`, `pywin32` are needed — `py -3.12 -m pip install -r requirements.txt`.
2. Double-click **`run.bat`**.

**Option B — build a standalone exe:**
1. Double-click **`build.bat`** (uses Python **3.12** — see note below).
2. Run **`dist\Inka.exe`**. No Python needed on the target machine.

Then, on any device on the same Wi-Fi, open the URL Inka prints (e.g. `http://192.168.0.50:8000/`).

> **Build note:** build with **Python 3.12**, not 3.14. Python 3.14 embeds Tcl/Tk inside its DLL (`//zipfs:`), which PyInstaller can't package — the resulting exe crashes on startup. `run.bat` (which just runs the script) works on any Python 3.

---

## Using it

### Pick what to stream
In the app: **Mode** = Screen Mirror or Terminal; **Capture** = Full Screen, a specific window, or a `📱 Android` device.

### View it on a device
- **Modern phone/tablet:** open `http://<PC-IP>:8000/` — live WebSocket stream, full frame rate.
- **Old device (Android 4.4, Fire 7, e-reader):** open `http://<PC-IP>:8000/simple` — a no-JavaScript page that works where the modern one can't.

### The `/simple` page (for old browsers)
A tiny toolbar lets you tap to change everything — no URL editing:

`↻ Refresh · slower/faster/manual · fit whole/fill/width · ⚡ Live · text A-/A+ · 🖱 Control · hide bar`

Handy URLs:

| URL | What it does |
|---|---|
| `…/simple` | Auto-refreshing image (safe everywhere) |
| `…/simple?live=1` | **Realtime** MJPEG stream, no reloads |
| `…/simple?tap=1` | **Tap-to-control** (+ keyboard toolbar) |
| `…/simple?live=1&tap=1` | Realtime **and** controllable — the sweet spot for old tablets |
| `…&dw=600` | Set display width for accurate tap mapping (7" portrait) |
| `…&bar=0` | Hide the toolbar for a clean full view |

### Remote control
1. Tick **"Allow remote control (taps click this PC)"** in the app (safety gate, off by default).
2. On the device, enable **🖱 Control** (or use `?tap=1`).
3. Tap the image to click; use the **Type** box and key buttons to type. When streaming an Android device, **Back / Home / Recent** appear too.

### Park an app off-screen (stream it in the background)
Minimizing a window makes it **blank** (Windows stops drawing minimized windows — no tool can capture that). Instead, pick the window and click **"Park app off-screen"** — it moves out of sight but keeps rendering, so it keeps streaming. **"Bring back"** restores it.

### Android (ADB / scrcpy)
- **Scan** / **Connect** (type `ip:port` for wireless ADB) — the device shows up in the Capture dropdown as `📱 <serial>`.
- Select it to **mirror the phone** to your devices; taps control it via `adb input`.
- **PC→Phone (adb)** sets up `adb reverse` so the phone reaches the PC as `localhost:8000` **over USB** — no Wi-Fi needed. Great for flaky old-tablet Wi-Fi.
- **scrcpy** launches [scrcpy](https://github.com/Genymobile/scrcpy) for full-quality phone→PC mirror + control (install it separately, e.g. `winget install Genymobile.scrcpy`).

### Old Kindles (Kindle 4 era) — no browser
See [`kindle-extension/pcscreen`](kindle-extension/pcscreen). It's a KUAL add-on that pulls frames from Inka and paints them **fullscreen with `eips`** — no browser involved. Read its README before using; it manipulates the Kindle UI, so treat it as experimental.

---

## Compatibility

| Device | View | Control |
|---|---|---|
| Modern phone / tablet | ✅ live WebSocket | ✅ tap + keyboard |
| Android 4.4 / Fire 7 (old browser) | ✅ `/simple` (+ `?live=1` MJPEG) | ✅ `?tap=1` (no-JS) |
| Very old e-reader browser | ✅ `/simple` (auto-refresh image) | ➖ depends on browser |
| Jailbroken old Kindle (no browser) | ✅ via the KUAL/`eips` extension | ➖ |

---

## Notes & limitations
- Windows-only host (uses `ImageGrab`, `pywin32`, `eips` is Kindle-side).
- **Minimized windows can't be captured** — use **Park off-screen** instead.
- **GPU-heavy windows** (some browsers/games) may capture blank even when only covered; keep them visible, or use full-screen capture.
- Remote control moves the real mouse/keyboard — it's off by default; only enable it on a trusted network.
- No encryption/auth — intended for your own LAN.

---

## License

[MIT](LICENSE) © 2026 Bhargava Ganti.

scrcpy and ADB are separate projects with their own licenses; Inka just launches/talks to them.
