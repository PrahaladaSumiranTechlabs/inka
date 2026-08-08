import asyncio
import websockets
import json
import tkinter as tk
from PIL import ImageGrab, Image, ImageOps, ImageDraw, ImageFont
import io
import sys
import base64
import threading
import time
import socket
import http.server
import socketserver
import os
import webbrowser
import subprocess
import shutil
import urllib.request
import urllib.error
from urllib.parse import urlparse, parse_qs
import html
import traceback
from tkinter import ttk

IS_WINDOWS = (os.name == "nt")

# Optional: pywin32 enables window capture, park off-screen, and input injection.
try:
    import win32gui
    import win32ui
    import win32api
    import win32con
    from ctypes import windll
    HAS_WIN32 = True
except ImportError:
    HAS_WIN32 = False

# mss: fast, cross-platform screen capture (Windows/macOS/Linux).
try:
    import mss
    HAS_MSS = True
except ImportError:
    HAS_MSS = False

# pyautogui: cross-platform mouse/keyboard injection (used off Windows).
try:
    import pyautogui
    pyautogui.FAILSAFE = False
    HAS_PYAUTOGUI = True
except Exception:
    HAS_PYAUTOGUI = False

IS_MAC = (sys.platform == "darwin")
IS_LINUX = sys.platform.startswith("linux")

# Quartz (pyobjc): single-window enumeration + capture on macOS (the mac
# equivalent of pywin32's window APIs). Optional — falls back to full screen.
if IS_MAC:
    try:
        import Quartz
        HAS_QUARTZ = True
    except Exception:
        HAS_QUARTZ = False
else:
    HAS_QUARTZ = False

# wmctrl: enumerate + locate X11 windows on Linux (region-cropped from the
# full-screen grab). Optional — falls back to full screen if not installed.
HAS_WMCTRL = bool(IS_LINUX and shutil.which("wmctrl"))


def _btn_kw(color, light_text=True):
    """Per-platform button coloring. macOS's native (aqua) button ignores `bg`,
    so `fg="white"` would render white text on a light button = invisible; there
    we tint via `highlightbackground` and keep the default dark, legible text.
    Windows/Linux honor bg/fg normally."""
    if IS_MAC:
        return {"highlightbackground": color}
    return {"bg": color, "fg": "white"} if light_text else {"bg": color}


def grab_fullscreen():
    """Capture the primary screen as a PIL image, cross-platform (mss), with a
    Pillow fallback (Windows/macOS)."""
    if HAS_MSS:
        with mss.mss() as sct:
            mons = sct.monitors
            mon = mons[1] if len(mons) > 1 else mons[0]
            shot = sct.grab(mon)
            return Image.frombytes("RGB", shot.size, shot.bgra, "raw", "BGRX")
    return ImageGrab.grab()


def list_monitors():
    """Return [(index, left, top, width, height)] for each physical monitor
    (mss index >= 1; index 0 is the union of all monitors and is skipped).

    This is how a BetterDisplay/virtual-display 'second screen' shows up so a
    device can be pointed at just that display.
    """
    out = []
    if HAS_MSS:
        try:
            with mss.mss() as sct:
                for i, m in enumerate(sct.monitors):
                    if i == 0:
                        continue
                    out.append((i, m["left"], m["top"], m["width"], m["height"],
                                bool(m.get("is_primary"))))
        except Exception:
            pass
    return out


def grab_monitor(index):
    """Capture a single monitor by mss index -> (PIL image, region rect)."""
    if HAS_MSS:
        try:
            with mss.mss() as sct:
                mons = sct.monitors
                if 0 <= index < len(mons):
                    m = mons[index]
                    shot = sct.grab(m)
                    img = Image.frombytes("RGB", shot.size, shot.bgra, "raw", "BGRX")
                    return img, (m["left"], m["top"], m["width"], m["height"])
        except Exception:
            pass
    img = grab_fullscreen()
    return img, (0, 0, img.width, img.height)


# ---- cross-platform input injection (Windows: win32; else: pyautogui) ----
_PYKEY = {
    "enter": "enter", "backspace": "backspace", "esc": "esc", "tab": "tab",
    "space": "space", "up": "up", "down": "down", "left": "left", "right": "right",
    "del": "delete", "home": "home", "end": "end",
}


def input_click(x, y, button="left"):
    if HAS_WIN32:
        win32api.SetCursorPos((x, y))
        if button == "right":
            down, up = win32con.MOUSEEVENTF_RIGHTDOWN, win32con.MOUSEEVENTF_RIGHTUP
        else:
            down, up = win32con.MOUSEEVENTF_LEFTDOWN, win32con.MOUSEEVENTF_LEFTUP
        win32api.mouse_event(down, 0, 0, 0, 0)
        win32api.mouse_event(up, 0, 0, 0, 0)
    elif HAS_PYAUTOGUI:
        pyautogui.click(x, y, button=("right" if button == "right" else "left"))


def input_move(x, y):
    if HAS_WIN32:
        win32api.SetCursorPos((x, y))
    elif HAS_PYAUTOGUI:
        pyautogui.moveTo(x, y)


def input_key(name):
    if HAS_WIN32:
        vk = _PC_VK.get(name)
        if vk is None:
            return
        win32api.keybd_event(vk, 0, 0, 0)
        win32api.keybd_event(vk, 0, win32con.KEYEVENTF_KEYUP, 0)
    elif HAS_PYAUTOGUI:
        k = _PYKEY.get(name)
        if k:
            pyautogui.press(k)


def input_text(text):
    if HAS_WIN32:
        for ch in text:
            try:
                res = win32api.VkKeyScan(ch)
            except Exception:
                continue
            if res == -1:
                continue
            vk = res & 0xFF
            shift = (res >> 8) & 1
            if shift:
                win32api.keybd_event(0x10, 0, 0, 0)
            win32api.keybd_event(vk, 0, 0, 0)
            win32api.keybd_event(vk, 0, win32con.KEYEVENTF_KEYUP, 0)
            if shift:
                win32api.keybd_event(0x10, 0, win32con.KEYEVENTF_KEYUP, 0)
    elif HAS_PYAUTOGUI:
        pyautogui.typewrite(text)


def _inverse_rot_norm(nx, ny, rot):
    """Map a normalized point in the displayed (rotated) image back to the
    unrotated source. Server rotates via rotate(-rot) = clockwise by rot."""
    rot = rot % 360
    if rot == 90:
        return (ny, 1.0 - nx)
    if rot == 180:
        return (1.0 - nx, 1.0 - ny)
    if rot == 270:
        return (1.0 - ny, nx)
    return (nx, ny)


def list_windows():
    """Return a list of (id, title) for visible, titled top-level windows.

    `id` is a Windows HWND or a macOS CGWindowID — both plain ints, so the rest
    of the app can treat them uniformly under the `win:<id>` source key.
    """
    result = []
    if HAS_WIN32:
        def _cb(hwnd, _):
            if win32gui.IsWindowVisible(hwnd):
                title = win32gui.GetWindowText(hwnd)
                if title and title.strip():
                    result.append((hwnd, title))
        win32gui.EnumWindows(_cb, None)
        return result
    if HAS_QUARTZ:
        return _mac_list_windows()
    if HAS_WMCTRL:
        return _linux_list_windows()
    return result


def _wmctrl_rows():
    """Parse `wmctrl -lG` -> list of (wid:int, x, y, w, h, title)."""
    rows = []
    try:
        raw = subprocess.run(["wmctrl", "-lG"], capture_output=True,
                             text=True, timeout=3).stdout
    except Exception:
        return rows
    for line in raw.splitlines():
        parts = line.split(None, 7)
        if len(parts) < 8:
            continue
        try:
            wid = int(parts[0], 16)
            x, y, w, h = int(parts[2]), int(parts[3]), int(parts[4]), int(parts[5])
        except ValueError:
            continue
        rows.append((wid, x, y, w, h, parts[7].strip()))
    return rows


def _linux_list_windows():
    """Enumerate top-level windows on Linux/X11 via `wmctrl -lG`."""
    out = []
    for wid, _x, _y, w, h, title in _wmctrl_rows():
        if w < 80 or h < 80 or not title:
            continue
        out.append((wid, title))
    return out


def _linux_window_region(wid):
    """(x, y, w, h) on-screen rect for a Linux window id, or None."""
    for w_id, x, y, w, h, _title in _wmctrl_rows():
        if w_id == wid:
            return (x, y, w, h)
    return None


def _linux_capture_window(wid):
    """Capture one Linux window by cropping its region out of the full grab
    (works for on-screen, unobscured windows on X11)."""
    full = grab_fullscreen()
    r = _linux_window_region(wid)
    if not r:
        return full
    x, y, w, h = r
    x, y = max(0, x), max(0, y)
    x2, y2 = min(x + w, full.width), min(y + h, full.height)
    if x2 <= x or y2 <= y:
        return full
    return full.crop((x, y, x2, y2))


def _mac_list_windows():
    """Enumerate on-screen application windows on macOS via Quartz.

    Keeps *every* real window (so three VS Code windows show as three, not one),
    numbering same-named ones. Window *names* only populate once Screen Recording
    permission is granted; without it every window of an app shows as just the app
    name — which is why they used to collapse together.
    """
    out = []
    counts = {}
    opts = (Quartz.kCGWindowListOptionOnScreenOnly |
            Quartz.kCGWindowListExcludeDesktopElements)
    infos = Quartz.CGWindowListCopyWindowInfo(opts, Quartz.kCGNullWindowID) or []
    for info in infos:
        # Layer 0 = normal app windows; skip menubar, Dock, overlays, wallpaper.
        if int(info.get("kCGWindowLayer", 0)) != 0:
            continue
        try:
            if float(info.get("kCGWindowAlpha", 1)) <= 0.0:
                continue  # fully transparent helper/overlay windows
        except Exception:
            pass
        b = info.get("kCGWindowBounds") or {}
        if float(b.get("Width", 0)) < 80 or float(b.get("Height", 0)) < 80:
            continue
        wid = int(info.get("kCGWindowNumber", 0))
        owner = (info.get("kCGWindowOwnerName") or "").strip()
        name = (info.get("kCGWindowName") or "").strip()
        base = (f"{owner} — {name}" if name and name != owner
                else (owner or name or f"Window {wid}"))
        counts[base] = counts.get(base, 0) + 1
        label = base if counts[base] == 1 else f"{base} ({counts[base]})"
        out.append((wid, label))
    return out


