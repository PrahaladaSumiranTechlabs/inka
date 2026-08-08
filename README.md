# Inka

**Turn any device — even a decade-old tablet or a jailbroken Kindle — into a live second screen for your PC, and control the PC (or an Android phone) right back from it.**

Inka is a tiny, self-hosted app that runs on **Windows, macOS, and Linux**. It streams your whole screen, a single window, or a terminal to any device on your network through a plain web page — and, if you want, lets that device **tap and type to control the PC**. No accounts, no cloud, no app store.

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

**Windows — run it (no build):**
1. Install Python 3 (the `py` launcher), then `py -3.12 -m pip install -r requirements.txt`.
2. Double-click **`run.bat`**.

**Windows — standalone exe:**
1. Double-click **`build.bat`** (uses Python **3.12** — see note below), or grab `Inka.exe` from [Releases](../../releases).
2. Run **`dist\Inka.exe`**. No Python needed on the target machine.

**macOS / Linux:**
```bash
pip install pillow websockets mss pyautogui
python3 inka.py        # or ./run.sh
```
- **macOS:** grant Terminal/Python **Screen Recording** (to capture) and **Accessibility** (to control) in System Settings → Privacy & Security.
- **Linux:** needs an X11/Wayland session for capture.

Then, on any device on the same Wi-Fi, open the URL Inka prints (e.g. `http://192.168.0.50:8000/`).

> **Windows build note:** build with **Python 3.12**, not 3.14. Python 3.14 embeds Tcl/Tk inside its DLL (`//zipfs:`), which PyInstaller can't package — the resulting exe crashes on startup. `run.bat` (which just runs the script) works on any Python 3.

---

## Using it

### Pick what to stream
In the app: **Mode** = Screen Mirror or Terminal; **Capture** = Full Screen, a **specific monitor** (`🖥 Display N` — shown when you have more than one, e.g. a virtual/second display), a specific window, or a `📱 Android` device.

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

### Multiple devices, each a different screen
Every device can choose **its own** source — so three Kindles can show three different things at once, and Inka captures them all in parallel.

- On a device, open the picker: **`http://<PC-IP>:8000/simple?pick=1`** (or tap **📺 Screens** in the toolbar) and choose Full Screen, a specific window, or an Android device.
- Or link directly: `…/simple?src=win:<hwnd>` / `…/simple?src=screen` / `…/simple?src=adb:<serial>`.
- Control (`?tap=1`) is per-source too — each device controls only what it's showing.

No virtual-display driver required. (A true virtual-monitor mode — real extra desktops via a signed driver — is on the roadmap; see below.)

### Mirror vs. true second screen
Inka **streams a source** you already have — your whole screen, one window, or a terminal. That's *mirroring*, not an *extended* desktop: by itself, your Kindle/tablet can't be a genuine extra monitor that you drag windows onto.

To get a **real second screen**, pair Inka with a **virtual display**, then point Inka's **Full Screen** capture at it (or use `?src=screen`):

- **macOS — with [BetterDisplay](https://github.com/waydabber/BetterDisplay) (free):**
  1. Install BetterDisplay (`brew install --cask betterdisplay`).
  2. BetterDisplay menu → **Create New Display → Virtual Display** (pick a resolution that fits your device, e.g. 1024×768 for a 7″ tablet).
  3. System Settings → Displays → set the virtual display to **Extended** (not Mirrored) and arrange it.
  4. In Inka, grant **Screen Recording**, then pick the virtual display from **Capture → 🖥 Display N** (each monitor is listed with its resolution). Open `…/simple` on your device. Now drag any window onto the virtual display and it appears on the device — a true second screen you can also **tap to control**.
- **Windows — with an IddCx virtual display driver (free, open source):**
  1. Install a virtual display driver such as [Virtual-Display-Driver](https://github.com/VirtualDrivers/Virtual-Display-Driver) (adds a headless monitor Windows treats as real).
  2. Settings → System → Display → set the new display to **Extend**.
  3. In Inka, pick the virtual display from **Capture → 🖥 Display N** (each monitor is listed with its resolution), then open `…/simple` on the device and drag windows onto it.
- **Linux:** add a dummy output (e.g. an `xrandr --addmode` virtual head, or a "dummy" X driver), set it Extended, then point Inka's Full Screen capture at it.

A built-in, signed virtual-monitor mode (no third-party driver) is on the roadmap.

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

## Platform support

| Capability | Windows | macOS | Linux |
|---|---|---|---|
| Full-screen streaming (`mss`) | ✅ | ✅ | ✅ (X11/Wayland) |
| `/simple`, MJPEG live, WebSocket | ✅ | ✅ | ✅ |
| Remote control (tap/keyboard) | ✅ `pywin32` | ✅ `pyautogui`\* | ✅ `pyautogui`\* |
| Terminal mode | ✅ WSL tmux | ✅ native tmux | ✅ native tmux |
| **Single-window capture** | ✅ `pywin32` | ✅ `Quartz` | ✅ `wmctrl`\*\* |
| **Park off-screen** | ✅ | ➖ | ➖ |
| Android via ADB / scrcpy | ✅ | ✅ | ✅ |

\* macOS needs Screen Recording + Accessibility permissions.
\*\* Linux single-window capture needs `wmctrl` (`sudo apt install wmctrl`) and an X11 session; it crops the window's region from the full grab, so the window must be on-screen and unobscured. Park-off-screen remains Windows-only.

> The core (stream + view + control + terminal + Android) runs on all three, and single-window capture now works on macOS (Quartz) and Linux (wmctrl) too. Park-off-screen still uses Windows-specific APIs. **Windows is the most tested platform; macOS/Linux are structured and welcome testers/PRs.**

## Notes & limitations
- **Minimized windows can't be captured** — use **Park off-screen** (Windows) instead, or keep the window visible.
- **GPU-heavy windows** (some browsers/games) may capture blank even when only covered; keep them visible, or use full-screen capture.
- Remote control moves the real mouse/keyboard — it's off by default; only enable it on a trusted network.
- No encryption/auth — intended for your own LAN.

---

## License

[MIT](LICENSE) © 2026 Bhargava Ganti.

scrcpy and ADB are separate projects with their own licenses; Inka just launches/talks to them.