def _mac_screen_capture_ok():
    """True if macOS Screen Recording permission is granted (or the API is absent
    on this macOS). Without it, window names are hidden and window/screen capture
    comes back blank."""
    if not (IS_MAC and HAS_QUARTZ):
        return True
    try:
        return bool(Quartz.CGPreflightScreenCaptureAccess())
    except Exception:
        return True


def _mac_request_screen_capture():
    """Trigger the macOS Screen Recording permission dialog (once)."""
    try:
        Quartz.CGRequestScreenCaptureAccess()
    except Exception:
        pass


def _mac_capture_window(wid):
    """Capture one macOS window by CGWindowID -> RGB PIL image."""
    img = Quartz.CGWindowListCreateImage(
        Quartz.CGRectNull,
        Quartz.kCGWindowListOptionIncludingWindow,
        wid,
        Quartz.kCGWindowImageBoundsIgnoreFraming)
    if img is None:
        return grab_fullscreen()
    w = int(Quartz.CGImageGetWidth(img))
    h = int(Quartz.CGImageGetHeight(img))
    if w == 0 or h == 0:
        return grab_fullscreen()
    bpr = int(Quartz.CGImageGetBytesPerRow(img))
    data = Quartz.CGDataProviderCopyData(Quartz.CGImageGetDataProvider(img))
    buf = bytes(data)
    # CGImage is BGRA; `bpr` handles any per-row padding.
    return Image.frombuffer("RGBA", (w, h), buf, "raw", "BGRA", bpr, 1).convert("RGB")


def _mac_window_region(wid):
    """(x, y, w, h) on-screen rect in points for a macOS window id, or None."""
    try:
        infos = Quartz.CGWindowListCopyWindowInfo(
            Quartz.kCGWindowListOptionIncludingWindow, wid) or []
        for info in infos:
            if int(info.get("kCGWindowNumber", 0)) == wid:
                b = info.get("kCGWindowBounds") or {}
                return (int(b.get("X", 0)), int(b.get("Y", 0)),
                        int(b.get("Width", 0)), int(b.get("Height", 0)))
    except Exception:
        pass
    return None


_FONT_CACHE = {}


def _get_mono_font(size):
    if size in _FONT_CACHE:
        return _FONT_CACHE[size]
    font = None
    for name in ("consola.ttf", "cour.ttf", "lucon.ttf", "DejaVuSansMono.ttf"):
        try:
            font = ImageFont.truetype(name, size)
            break
        except Exception:
            continue
    if font is None:
        font = ImageFont.load_default()
    _FONT_CACHE[size] = font
    return font


def render_terminal_image(text, w, h):
    """Render terminal text into a w x h grayscale image (black on white),
    auto-sizing the monospace font so the widest line fits the width."""
    if not text:
        text = "(waiting for terminal...)"
    lines = text.split("\n")
    cols = max((len(l) for l in lines), default=1) or 1
    margin = 6
    avail = max(w - 2 * margin, 1)
    # Consolas advance width is ~0.55 x font size.
    size = int(avail / (cols * 0.55)) if cols else 18
    size = max(8, min(size, 24))
    font = _get_mono_font(size)
    line_h = int(size * 1.25) or 1

    img = Image.new("L", (w, h), 255)
    draw = ImageDraw.Draw(img)
    y = margin
    for line in lines:
        if y > h:
            break
        draw.text((margin, y), line, fill=0, font=font)
        y += line_h
    return img


def _is_mostly_black(img):
    """True if the image is essentially all black (PrintWindow failed on a GPU app)."""
    try:
        extrema = img.convert("RGB").getextrema()
        return all(hi <= 12 for (_lo, hi) in extrema)
    except Exception:
        return False


def capture_window(hwnd):
    """Capture a single window by handle. Works even if it's behind other windows.

    Uses PrintWindow(PW_RENDERFULLCONTENT); if that yields a black frame (common
    for GPU-rendered windows like Windows Terminal), falls back to grabbing the
    window's on-screen region.

    On macOS/Linux (no pywin32) it delegates to the Quartz / wmctrl paths.
    """
    if not HAS_WIN32:
        if HAS_QUARTZ:
            return _mac_capture_window(hwnd)
        if HAS_WMCTRL:
            return _linux_capture_window(hwnd)
        return grab_fullscreen()
    minimized = bool(win32gui.IsIconic(hwnd))
    if minimized:
        # Minimized windows sit off-screen; use the restored size so PrintWindow
        # can render the window's own buffer at its normal dimensions.
        try:
            _, _, _, _, rc_normal = win32gui.GetWindowPlacement(hwnd)
            left, top, right, bottom = rc_normal
        except Exception:
            left, top, right, bottom = win32gui.GetWindowRect(hwnd)
    else:
        left, top, right, bottom = win32gui.GetWindowRect(hwnd)
    w, h = right - left, bottom - top
    if w <= 0 or h <= 0:
        return ImageGrab.grab()

    hwnd_dc = win32gui.GetWindowDC(hwnd)
    mfc_dc = win32ui.CreateDCFromHandle(hwnd_dc)
    save_dc = mfc_dc.CreateCompatibleDC()
    save_bmp = win32ui.CreateBitmap()
    save_bmp.CreateCompatibleBitmap(mfc_dc, w, h)
    save_dc.SelectObject(save_bmp)

    # PW_RENDERFULLCONTENT = 2 (captures modern/DWM-composited windows, and is
    # the best shot at rendering a minimized window's own buffer).
    ok = windll.user32.PrintWindow(hwnd, save_dc.GetSafeHdc(), 2)

    info = save_bmp.GetInfo()
    bits = save_bmp.GetBitmapBits(True)
    img = Image.frombuffer("RGB", (info["bmWidth"], info["bmHeight"]),
                           bits, "raw", "BGRX", 0, 1)

    # Clean up GDI objects
    win32gui.DeleteObject(save_bmp.GetHandle())
    save_dc.DeleteDC()
    mfc_dc.DeleteDC()
    win32gui.ReleaseDC(hwnd, hwnd_dc)

    # Fallback for GPU apps that return black to PrintWindow. Only grab the
    # on-screen region when the window is NOT minimized (a minimized window has
    # no valid on-screen region to grab).
    if (not ok or _is_mostly_black(img)) and not minimized:
        try:
            img = ImageGrab.grab(bbox=(left, top, right, bottom), all_screens=True)
        except Exception:
            pass
    return img

def _adb_exe():
    """Locate adb.exe (PATH first, then common install dirs)."""
    p = shutil.which("adb")
    if p:
        return p
    for c in (r"C:\platform-tools\adb.exe", r"C:\adb\adb.exe",
              os.path.expanduser(r"~\platform-tools\adb.exe")):
        if os.path.isfile(c):
            return c
    return "adb"


def _scrcpy_exe():
    p = shutil.which("scrcpy")
    if p:
        return p
    for c in (r"C:\scrcpy\scrcpy.exe", r"C:\platform-tools\scrcpy.exe",
              os.path.expanduser(r"~\scrcpy\scrcpy.exe")):
        if os.path.isfile(c):
            return c
    return None


ADB = _adb_exe()
_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)


def _adb_run(args, timeout=15, binary=False):
    proc = subprocess.run([ADB] + list(args), capture_output=True,
                          timeout=timeout, creationflags=_NO_WINDOW)
    if binary:
        return proc.returncode, proc.stdout, proc.stderr
    return (proc.returncode,
            proc.stdout.decode("utf-8", "replace"),
            proc.stderr.decode("utf-8", "replace"))


def adb_devices():
    """Return a list of connected/authorized device serials."""
    try:
        _rc, out, _err = _adb_run(["devices"])
    except Exception as e:
        print("adb devices error:", e)
        return []
    devices = []
    for line in out.splitlines()[1:]:
        line = line.strip()
        if line and "\tdevice" in line:
            devices.append(line.split("\t")[0])
    return devices


def adb_connect(hostport):
    try:
        _rc, out, err = _adb_run(["connect", hostport], timeout=20)
        return (out.strip() or err.strip())
    except Exception as e:
        return str(e)


def adb_screencap(serial):
    """Grab the Android screen as a PIL image (exec-out avoids CRLF corruption)."""
    rc, out, err = _adb_run(["-s", serial, "exec-out", "screencap", "-p"],
                            timeout=15, binary=True)
    if rc != 0 or not out:
        raise RuntimeError((err or b"").decode("utf-8", "replace") or "screencap failed")
    return Image.open(io.BytesIO(out)).convert("RGB")


def adb_tap(serial, x, y):
    try:
        _adb_run(["-s", serial, "shell", "input", "tap", str(int(x)), str(int(y))], timeout=8)
    except Exception as e:
        print("adb tap error:", e)


def adb_keyevent(serial, keycode):
    try:
        _adb_run(["-s", serial, "shell", "input", "keyevent", str(keycode)], timeout=8)
    except Exception as e:
        print("adb key error:", e)


def adb_text(serial, text):
    try:
        _adb_run(["-s", serial, "shell", "input", "text", text.replace(" ", "%s")], timeout=8)
    except Exception as e:
        print("adb text error:", e)


# Named key -> Windows virtual-key code
_PC_VK = {
    "enter": 0x0D, "backspace": 0x08, "esc": 0x1B, "tab": 0x09, "space": 0x20,
    "up": 0x26, "down": 0x28, "left": 0x25, "right": 0x27, "del": 0x2E,
    "home": 0x24, "end": 0x23,
}
# Named key -> Android keycode
_ANDROID_KEY = {
    "enter": 66, "backspace": 67, "esc": 111, "tab": 61, "space": 62,
    "up": 19, "down": 20, "left": 21, "right": 22, "del": 67,
    "aback": 4, "ahome": 3, "arecents": 187,
}


class CustomHTTPRequestHandler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, directory=None, ws_port=None, app=None, **kwargs):
        self.ws_port = ws_port
        self.app = app
        # Set the directory to the folder containing the mirrorindex.html
        if directory is None:
            directory = os.path.dirname(os.path.abspath(__file__))
        super().__init__(*args, directory=directory, **kwargs)

    def log_message(self, format, *args):
        # Silence HTTP logs to avoid cluttering the console
        pass

    def do_GET(self):
        path = urlparse(self.path).path

        # Handle request to get the WebSocket port
        if path == '/get_ws_port':
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')  # Enable CORS
            self.send_header('Cache-Control', 'no-cache, no-store')  # Prevent caching
            self.end_headers()
            response = json.dumps({'ws_port': self.ws_port})
            print(f"Client requested WebSocket port. Sending: {self.ws_port}")
            self.wfile.write(response.encode('utf-8'))
            return

        # No-JavaScript, auto-refreshing page for old browsers (e.g. Kindle 4).
        if path == '/simple':
            return self.serve_simple()
        # Raw latest frame (image) for the /simple page's <img>.
        if path == '/frame':
            return self.serve_frame()
        # MJPEG live stream (no-JS realtime for old browsers).
        if path == '/mjpeg':
            return self.serve_mjpeg()
        # Cheap change token — clients poll this and only re-fetch /frame on change.
        if path == '/frameid':
            return self.serve_frameid()
        # No-JS tap-to-click target for the /simple page (old browsers).
        if path == '/click':
            return self.serve_click()
        # No-JS keyboard / special-key / Android-nav targets.
        if path == '/key':
            return self.serve_key()
        if path == '/type':
            return self.serve_type()

        # Serve the index page for root requests
        if self.path == '/' or self.path == '/index.html':
            self.path = '/mirrorindex.html'

        # Otherwise serve files as usual
        return super().do_GET()

    def serve_simple(self):
        """A plain HTML page that auto-refreshes via <meta refresh> — no JS/WebSocket.
        Shows terminal text in Terminal mode, or the latest frame otherwise."""
        app = self.app
        q = parse_qs(urlparse(self.path).query)

        def _clamp(name, default, lo, hi):
            try:
                return max(lo, min(int(q.get(name, [default])[0]), hi))
            except Exception:
                return default

        # Refresh defaults SLOW (e-ink hates frequent full repaints). 0 = manual only.
        refresh = _clamp('r', 15, 0, 600)   # seconds between refreshes (0 = manual)
        fontsize = _clamp('fs', 20, 8, 60)  # terminal font px
        # Image fit: 'screen' = fill screen, whole window visible (default);
        #            'cover'  = fill edge-to-edge (may crop); 'width' = fill width, scroll.
        fit = q.get('fit', ['screen'])[0]
        tap = q.get('tap', ['0'])[0] == '1'   # no-JS tap-to-click control
        live = q.get('live', ['0'])[0] == '1'  # MJPEG realtime stream (no JS)
        dw = _clamp('dw', 1024, 100, 4000)     # display width used for tap mapping
        src = q.get('src', [''])[0]            # per-device source (?src=win:HWND etc.)
        pick = q.get('pick', ['0'])[0] == '1'  # show the source picker

        # This device's chosen source frame (marks it active so it keeps capturing).
        frame, src_key = (app.frame_for(src) if app else (None, 'screen'))

        # Picker page: list every source this device can pick.
        if pick and app:
            return self._serve_picker(app, live, tap)

        # Read the plain mirror attribute (never a Tk var) from this thread.
        mode = getattr(app, 'active_mode', 'screen') if app else 'screen'
        show_terminal = (mode == 'terminal') and not src  # a picked src is always image

        def link(r=None, f=None, fs=None, t=None, lv=None):
            return (f"/simple?r={refresh if r is None else r}"
                    f"&fit={fit if f is None else f}"
                    f"&fs={fontsize if fs is None else fs}"
                    f"&tap={('1' if tap else '0') if t is None else t}"
                    f"&live={('1' if live else '0') if lv is None else lv}"
                    f"&dw={dw}&src={src}")

        srcq = f"&src={src}" if src else ""
        # Image source: live MJPEG stream, or a single cache-busted frame.
        img_src = (f"/mjpeg?src={src}" if live else f"/frame?ts={int(time.time())}{srcq}")

        auto = 'manual' if refresh == 0 else f'{refresh}s'
        bare = q.get('bar', ['1'])[0] == '0'   # bar=0 hides the control bar entirely
        # Full-screen image modes float the bar (not in tap mode, which is fixed-size).
        full = (not show_terminal) and fit in ('screen', 'cover') and not tap
        bar_pos = ('position:fixed;top:0;left:0;right:0;z-index:10;opacity:0.92;'
                   if full else '')
        bar = '' if bare else (
            f'<div style="{bar_pos}font-family:sans-serif;font-size:15px;padding:6px 8px;'
            'border-bottom:2px solid #000;background:#fff;">'
            f'<a href="{link()}">&#8635; Refresh</a> &nbsp; '
            f'auto {auto}: '
            f'<a href="{link(r=min(600, (refresh or 0) + 10))}">slower</a> '
            f'<a href="{link(r=max(0, refresh - 10))}">faster</a> '
            f'<a href="{link(r=0)}">manual</a> &nbsp; '
            f'fit <a href="{link(f="screen")}">whole</a> '
            f'<a href="{link(f="cover")}">fill</a> '
            f'<a href="{link(f="width")}">width</a> &nbsp; '
            f'<a href="{link(lv=("0" if live else "1"))}">'
            f'{"⚡ Live: ON" if live else "⚡ Live: off"}</a> &nbsp; '
            f'text <a href="{link(fs=max(8, fontsize - 4))}">A-</a> '
            f'<a href="{link(fs=min(60, fontsize + 4))}">A+</a> &nbsp; '
            f'<a href="{link(t=("0" if tap else "1"))}">'
            f'{"🖱 Control: ON" if tap else "🖱 Control: off"}</a> &nbsp; '
            f'<a href="{link()}&pick=1">📺 Screens</a> &nbsp; '
            f'<a href="{link()}&bar=0">hide bar</a>'
            '</div>'
        )

        if show_terminal:
            text = (app.latest_text if app and app.latest_text else '(waiting for terminal...)')
            content = (f'<pre style="white-space:pre-wrap;word-wrap:break-word;'
                       f'font-family:monospace;font-size:{fontsize}px;margin:0;padding:6px;'
                       f'color:#000;">{html.escape(text)}</pre>')
        elif tap:
            # No-JS control: an <input type=image> submits the tap's pixel coords.
            # We display at a fixed dw x dh so those coords map linearly to [0,1].
            lw, lh = (frame["size"] if frame else (app.latest_size if app else None)) or (dw, dw)
            dh = int(dw * lh / lw) if lw else dw
            form_html = (
                '<form action="/click" method="get" style="margin:0">'
                f'<input type="image" src="{img_src}" name="t" '
                f'width="{dw}" height="{dh}" style="display:block;border:0;" alt="tap to click">'
                f'<input type="hidden" name="w" value="{dw}">'
                f'<input type="hidden" name="h" value="{dh}">'
                f'<input type="hidden" name="dw" value="{dw}">'
                f'<input type="hidden" name="r" value="{refresh}">'
                f'<input type="hidden" name="src" value="{src}">'
                '</form>'
            )
            keys = [("enter", "Enter"), ("backspace", "&#9003;"), ("esc", "Esc"),
                    ("tab", "Tab"), ("up", "&uarr;"), ("down", "&darr;"),
                    ("left", "&larr;"), ("right", "&rarr;"),
                    ("aback", "&#9665;Back"), ("ahome", "&#9711;Home"),
                    ("arecents", "&#9723;Recent")]
            keybar = (
                '<div style="font-family:sans-serif;font-size:16px;padding:6px;line-height:2.2;">'
                '<form action="/type" method="get" style="display:inline">'
                '<input name="text" size="14" style="font-size:16px;">'
                f'<input type="hidden" name="dw" value="{dw}">'
                f'<input type="hidden" name="r" value="{refresh}">'
                f'<input type="hidden" name="src" value="{src}">'
                '<input type="submit" value="Type"></form> &nbsp; '
                + ' '.join(
                    f'<a href="/key?k={k}&dw={dw}&r={refresh}&src={src}" style="text-decoration:none;'
                    f'border:1px solid #000;padding:4px 9px;color:#000;">{lbl}</a>'
                    for k, lbl in keys)
                + '</div>'
            )
            content = form_html + keybar
        elif fit == 'width':
            # Fill the width; a tall window scrolls vertically.
            content = (f'<img src="{img_src}" '
                       f'style="display:block;width:100%;height:auto;" alt="screen">')
        else:
            # Fill the whole screen. object-fit:contain (screen) shows the entire
            # window; 'cover' fills edge-to-edge and may crop. Old browsers ignore
            # object-fit and simply stretch to fill — still full-screen.
            objfit = 'cover' if fit == 'cover' else 'contain'
            content = (f'<img src="{img_src}" '
                       f'style="display:block;width:100%;height:100%;'
                       f'object-fit:{objfit};" alt="screen">')

        # Full 100%-height body is required for the full-screen image to fill.
        html_h = 'height:100%;' if full else ''
        # Auto-refresh only when NOT live (MJPEG self-updates) and interval > 0.
        meta_refresh = (f'<meta http-equiv="refresh" content="{refresh}">'
                        if (refresh > 0 and not live) else '')
        page = (
            '<html><head>'
            + meta_refresh +
            '<meta name="viewport" content="width=device-width, initial-scale=1">'
            f'<style>html,body{{margin:0;padding:0;{html_h}background:#fff;color:#000;}}'
            'a{color:#000;}</style>'
            '</head><body>' + bar + content + '</body></html>'
        )
        data = page.encode('utf-8')
        self.send_response(200)
        self.send_header('Content-type', 'text/html; charset=utf-8')
        self.send_header('Cache-Control', 'no-cache, no-store, must-revalidate')
        self.end_headers()
        self.wfile.write(data)

    def serve_click(self):
        """Handle a no-JS tap from /simple: <input type=image> submits t.x/t.y."""
        app = self.app
        q = parse_qs(urlparse(self.path).query)

        def _f(name, default=0.0):
            try:
                return float(q.get(name, [default])[0])
            except Exception:
                return default

        tx, ty = _f("t.x"), _f("t.y")
        w, h = _f("w", 0), _f("h", 0)
        dw, r = int(_f("dw", 1024)), int(_f("r", 15))
        src = q.get("src", [""])[0]
        if app and w > 0 and h > 0:
            nx = min(max(tx / w, 0.0), 1.0)
            ny = min(max(ty / h, 0.0), 1.0)
            try:
                app.inject_at(src, nx, ny, "click")
            except Exception as e:
                print("no-JS click inject error:", e)
        # Redirect back to the tap page so the browser reloads a fresh frame.
        self._redirect_tap(dw, r, src)

    def _redirect_tap(self, dw, r, src=""):
        srcq = f"&src={src}" if src else ""
        self.send_response(302)
        self.send_header("Location", f"/simple?tap=1&dw={int(dw)}&r={int(r)}{srcq}")
        self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
        self.end_headers()

    def serve_key(self):
        """No-JS special key / Android nav: /key?k=enter&dw=&r=&src=."""
        q = parse_qs(urlparse(self.path).query)
        name = q.get("k", [""])[0]
        src = q.get("src", [""])[0]
        try:
            dw = int(q.get("dw", [1024])[0]); r = int(q.get("r", [15])[0])
        except Exception:
            dw, r = 1024, 15
        if self.app and name:
            try:
                self.app.send_key(name, src)
            except Exception as e:
                print("key inject error:", e)
        self._redirect_tap(dw, r, src)

    def serve_type(self):
        """No-JS text typing: /type?text=hello&dw=&r=&src=."""
        q = parse_qs(urlparse(self.path).query)
        text = q.get("text", [""])[0]
        src = q.get("src", [""])[0]
        try:
            dw = int(q.get("dw", [1024])[0]); r = int(q.get("r", [15])[0])
        except Exception:
            dw, r = 1024, 15
        if self.app and text:
            try:
                self.app.send_text(text, src)
            except Exception as e:
                print("type inject error:", e)
        self._redirect_tap(dw, r, src)

    def _serve_picker(self, app, live, tap):
        """List every source this device can pick (full screen, each window, Android)."""
        lv = "1" if live else "0"
        tp = "1" if tap else "0"

        def item(key, label):
            return (f'<a href="/simple?src={key}&live={lv}&tap={tp}&r=15" '
                    'style="display:block;padding:16px;font-size:20px;'
                    'border-bottom:1px solid #ccc;color:#000;text-decoration:none;">'
                    f'{html.escape(label)}</a>')

        rows = [item("screen", "🖥  Full Screen")]
        for label, idx in list(getattr(app, "monitor_map", {}).items()):
            rows.append(item(f"mon:{idx}", label))
        for label, hwnd in list(getattr(app, "window_map", {}).items()):
            rows.append(item(f"win:{hwnd}", f"🪟  {label}"))
        for label, serial in list(getattr(app, "android_map", {}).items()):
            rows.append(item(f"adb:{serial}", f"📱  {label}"))
        page = (
            '<html><head><meta name="viewport" content="width=device-width, initial-scale=1">'
            '<style>body{margin:0;font-family:sans-serif;background:#fff;color:#000;}'
            'h3{padding:12px;margin:0;background:#eee;}</style></head><body>'
            '<h3>Pick what to show on THIS device:</h3>' + ''.join(rows) +
            '</body></html>'
        )
        data = page.encode('utf-8')
        self.send_response(200)
        self.send_header('Content-type', 'text/html; charset=utf-8')
        self.send_header('Cache-Control', 'no-cache, no-store, must-revalidate')
        self.end_headers()
        self.wfile.write(data)

    def serve_mjpeg(self):
        """Live MJPEG stream (multipart/x-mixed-replace) — realtime, no JS.
        Only pushes a new part when the frame actually changed (change-detection)."""
        app = self.app
        src = parse_qs(urlparse(self.path).query).get('src', [''])[0]
        self.send_response(200)
        self.send_header("Content-Type", "multipart/x-mixed-replace; boundary=frame")
        self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
        self.send_header("Connection", "close")
        self.end_headers()
        last_ver = None
        try:
            while True:
                frame, _key = app.frame_for(src) if app else (None, None)
                if frame:
                    ver, b64, fmt = frame["version"], frame["image"], frame["format"]
                else:
                    ver = getattr(app, "frame_version", 0) if app else 0
                    b64 = app.latest_image if app else None
                    fmt = getattr(app, "latest_format", "jpeg") if app else "jpeg"
                if b64 and ver != last_ver:
                    last_ver = ver
                    raw = base64.b64decode(b64)
                    if fmt != "jpeg":  # MJPEG wants jpeg parts
                        try:
                            im = Image.open(io.BytesIO(raw)).convert("RGB")
                            buf = io.BytesIO()
                            im.save(buf, "JPEG", quality=70)
                            raw = buf.getvalue()
                        except Exception:
                            pass
                    self.wfile.write(b"--frame\r\n")
                    self.wfile.write(b"Content-Type: image/jpeg\r\n")
                    self.wfile.write(f"Content-Length: {len(raw)}\r\n\r\n".encode())
                    self.wfile.write(raw)
                    self.wfile.write(b"\r\n")
                    self.wfile.flush()
                time.sleep(0.1)  # up to ~10 fps; idle when nothing changes
        except (BrokenPipeError, ConnectionResetError, OSError):
            return
        except Exception:
            return

    def serve_frameid(self):
        """Return a small change token (frame version). Clients poll this cheaply
        and only re-fetch /frame when it differs from the last one they painted."""
        app = self.app
        src = parse_qs(urlparse(self.path).query).get('src', [''])[0]
        frame, _key = app.frame_for(src) if app else (None, None)
        version = frame["version"] if frame else (getattr(app, 'frame_version', 0) if app else 0)
        body = str(version).encode('utf-8')
        self.send_response(200)
        self.send_header('Content-type', 'text/plain')
        self.send_header('Cache-Control', 'no-cache, no-store, must-revalidate')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def serve_frame(self):
        """Return the latest captured frame as raw image bytes.

        Query options (used by the Kindle 'eips' extension):
          png=1     -> re-encode as grayscale PNG (what eips/fbink want)
          w=&h=     -> fit the frame into an exactly w x h grayscale PNG,
                       padded/centered, so it fills the Kindle screen edge-to-edge.
        """
        app = self.app
        q = parse_qs(urlparse(self.path).query)
        src = q.get('src', [''])[0]

        want_png = q.get('png', ['0'])[0] == '1'
        try:
            w = int(q.get('w', ['0'])[0])
            h = int(q.get('h', ['0'])[0])
        except Exception:
            w = h = 0

        # Terminal mode (only when no explicit ?src): render the text into an image
        # so the Kindle eips extension shows crisp terminal text, not a screenshot.
        mode = getattr(app, 'active_mode', 'screen') if app else 'screen'
        if mode == 'terminal' and not src:
            text = getattr(app, 'latest_text', None) if app else None
            tw = w if w > 0 else 600
            th = h if h > 0 else 800
            try:
                img = render_terminal_image(text, tw, th)
                buf = io.BytesIO()
                img.save(buf, 'PNG')
                raw = buf.getvalue()
            except Exception as e:
                print(f"terminal render error: {e}")
                self.send_response(500)
                self.end_headers()
                return
            self.send_response(200)
            self.send_header('Content-type', 'image/png')
            self.send_header('Cache-Control', 'no-cache, no-store, must-revalidate')
            self.end_headers()
            self.wfile.write(raw)
            return

        frame, _key = app.frame_for(src) if app else (None, None)
        if frame:
            b64 = frame["image"]
            fmt_default = frame["format"]
        else:
            b64 = app.latest_image if app else None
            fmt_default = getattr(app, 'latest_format', 'jpeg') if app else 'jpeg'
        fmt = fmt_default
        if not b64:
            self.send_response(503)
            self.end_headers()
            return
        try:
            raw = base64.b64decode(b64)
        except Exception:
            self.send_response(500)
            self.end_headers()
            return

        if want_png or (w > 0 and h > 0):
            try:
                im = Image.open(io.BytesIO(raw)).convert('L')  # grayscale
                if w > 0 and h > 0:
                    fitted = im.copy()
                    fitted.thumbnail((w, h), Image.Resampling.LANCZOS)
                    canvas = Image.new('L', (w, h), 255)  # white background
                    canvas.paste(fitted, ((w - fitted.width) // 2,
                                          (h - fitted.height) // 2))
                    im = canvas
                buf = io.BytesIO()
                im.save(buf, 'PNG')
                raw = buf.getvalue()
                fmt = 'png'
            except Exception as e:
                print(f"Kindle frame convert error: {e}")

        self.send_response(200)
        self.send_header('Content-type', f'image/{fmt}')
        self.send_header('Cache-Control', 'no-cache, no-store, must-revalidate')
        self.end_headers()
        self.wfile.write(raw)

class MirrorApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Inka — second screen + remote control")
        self.root.geometry("430x560")  # room for all controls
        # Force an opaque background. Without this, some macOS Tcl/Tk builds leave
        # the window's backing store unpainted (garbled/static look).
        try:
            self.root.configure(bg="#ECECEC")
        except Exception:
            pass

        # Create a frame for controls
        control_frame = tk.Frame(root, padx=10, pady=10)
        control_frame.pack(fill=tk.X)

        # Mode selection: mirror the screen, or stream a WSL terminal (Claude CLI)
        mode_frame = tk.Frame(control_frame)
        mode_frame.pack(fill=tk.X, pady=5)
        tk.Label(mode_frame, text="Mode:").pack(side=tk.LEFT)
        self.mode_var = tk.StringVar(value="screen")
        tk.Radiobutton(mode_frame, text="Screen Mirror", variable=self.mode_var,
                       value="screen").pack(side=tk.LEFT, padx=5)
        tk.Radiobutton(mode_frame, text="Terminal (Claude CLI)", variable=self.mode_var,
                       value="terminal").pack(side=tk.LEFT, padx=5)

        # Terminal settings: which WSL distro + tmux session to read
        term_frame = tk.Frame(control_frame)
        term_frame.pack(fill=tk.X, pady=5)
        tk.Label(term_frame, text="WSL distro:").pack(side=tk.LEFT)
        self.distro_var = tk.StringVar(value="Ubuntu")
        tk.Entry(term_frame, textvariable=self.distro_var, width=10).pack(side=tk.LEFT, padx=3)
        tk.Label(term_frame, text="tmux session:").pack(side=tk.LEFT)
        self.session_var = tk.StringVar(value="claude")
        tk.Entry(term_frame, textvariable=self.session_var, width=10).pack(side=tk.LEFT, padx=3)

        # Terminal font size (sent to the browser)
        font_frame = tk.Frame(control_frame)
        font_frame.pack(fill=tk.X, pady=5)
        tk.Label(font_frame, text="Terminal Font:").pack(side=tk.LEFT)
        self.fontsize_var = tk.IntVar(value=20)
        font_slider = ttk.Scale(font_frame, from_=10, to=48,
                                variable=self.fontsize_var, orient=tk.HORIZONTAL)
        font_slider.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
        tk.Label(font_frame, textvariable=self.fontsize_var).pack(side=tk.LEFT, padx=5)

        # E-ink rendering for screen/window streaming
        eink_frame = tk.Frame(control_frame)
        eink_frame.pack(fill=tk.X, pady=5)
        tk.Label(eink_frame, text="E-ink:").pack(side=tk.LEFT)
        self.eink_var = tk.StringVar(value="gray")
        tk.Radiobutton(eink_frame, text="Color", variable=self.eink_var,
                       value="off").pack(side=tk.LEFT, padx=5)
        tk.Radiobutton(eink_frame, text="Grayscale", variable=self.eink_var,
                       value="gray").pack(side=tk.LEFT, padx=5)
        tk.Radiobutton(eink_frame, text="B&W", variable=self.eink_var,
                       value="bw").pack(side=tk.LEFT, padx=5)

        # Window picker (used in Screen Mirror mode): stream one app window
        window_frame = tk.Frame(control_frame)
        window_frame.pack(fill=tk.X, pady=5)
        tk.Label(window_frame, text="Capture:").pack(side=tk.LEFT)
        self.window_var = tk.StringVar(value="Full Screen")
        self.window_map = {}  # label -> hwnd
        self.window_combo = ttk.Combobox(window_frame, textvariable=self.window_var,
                                         state="readonly", width=26)
        self.window_combo.pack(side=tk.LEFT, padx=3)
        tk.Button(window_frame, text="⟳", width=3,
                  command=self.refresh_windows).pack(side=tk.LEFT)
        self.refresh_windows()

        # Park the captured app off-screen (stays rendered → keeps streaming) so it's
        # out of the way — use this INSTEAD of minimizing (minimizing goes blank).
        park_frame = tk.Frame(control_frame)
        park_frame.pack(fill=tk.X, pady=2)
        tk.Button(park_frame, text="Park app off-screen (keeps streaming)",
                  command=self.park_app, **_btn_kw("#673AB7")).pack(side=tk.LEFT, padx=2)
        tk.Button(park_frame, text="Bring back",
                  command=self.restore_app).pack(side=tk.LEFT, padx=2)

        # Remote control: let a viewing device's taps click the PC (off by default).
        self.control_var = tk.BooleanVar(value=False)
        self.control_enabled = False  # plain mirror, safe to read from WS thread
        self.control_var.trace_add(
            "write", lambda *a: setattr(self, "control_enabled", self.control_var.get()))
        tk.Checkbutton(control_frame, text="Allow remote control (taps click this PC)",
                       variable=self.control_var).pack(anchor="w", pady=2)

        # Android (ADB / scrcpy) section
        android_frame = tk.Frame(control_frame)
        android_frame.pack(fill=tk.X, pady=5)
        tk.Label(android_frame, text="Android:").pack(side=tk.LEFT)
        tk.Button(android_frame, text="Scan", command=self.scan_android).pack(side=tk.LEFT, padx=2)
        self.android_ip_var = tk.StringVar()
        tk.Entry(android_frame, textvariable=self.android_ip_var, width=14).pack(side=tk.LEFT, padx=2)
        tk.Button(android_frame, text="Connect", command=self.connect_android).pack(side=tk.LEFT, padx=2)
        tk.Button(android_frame, text="PC→Phone (adb)", command=self.stream_to_android,
                  **_btn_kw("#2196F3")).pack(side=tk.LEFT, padx=2)
        tk.Button(android_frame, text="scrcpy", command=self.launch_scrcpy,
                  **_btn_kw("#3DDC84", light_text=False)).pack(side=tk.LEFT, padx=2)

        # Add rotation control
        rotation_frame = tk.Frame(control_frame)
        rotation_frame.pack(fill=tk.X, pady=5)
        
        tk.Label(rotation_frame, text="Rotation:").pack(side=tk.LEFT)
        
        # Rotation variable and radio buttons
        self.rotation_var = tk.IntVar(value=0)
        rotations = [
            ("0°", 0),
            ("90°", 90),
            ("180°", 180),
            ("270°", 270)
        ]
        
        # Create radio buttons for each rotation option
        rotation_buttons_frame = tk.Frame(rotation_frame)
        rotation_buttons_frame.pack(side=tk.LEFT, fill=tk.X, expand=True)
        
        for text, value in rotations:
            tk.Radiobutton(
                rotation_buttons_frame,
                text=text,
                variable=self.rotation_var,
                value=value
            ).pack(side=tk.LEFT, padx=10)
        
        # Quality slider
        quality_frame = tk.Frame(control_frame)
        quality_frame.pack(fill=tk.X, pady=5)
        
        tk.Label(quality_frame, text="Image Quality:").pack(side=tk.LEFT)
        self.quality_var = tk.IntVar(value=50)
        quality_slider = ttk.Scale(quality_frame, from_=10, to=95, 
                                   variable=self.quality_var, orient=tk.HORIZONTAL)
        quality_slider.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
        tk.Label(quality_frame, textvariable=self.quality_var).pack(side=tk.LEFT, padx=5)
        
        # Resolution scaling slider
        scale_frame = tk.Frame(control_frame)
        scale_frame.pack(fill=tk.X, pady=5)
        
        tk.Label(scale_frame, text="Resolution Scale:").pack(side=tk.LEFT)
        self.scale_var = tk.DoubleVar(value=1.0)
        scale_slider = ttk.Scale(scale_frame, from_=0.1, to=1.0, 
                                variable=self.scale_var, orient=tk.HORIZONTAL)
        scale_slider.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
        
        # Display the scale value with 1 decimal place
        self.scale_label = tk.Label(scale_frame, text="1.0")
        self.scale_label.pack(side=tk.LEFT, padx=5)
        
        # Update label when scale changes
        self.scale_var.trace_add("write", self.update_scale_label)
        
        # FPS control
        fps_frame = tk.Frame(control_frame)
        fps_frame.pack(fill=tk.X, pady=5)
        
        tk.Label(fps_frame, text="FPS:").pack(side=tk.LEFT)
        self.fps_var = tk.IntVar(value=10)
        fps_slider = ttk.Scale(fps_frame, from_=1, to=30, 
                              variable=self.fps_var, orient=tk.HORIZONTAL)
        fps_slider.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
        tk.Label(fps_frame, textvariable=self.fps_var).pack(side=tk.LEFT, padx=5)
        
        # Add a test connection button
        test_frame = tk.Frame(control_frame)
        test_frame.pack(fill=tk.X, pady=5)
        
        self.test_btn = tk.Button(test_frame, text="Test Connection",
                                 command=self.test_connection, **_btn_kw("#2196F3"))
        self.test_btn.pack(side=tk.LEFT, padx=5)

        self.startstop_btn = tk.Button(test_frame, text="Stop Server",
                                    command=self.toggle_server, **_btn_kw("#FF9800"))
        self.startstop_btn.pack(side=tk.LEFT, padx=5)
        
        # Status label to show server state
        self.status_label = tk.Label(root, text="Starting servers...", font=("Arial", 12))
        self.status_label.pack(side=tk.BOTTOM, fill=tk.X, pady=10)
        
        # Connection info
        self.conn_label = tk.Label(root, text="", font=("Arial", 10))
        self.conn_label.pack(side=tk.BOTTOM, fill=tk.X)
        
        # Get local IP using improved method
        self.local_ip = self.get_local_ip()
        
        # This variable will hold the latest captured screen image as a base64 string.
        self.latest_image = None

        # Latest captured terminal text (for Terminal mode).
        self.latest_text = None

        # Image format of the latest screen frame ("jpeg" or "png").
        self.latest_format = "jpeg"
        # Pixel size of the latest frame (for no-JS tap mapping on /simple).
        self.latest_size = None

        # Plain mirror of the current mode, safe to read from server threads
        # (reading Tk variables off the main thread can hang).
        self.active_mode = "screen"

        # Frame change detection: version bumps only when the content changes,
        # so slow devices (Kindle eips) can repaint only on change, not every poll.
        self.frame_version = 0
        self._last_sig = None

        # Screen-space rect of the current capture, for mapping remote taps.
        self.capture_region = None
        self.capture_rot = 0

        # Android (ADB) state
        self.android_devices = []   # serials of connected devices
        self.android_map = {}       # capture-dropdown label -> serial
        self.android_active = None  # serial currently being captured
        self.android_size = (0, 0)  # captured Android resolution (w, h)

        # "Park off-screen" state (stream an app while it's out of the way)
        self.parked_hwnd = None
        self.parked_rect = None

        # Per-device sources: each viewing device can request its own source via
        # ?src=screen | win:<hwnd> | adb:<serial>. Captured on demand into `frames`.
        self.frames = {}          # key -> dict(image, format, size, region, rot, android, android_size, version)
        self._frame_sigs = {}     # key -> last content hash
        self._src_requested = {}  # key -> last request time (time.time())
        
        # Flag to control the screen capture loop.
        self.capturing = True

        # Server state / handles (used to start & stop cleanly)
        self.server_running = False
        self.httpd = None
        self.ws_loop = None
        self.ws_server = None

        # Server ports - find available ports for both
        self.http_port = self.find_available_port(8000)
        self.ws_port = self.find_available_port(8765)

        if self.http_port is None or self.ws_port is None:
            error_msg = "Error: Could not find available ports"
            print(error_msg)
            self.status_label.config(text=error_msg)
            return

        # Start the servers, then open a browser on this PC and show connection info
        self.start_servers()

        self.open_browser_thread = threading.Thread(target=self.open_browser)
        self.open_browser_thread.daemon = True
        self.open_browser_thread.start()

        # Update connection info
        self.update_connection_info()

    def start_servers(self):
        """Start the HTTP, WebSocket, and capture threads (idempotent)."""
        if self.server_running:
            return
        self.capturing = True
        self.server_running = True

        self.http_server_thread = threading.Thread(target=self.start_http_server, daemon=True)
        self.http_server_thread.start()

        self.server_thread = threading.Thread(target=self.start_server, daemon=True)
        self.server_thread.start()

        self.capture_thread = threading.Thread(target=self.capture_loop, daemon=True)
        self.capture_thread.start()

        if hasattr(self, "startstop_btn"):
            self.startstop_btn.config(text="Stop Server")
        self.update_status("Server started")

    def stop_servers(self):
        """Stop the capture loop and both servers, freeing the ports."""
        if not self.server_running:
            return
        self.server_running = False
        self.capturing = False

        # Grab handles now, then do the (potentially blocking) shutdown off the
        # GUI thread so the window never freezes.
        httpd = self.httpd
        ws_loop = self.ws_loop
        ws_server = self.ws_server

        def _shutdown():
            if httpd is not None:
                try:
                    httpd.shutdown()
                except Exception as e:
                    print(f"HTTP shutdown error: {e}")
            if ws_loop is not None and ws_server is not None:
                try:
                    ws_loop.call_soon_threadsafe(ws_server.close)
                except Exception as e:
                    print(f"WS close error: {e}")

        threading.Thread(target=_shutdown, daemon=True).start()

        if hasattr(self, "startstop_btn"):
            self.startstop_btn.config(text="Start Server")
        self.update_status("Server stopped")

    def toggle_server(self):
        if self.server_running:
            self.stop_servers()
        else:
            self.start_servers()
    
    def update_scale_label(self, *args):
        self.scale_label.config(text=f"{self.scale_var.get():.1f}")

    def refresh_windows(self):
        """Populate the Capture dropdown with windows and Android devices."""
        items = ["Full Screen"]
        self.window_map = {}
        # Per-monitor sources (so a virtual/second display can be picked directly).
        # Only shown when there's more than one display — else "Full Screen" is it.
        self.monitor_map = {}
        mons = list_monitors()
        if len(mons) > 1:
            for idx, _l, _t, w, h, primary in mons:
                tag = ", primary" if primary else ""
                label = f"🖥 Display {idx} ({w}×{h}{tag})"
                self.monitor_map[label] = idx
                items.append(label)
        # macOS: window capture (and window names) require Screen Recording
        # permission. Surface it clearly instead of silently returning blanks.
        if IS_MAC and HAS_QUARTZ and not _mac_screen_capture_ok():
            if not getattr(self, "_asked_screen_perm", False):
                self._asked_screen_perm = True
                _mac_request_screen_capture()
            items.append("⚠ Grant Screen Recording, then press ⟳")
            self.update_status(
                "macOS: grant Inka 'Screen Recording' in System Settings → "
                "Privacy & Security, quit & reopen Inka, then press ⟳.")
        if HAS_WIN32 or HAS_QUARTZ or HAS_WMCTRL:
            for hwnd, title in list_windows():
                label = title if len(title) <= 55 else title[:52] + "..."
                # Disambiguate identical titles by appending the handle
                if label in self.window_map:
                    label = f"{label} ({hwnd})"
                self.window_map[label] = hwnd
                items.append(label)
        # Android devices as capture sources
        self.android_map = {}
        for serial in getattr(self, "android_devices", []):
            label = f"📱 {serial}"
            self.android_map[label] = serial
            items.append(label)
        self.window_combo["values"] = items
        if self.window_var.get() not in items:
            self.window_var.set("Full Screen")

    def park_app(self):
        """Move the selected capture window off-screen so it keeps rendering (and
        streaming) while being out of the way. Use this instead of minimizing."""
        if not HAS_WIN32:
            if IS_MAC:
                self.update_status("Park is Windows-only — and not needed on macOS: "
                                   "capture grabs the window even when it's behind "
                                   "others. Just don't minimize it.")
            elif IS_LINUX:
                self.update_status("Park is Windows-only. On Linux, keep the window "
                                   "visible and unobscured for window capture.")
            else:
                self.update_status("Park needs pywin32 (Windows).")
            return
        sel = self.window_var.get()
        hwnd = self.window_map.get(sel)
        if not hwnd or not win32gui.IsWindow(hwnd):
            self.update_status("Pick a window in 'Capture:' first, then Park.")
            return
        try:
            # Un-minimize without stealing focus so it renders again.
            if win32gui.IsIconic(hwnd):
                win32gui.ShowWindow(hwnd, win32con.SW_SHOWNOACTIVATE)
            l, t, r, b = win32gui.GetWindowRect(hwnd)
            self.parked_rect = (l, t, r - l, b - t)
            self.parked_hwnd = hwnd
            # Park just past the right edge of the whole (virtual) desktop.
            vx = win32api.GetSystemMetrics(win32con.SM_XVIRTUALSCREEN)
            vw = win32api.GetSystemMetrics(win32con.SM_CXVIRTUALSCREEN)
            park_x, park_y = vx + vw + 50, 50
            win32gui.SetWindowPos(hwnd, 0, park_x, park_y, r - l, b - t,
                                  win32con.SWP_NOACTIVATE | win32con.SWP_NOZORDER)
            self.update_status("App parked off-screen — still streaming. 'Bring back' to restore.")
        except Exception as e:
            self.update_status(f"Park error: {e}")

    def restore_app(self):
        """Bring a parked window back to its original on-screen position."""
        if not (HAS_WIN32 and self.parked_hwnd and self.parked_rect):
            self.update_status("Nothing parked.")
            return
        try:
            l, t, w, h = self.parked_rect
            win32gui.SetWindowPos(self.parked_hwnd, 0, l, t, w, h, win32con.SWP_NOZORDER)
            win32gui.ShowWindow(self.parked_hwnd, win32con.SW_SHOW)
            self.update_status("App brought back on-screen.")
        except Exception as e:
            self.update_status(f"Restore error: {e}")
        finally:
            self.parked_hwnd = None
            self.parked_rect = None

    def scan_android(self):
        """Scan for connected/authorized ADB devices and add them to Capture."""
        self.android_devices = adb_devices()
        self.refresh_windows()
        found = ", ".join(self.android_devices) if self.android_devices else "none"
        self.update_status(f"Android devices: {found}")

    def connect_android(self):
        """Connect to a wireless device: adb connect <ip[:port]>."""
        hp = (self.android_ip_var.get() or "").strip()
        if not hp:
            self.update_status("Enter the phone's IP (e.g. 192.168.0.50:5555)")
            return
        if ":" not in hp:
            hp += ":5555"
        result = adb_connect(hp)
        self.update_status(f"adb connect: {result}")
        self.scan_android()

    def _current_android_serial(self):
        sel = self.window_var.get()
        if sel in self.android_map:
            return self.android_map[sel]
        return self.android_devices[0] if self.android_devices else None

    def stream_to_android(self):
        """Stream the PC TO the phone over the adb tunnel (adb reverse).
        The phone then reaches the PC as localhost — over USB/adb, no Wi-Fi needed."""
        serial = self._current_android_serial()
        if not serial:
            self.update_status("No Android device — Scan/Connect a phone first (USB or wireless).")
            return
        try:
            _adb_run(["-s", serial, "reverse", f"tcp:{self.http_port}", f"tcp:{self.http_port}"])
            _adb_run(["-s", serial, "reverse", f"tcp:{self.ws_port}", f"tcp:{self.ws_port}"])
            url = f"http://localhost:{self.http_port}/simple"
            print(f"adb reverse set for {serial}. On the phone open: {url}")
            self.update_status(f"On the phone's browser open: {url}")
        except Exception as e:
            self.update_status(f"adb reverse error: {e}")

    def launch_scrcpy(self):
        """Launch real scrcpy for full-quality mirror + control (own window)."""
        scrcpy = _scrcpy_exe()
        if not scrcpy:
            self.update_status("scrcpy not found — install from github.com/Genymobile/scrcpy")
            return
        serial = self._current_android_serial()
        args = [scrcpy]
        if serial:
            args += ["-s", serial]
        try:
            subprocess.Popen(args, creationflags=_NO_WINDOW)
            self.update_status(f"Launched scrcpy{(' for ' + serial) if serial else ''}")
        except Exception as e:
            self.update_status(f"scrcpy launch error: {e}")

    def send_key(self, name, src=None):
        """Send a named special key to the active source (PC or Android)."""
        if not getattr(self, "control_enabled", False):
            return
        serial = self._android_for_src(src)
        if serial:
            code = _ANDROID_KEY.get(name)
            if code is not None:
                adb_keyevent(serial, code)
            return
        input_key(name)  # cross-platform (win32 on Windows, else pyautogui)

    def _android_for_src(self, src):
        """Resolve the Android serial for a ?src key (or the active one)."""
        if src:
            frame = self.frames.get(src)
            if frame and frame.get("android"):
                return frame["android"]
        return getattr(self, "android_active", None)

    def send_text(self, text, src=None):
        """Type text into the focused window (PC) or the Android device."""
        if not getattr(self, "control_enabled", False) or not text:
            return
        serial = self._android_for_src(src)
        if serial:
            adb_text(serial, text)
            return
        input_text(text)  # cross-platform

    def get_local_ip(self):
        """Get the actual local IP address that can be reached from other devices."""
        try:
            # Connect to a remote address to determine which local interface to use
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
                s.connect(("8.8.8.8", 80))
                ip = s.getsockname()[0]
                print(f"Detected network IP: {ip}")
                return ip
        except Exception as e:
            print(f"Failed to detect network IP: {e}")
            # Fallback to the original method
            fallback_ip = socket.gethostbyname(socket.gethostname())
            print(f"Using fallback IP: {fallback_ip}")
            return fallback_ip
    
    def run_network_diagnostics(self):
        """Run basic network diagnostics to help troubleshoot connectivity."""
        try:
            # Test if we can bind to the IP and ports
            print(f"Testing HTTP port {self.http_port}...")
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                s.bind((self.local_ip, self.http_port))
                print(f"✓ HTTP port {self.http_port} is accessible")
        except Exception as e:
            print(f"✗ HTTP port {self.http_port} test failed: {e}")
        
        try:
            print(f"Testing WebSocket port {self.ws_port}...")
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                s.bind((self.local_ip, self.ws_port))
                print(f"✓ WebSocket port {self.ws_port} is accessible")
        except Exception as e:
            print(f"✗ WebSocket port {self.ws_port} test failed: {e}")
        
        # Check for common network interfaces
        try:
            import subprocess
            result = subprocess.run(['ipconfig'], capture_output=True, text=True, timeout=5)
            if 'Wireless LAN adapter Wi-Fi' in result.stdout:
                print("✓ WiFi adapter detected")
            else:
                print("⚠ WiFi adapter not clearly detected")
        except Exception as e:
            print(f"Network interface check failed: {e}")
    
    def update_connection_info(self):
        # Create a message with both HTTP and WebSocket info
        info = f"Connect: http://{self.local_ip}:{self.http_port}/mirrorindex.html"
        self.conn_label.config(text=info)
        print("=" * 50)
        print("CONNECTION INFORMATION:")
        print(f"Server IP: {self.local_ip}")
        print(f"HTTP Port: {self.http_port}")
        print(f"WebSocket Port: {self.ws_port}")
        print(f"Full URL: {info}")
        print("\nNETWORK DIAGNOSTICS:")
        self.run_network_diagnostics()
        print("\nTROUBLESHOoting TIPS:")
        print("1. Make sure both devices are on the same WiFi network")
        print("2. Check Windows Firewall settings")
        print("3. Try accessing from PC browser first")
        print("4. Verify mirrorindex.html exists in the same folder")
        print("5. Try disabling Windows Firewall temporarily")
        print(f"6. Test connectivity: ping {self.local_ip} from your phone")
        print("=" * 50)
    
    def is_port_in_use(self, port):
        """Check if a port is already in use."""
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                # Set SO_REUSEADDR to handle TIME_WAIT state
                s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                s.bind(('0.0.0.0', port))
                return False
            except OSError as e:
                print(f"Port {port} is in use: {e}")
                return True
    
    def find_available_port(self, start_port, max_attempts=10):
        """Find an available port starting from start_port."""
        port = start_port
        for _ in range(max_attempts):
            if not self.is_port_in_use(port):
                return port
            port += 1
        
        # If we couldn't find an available port, return None and handle it later
        print(f"Warning: Could not find an available port after {max_attempts} attempts")
        return None
    
    def open_browser(self):
        # Wait a moment for servers to start
        time.sleep(1.5)
        url = f"http://{self.local_ip}:{self.http_port}/mirrorindex.html"
        try:
            webbrowser.open(url)
            print(f"Browser opened at {url}")
        except Exception as e:
            print(f"Failed to open browser: {e}")
    
    def update_status(self, message):
        # Called from background threads too; root.after() is main-thread-only and
        # can raise. Never let a GUI-update failure kill a server/capture thread.
        try:
            self.root.after(0, lambda: self.status_label.config(text=message))
        except Exception:
            pass
    
    def start_http_server(self):
        try:
            # Create a handler with access to the WebSocket port and the app
            handler = lambda *args, **kwargs: CustomHTTPRequestHandler(
                *args, ws_port=self.ws_port, app=self, **kwargs
            )
            
            # Threaded so a slow request can't block others; SO_REUSEADDR avoids
            # "Address already in use" on restart.
            class ReuseAddrTCPServer(socketserver.ThreadingMixIn, socketserver.TCPServer):
                allow_reuse_address = True
                daemon_threads = True

            self.httpd = ReuseAddrTCPServer(("", self.http_port), handler)
            print(f"HTTP server started at http://{self.local_ip}:{self.http_port}")
            print(f"WebSocket port is {self.ws_port}")
            self.update_status(f"HTTP: {self.local_ip}:{self.http_port}, WS: {self.ws_port}")
            # Note: connection info / diagnostics are printed once from __init__;
            # doing it here would delay serve_forever() and can deadlock shutdown().
            try:
                self.httpd.serve_forever()
            finally:
                self.httpd.server_close()
                self.httpd = None
        except Exception as e:
            error_msg = f"HTTP server error: {str(e)}"
            print(error_msg)
            self.update_status(error_msg)
    
    async def handler(self, websocket, path=None):
        client_addr = f"{websocket.remote_address[0]}:{websocket.remote_address[1]}"
        print(f"New client connected from: {client_addr}")
        self.update_status(f"Client connected: {client_addr}")
        try:
            # Send frames and receive input (taps) concurrently.
            await asyncio.gather(
                self._send_frames(websocket),
                self._recv_input(websocket),
            )
        except websockets.exceptions.ConnectionClosed:
            print(f"Client {client_addr} disconnected")
            self.update_status("Client disconnected")
        except Exception as e:
            print(f"WebSocket error with client {client_addr}: {e}")
            self.update_status(f"WebSocket error: {str(e)}")

    async def _send_frames(self, websocket):
        while True:
            if self.mode_var.get() == "terminal":
                if self.latest_text is not None:
                    await websocket.send(json.dumps({
                        "type": "terminal",
                        "text": self.latest_text,
                        "fontSize": self.fontsize_var.get()
                    }))
            else:
                if self.latest_image:
                    await websocket.send(json.dumps({
                        "type": "screen",
                        "image": self.latest_image,
                        "format": self.latest_format,
                        "rotation": self.rotation_var.get()
                    }))
            await asyncio.sleep(1 / self.fps_var.get())

    async def _recv_input(self, websocket):
        """Receive control messages (taps) from the client and inject them."""
        async for raw in websocket:
            try:
                data = json.loads(raw)
            except Exception:
                continue
            if isinstance(data, dict) and data.get("type") == "input":
                try:
                    self._handle_input(data)
                except Exception as e:
                    print(f"Input inject error: {e}")

    def frame_for(self, src):
        """Look up a per-device source frame by ?src key; marks it active so the
        capture loop keeps refreshing it. src None/'default' -> the GUI source."""
        key = (getattr(self, "default_src_key", "screen")
               if (not src or src == "default") else src)
        self._src_requested[key] = time.time()
        return self.frames.get(key), key

    def inject_at(self, key, nx, ny, action="click", button="left"):
        """Inject a tap on a specific source (PC screen/window or Android)."""
        if self.active_mode == "terminal":
            return
        if not getattr(self, "control_enabled", False):
            return
        try:
            nx = min(max(float(nx), 0.0), 1.0)
            ny = min(max(float(ny), 0.0), 1.0)
        except (TypeError, ValueError):
            return
        if not key or key == "default":
            key = getattr(self, "default_src_key", "screen")
        frame = self.frames.get(key)
        if frame:
            region = frame.get("region")
            android = frame.get("android")
            asize = frame.get("android_size", (0, 0))
            rot = frame.get("rot", 0)
        else:
            region = getattr(self, "capture_region", None)
            android = getattr(self, "android_active", None)
            asize = getattr(self, "android_size", (0, 0))
            rot = getattr(self, "capture_rot", 0)
        nx, ny = _inverse_rot_norm(nx, ny, rot or 0)
        if android:
            aw, ah = asize
            if aw > 0 and ah > 0 and action in ("click", "up"):
                adb_tap(android, int(nx * aw), int(ny * ah))
            return
        if not (HAS_WIN32 or HAS_PYAUTOGUI) or not region:
            return
        left, top, w, h = region
        if w <= 0 or h <= 0:
            return
        sx, sy = int(left + nx * w), int(top + ny * h)
        if action == "move":
            input_move(sx, sy)
            return
        input_click(sx, sy, button=button)

    def _handle_input(self, data):
        """WebSocket control for the default source."""
        self.inject_at(None, data.get("x", 0), data.get("y", 0),
                       data.get("action", "click"),
                       "right" if data.get("button") == "right" else "left")
    
    def start_server(self):
        if self.ws_port is None:
            self.update_status("Error: Could not find an available WebSocket port")
            return
        
        async def run_websocket_server():
            """Async function to run the WebSocket server"""
            try:
                print(f"Starting WebSocket server on {self.local_ip}:{self.ws_port}")
                
                # Create a wrapper for the handler to make it compatible
                async def websocket_handler(websocket):
                    return await self.handler(websocket, None)

                self.ws_server = await websockets.serve(websocket_handler, "0.0.0.0", self.ws_port)
                print(f"WebSocket server successfully started on {self.local_ip}:{self.ws_port}")
                await self.ws_server.wait_closed()
            except Exception as e:
                error_msg = f"WebSocket server error: {str(e)}"
                print(error_msg)
                self.update_status(error_msg)
                traceback.print_exc()
        
        try:
            # Create a new event loop for this thread
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            self.ws_loop = loop

            status_msg = f"Servers running - WebSocket: {self.local_ip}:{self.ws_port}, HTTP: {self.local_ip}:{self.http_port}"
            print(status_msg)
            self.update_status(status_msg)

            # Run the WebSocket server until it is closed (via stop_servers)
            loop.run_until_complete(run_websocket_server())
        except Exception as e:
            error_msg = f"WebSocket server error: {str(e)}"
            print(error_msg)
            self.update_status(error_msg)
            traceback.print_exc()
        finally:
            try:
                self.ws_loop = None
                self.ws_server = None
                loop.close()
            except Exception:
                pass
    
    def capture_loop(self):
        while self.capturing:
            try:
                mode = self.mode_var.get()
                self.active_mode = mode  # plain mirror for the HTTP handler
                if mode == "terminal":
                    self.capture_terminal()
                    self._bump_version(self.latest_text)
                else:
                    self.capture_screen()
                    self._bump_version(self.latest_image)
                    # Also capture any EXTRA sources requested by other devices
                    # (?src=...) in the last 20s, so multiple Kindles can each
                    # view a different window/screen at once.
                    now = time.time()
                    for key in list(self._src_requested.keys()):
                        if now - self._src_requested[key] > 20:
                            self._src_requested.pop(key, None)
                            self.frames.pop(key, None)
                            self._frame_sigs.pop(key, None)
                            continue
                        if key == getattr(self, "default_src_key", None):
                            continue
                        try:
                            self.capture_one(key)
                        except Exception as e:
                            print(f"source {key} capture error: {e}")
                # Calculate sleep time to match desired FPS
                time.sleep(1 / self.fps_var.get())
            except Exception as e:
                print("Error in capture loop:", e)
                time.sleep(1)  # Wait a bit before retrying on error

    def _bump_version(self, content):
        """Increment frame_version only when the captured content actually changes."""
        sig = hash(content) if content is not None else None
        if sig != self._last_sig:
            self._last_sig = sig
            self.frame_version += 1

    def _default_src_key(self):
        """The source key for the GUI's current Capture selection."""
        selection = self.window_var.get()
        if selection in getattr(self, "monitor_map", {}):
            return "mon:%d" % self.monitor_map[selection]
        if selection in self.android_map:
            return "adb:" + self.android_map[selection]
        hwnd = self.window_map.get(selection) if selection != "Full Screen" else None
        return ("win:%d" % hwnd) if hwnd else "screen"

    def _grab_source(self, key):
        """Grab a raw PIL image for a source key -> (img, region, android, android_size)."""
        if key.startswith("mon:"):
            try:
                idx = int(key[4:])
            except ValueError:
                idx = 1
            img, region = grab_monitor(idx)
            return img, region, None, (0, 0)
        if key.startswith("adb:"):
            serial = key[4:]
            img = adb_screencap(serial)  # may raise; caller retries
            return img, None, serial, img.size
        if key.startswith("win:"):
            try:
                hwnd = int(key[4:])
            except ValueError:
                return None, None, None, (0, 0)
            if HAS_WIN32:
                if not win32gui.IsWindow(hwnd):
                    return None, None, None, (0, 0)
                img = capture_window(hwnd)
                region = None
                try:
                    if not win32gui.IsIconic(hwnd):
                        l, t, r, b = win32gui.GetWindowRect(hwnd)
                        region = (l, t, r - l, b - t)
                except Exception:
                    region = None
                return img, region, None, (0, 0)
            if HAS_QUARTZ:
                return _mac_capture_window(hwnd), _mac_window_region(hwnd), None, (0, 0)
            if HAS_WMCTRL:
                return _linux_capture_window(hwnd), _linux_window_region(hwnd), None, (0, 0)
            return None, None, None, (0, 0)
        # default: full screen
        img = grab_fullscreen()
        return img, (0, 0, img.width, img.height), None, (0, 0)

    def _process_and_encode(self, img):
        """Apply rotation/scale/e-ink and encode -> (b64, format, (w,h))."""
        rot = self.rotation_var.get()
        if rot:
            img = img.rotate(-rot, expand=True)
        sf = self.scale_var.get()
        if sf < 1.0:
            img = img.resize((int(img.width * sf), int(img.height * sf)),
                             Image.Resampling.LANCZOS)
        size = img.size
        eink = self.eink_var.get()
        buf = io.BytesIO()
        if eink == "bw":
            img.convert("L").convert("1", dither=Image.FLOYDSTEINBERG).save(buf, "PNG")
            fmt = "png"
        elif eink == "gray":
            ImageOps.autocontrast(img.convert("L")).save(buf, "JPEG", quality=self.quality_var.get())
            fmt = "jpeg"
        else:
            img.save(buf, "JPEG", quality=self.quality_var.get())
            fmt = "jpeg"
        return base64.b64encode(buf.getvalue()).decode("utf-8"), fmt, size

    def _store_source(self, key, is_default=False):
        """Capture a source, encode it, store in self.frames[key] (versioned)."""
        img, region, android, asize = self._grab_source(key)
        if img is None:
            return
        b64, fmt, size = self._process_and_encode(img)
        sig = hash(b64)
        prev = self.frames.get(key)
        ver = prev["version"] if prev else 0
        if sig != self._frame_sigs.get(key):
            ver += 1
            self._frame_sigs[key] = sig
        self.frames[key] = {"image": b64, "format": fmt, "size": size, "region": region,
                            "rot": self.rotation_var.get(), "android": android,
                            "android_size": asize, "version": ver}
        if is_default:
            self.latest_image = b64
            self.latest_format = fmt
            self.latest_size = size
            self.capture_region = region
            self.capture_rot = self.rotation_var.get()
            self.android_active = android
            self.android_size = asize

    def capture_screen(self):
        """Capture the GUI-selected (default) source into latest_* and frames[key]."""
        key = self._default_src_key()
        self.default_src_key = key
        self._store_source(key, is_default=True)

    def capture_one(self, key):
        """Capture an extra per-device source (requested via ?src=)."""
        self._store_source(key, is_default=False)

    def capture_terminal(self):
        """Grab the current text of a tmux session (via WSL on Windows, or native
        tmux on macOS/Linux) for Terminal mode."""
        distro = (self.distro_var.get() or "Ubuntu").strip()
        session = (self.session_var.get() or "claude").strip()
        if IS_WINDOWS:
            cmd = ["wsl.exe", "-d", distro, "tmux", "capture-pane", "-p", "-t", session]
        else:
            cmd = ["tmux", "capture-pane", "-p", "-t", session]
        # CREATE_NO_WINDOW keeps a console from flashing on every capture.
        no_window = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        try:
            proc = subprocess.run(cmd, capture_output=True, timeout=10,
                                  creationflags=no_window)
        except FileNotFoundError:
            self.latest_text = ("[wsl.exe not found]\n\n"
                                "Terminal mode needs WSL installed on Windows.")
            return
        except subprocess.TimeoutExpired:
            self.latest_text = "[Timed out reading the tmux session in WSL]"
            return

        if proc.returncode != 0:
            err = proc.stderr.decode("utf-8", "replace").strip()
            self.latest_text = (
                f"[Could not read tmux session '{session}' in WSL '{distro}']\n\n"
                f"{err}\n\n"
                f"In your WSL terminal run:\n"
                f"    tmux new -s {session}\n"
                f"then start `claude` inside it."
            )
        else:
            self.latest_text = proc.stdout.decode("utf-8", "replace")
    
    def test_connection(self):
        """Test if the server is accessible from the local network."""
        import urllib.request
        import urllib.error
        
        test_url = f"http://{self.local_ip}:{self.http_port}/get_ws_port"
        try:
            print(f"Testing connection to {test_url}...")
            response = urllib.request.urlopen(test_url, timeout=5)
            if response.getcode() == 200:
                print("✓ Server is accessible from local network")
                self.update_status("✓ Connection test successful")
            else:
                print(f"✗ Server returned status code: {response.getcode()}")
                self.update_status(f"✗ Test failed: HTTP {response.getcode()}")
        except urllib.error.URLError as e:
            print(f"✗ Connection test failed: {e}")
            self.update_status(f"✗ Connection test failed: {e}")
        except Exception as e:
            print(f"✗ Unexpected error during test: {e}")
            self.update_status(f"✗ Test error: {e}")
    
if __name__ == "__main__":
    root = tk.Tk()
    app = MirrorApp(root)
    root.mainloop()
