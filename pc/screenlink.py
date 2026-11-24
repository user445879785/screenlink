"""ScreenLink PC: shares this Windows screen with your iPhone over the local network.

No internet needed: the PC and the iPhone only have to be on the same Wi-Fi or hotspot.
Open the ScreenLink iPhone app (or Safari at the address shown) and enter the PIN.
"""
import ctypes
import hmac
import io
import json
import os
import random
import socket
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

VERSION = "1.0"
PORT = 8765
WIN = sys.platform == "win32"

if WIN:
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
    except Exception:
        try:
            ctypes.windll.user32.SetProcessDPIAware()
        except Exception:
            pass

import mss  # noqa: E402  (after DPI awareness so sizes are real pixels)
from PIL import Image, ImageDraw  # noqa: E402

HERE = os.path.dirname(os.path.abspath(sys.argv[0]))


def resource(name):
    base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, name)


# ---------------------------------------------------------------- settings / PIN
CONF_DIR = os.path.join(os.environ.get("APPDATA") or os.path.expanduser("~"), "ScreenLink")
CONF = os.path.join(CONF_DIR, "settings.json")


def load_conf():
    try:
        with open(CONF, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def save_conf(c):
    os.makedirs(CONF_DIR, exist_ok=True)
    with open(CONF, "w", encoding="utf-8") as f:
        json.dump(c, f)


conf = load_conf()
if not conf.get("pin"):
    conf["pin"] = "%06d" % random.SystemRandom().randrange(1000000)
    save_conf(conf)

state = {"viewers": {}, "bad": 0}


def new_pin():
    conf["pin"] = "%06d" % random.SystemRandom().randrange(1000000)
    save_conf(conf)


def local_ips():
    ips = set()
    try:
        for info in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET):
            ips.add(info[4][0])
    except Exception:
        pass
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("10.255.255.255", 1))
        ips.add(s.getsockname()[0])
        s.close()
    except Exception:
        pass
    return sorted(i for i in ips if not i.startswith("127.") and not i.startswith("169.254."))


# ---------------------------------------------------------------- screen capture
_tl = threading.local()


def grabber():
    if not hasattr(_tl, "sct"):
        _tl.sct = mss.mss()
    return _tl.sct


def monitors():
    m = grabber().monitors  # [0] = all screens, [1..] = each screen
    return m[1:] if len(m) > 1 else m


def cursor_pos():
    if not WIN:
        return None
    pt = wt.POINT()
    if ctypes.windll.user32.GetCursorPos(ctypes.byref(pt)):
        return pt.x, pt.y
    return None


def frame(mon_index, quality, max_w):
    mons = monitors()
    mon = mons[max(0, min(mon_index, len(mons) - 1))]
    shot = grabber().grab(mon)
    img = Image.frombytes("RGB", shot.size, shot.bgra, "raw", "BGRX")
    cp = cursor_pos()
    if cp:
        x, y = cp[0] - mon["left"], cp[1] - mon["top"]
        if 0 <= x < img.width and 0 <= y < img.height:
            d = ImageDraw.Draw(img)
            r = max(6, img.width // 220)
            d.ellipse((x - r, y - r, x + r, y + r), outline=(255, 255, 255), width=3)
            d.ellipse((x - r + 3, y - r + 3, x + r - 3, y + r - 3), outline=(255, 40, 40), width=2)
    if img.width > max_w:
        h = round(img.height * max_w / img.width)
        img = img.resize((max_w, h), Image.BILINEAR)
    buf = io.BytesIO()
    img.save(buf, "JPEG", quality=quality)
    return buf.getvalue()


# ---------------------------------------------------------------- input (Windows)
if WIN:
    import ctypes.wintypes as wt

    user32 = ctypes.windll.user32
    ULONG_PTR = ctypes.c_size_t

    class KEYBDINPUT(ctypes.Structure):
        _fields_ = [("wVk", wt.WORD), ("wScan", wt.WORD), ("dwFlags", wt.DWORD),
                    ("time", wt.DWORD), ("dwExtraInfo", ULONG_PTR)]

    class MOUSEINPUT(ctypes.Structure):
        _fields_ = [("dx", wt.LONG), ("dy", wt.LONG), ("mouseData", wt.DWORD),
                    ("dwFlags", wt.DWORD), ("time", wt.DWORD), ("dwExtraInfo", ULONG_PTR)]

    class HARDWAREINPUT(ctypes.Structure):
        _fields_ = [("uMsg", wt.DWORD), ("wParamL", wt.WORD), ("wParamH", wt.WORD)]

    class _U(ctypes.Union):
        _fields_ = [("ki", KEYBDINPUT), ("mi", MOUSEINPUT), ("hi", HARDWAREINPUT)]

    class INPUT(ctypes.Structure):
        _fields_ = [("type", wt.DWORD), ("u", _U)]

    def _send(*inputs):
        arr = (INPUT * len(inputs))(*inputs)
        user32.SendInput(len(inputs), arr, ctypes.sizeof(INPUT))

    def _mouse(flags, data=0):
        i = INPUT(type=0)
        i.u.mi = MOUSEINPUT(0, 0, ctypes.c_uint32(data & 0xFFFFFFFF).value, flags, 0, 0)
        _send(i)

    def _key(vk, up=False, ext=False):
        i = INPUT(type=1)
        i.u.ki = KEYBDINPUT(vk, 0, (2 if up else 0) | (1 if ext else 0), 0, 0)
        _send(i)

    def _uni(ch):
        code = ord(ch)
        units = [code] if code < 0x10000 else [0xD800 + ((code - 0x10000) >> 10), 0xDC00 + ((code - 0x10000) & 0x3FF)]
        for u in units:
            a, b = INPUT(type=1), INPUT(type=1)
            a.u.ki = KEYBDINPUT(0, u, 4, 0, 0)
            b.u.ki = KEYBDINPUT(0, u, 4 | 2, 0, 0)
            _send(a, b)
else:  # lets the server run on other systems for testing (no input)
    def _mouse(flags, data=0):
        pass

    def _key(vk, up=False, ext=False):
        pass

    def _uni(ch):
        pass

BTN = {"l": (0x2, 0x4), "r": (0x8, 0x10), "m": (0x20, 0x40)}
VK = {"enter": 0x0D, "backspace": 0x08, "tab": 0x09, "esc": 0x1B, "space": 0x20,
      "pgup": 0x21, "pgdn": 0x22, "end": 0x23, "home": 0x24, "left": 0x25, "up": 0x26,
      "right": 0x27, "down": 0x28, "insert": 0x2D, "delete": 0x2E, "win": 0x5B,
      "shift": 0x10, "ctrl": 0x11, "alt": 0x12, "menu": 0x5D}
EXT = {0x21, 0x22, 0x23, 0x24, 0x25, 0x26, 0x27, 0x28, 0x2D, 0x2E, 0x5B, 0x5D}
for n in range(1, 13):
    VK["f%d" % n] = 0x6F + n


def vk_of(name):
    name = name.lower()
    if name in VK:
        return VK[name]
    if len(name) == 1 and name.isalnum():
        return ord(name.upper())
    return None


def press(combo):
    keys = [vk_of(p) for p in combo.split("+")]
    if None in keys:
        return
    for k in keys:
        _key(k, False, k in EXT)
    for k in reversed(keys):
        _key(k, True, k in EXT)


def move_to(mon_index, nx, ny):
    mons = monitors()
    mon = mons[max(0, min(mon_index, len(mons) - 1))]
    x = mon["left"] + int(max(0.0, min(1.0, nx)) * (mon["width"] - 1))
    y = mon["top"] + int(max(0.0, min(1.0, ny)) * (mon["height"] - 1))
    if WIN:
        user32.SetCursorPos(x, y)


def do_input(ev, mon_index):
    t = ev.get("t")
    if "x" in ev and "y" in ev:
        move_to(mon_index, float(ev["x"]), float(ev["y"]))
    b = BTN.get(ev.get("b", "l"), BTN["l"])
    if t == "down":
        _mouse(b[0])
    elif t == "up":
        _mouse(b[1])
    elif t == "click":
        _mouse(b[0])
        _mouse(b[1])
    elif t == "wheel":
        _mouse(0x800, int(ev.get("d", 0)))
    elif t == "hwheel":
        _mouse(0x1000, int(ev.get("d", 0)))
    elif t == "text":
        for ch in str(ev.get("s", ""))[:2000]:
            if ch == "\n":
                press("enter")
            else:
                _uni(ch)
    elif t == "key":
        press(str(ev.get("k", "")))


# ---------------------------------------------------------------- web server
VIEWER = open(resource("viewer.html"), "rb").read()


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    server_version = "ScreenLink/" + VERSION

    def log_message(self, *a):
        pass

    def _send(self, code, body, ctype="application/json", extra=None):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("Access-Control-Allow-Origin", "*")
        for k, v in (extra or {}).items():
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(body)

    def _q(self):
        u = urlparse(self.path)
        return u.path, {k: v[0] for k, v in parse_qs(u.query).items()}

    def _authed(self, q):
        ok = hmac.compare_digest(q.get("k", ""), conf["pin"])
        if not ok:
            state["bad"] += 1
            if state["bad"] > 10:
                time.sleep(1.5)
            self._send(401, b'{"error":"pin"}')
            return False
        state["viewers"][self.client_address[0]] = time.time()
        return True

    def do_OPTIONS(self):
        self._send(204, b"", extra={"Access-Control-Allow-Methods": "GET, POST",
                                    "Access-Control-Allow-Headers": "Content-Type"})

    def do_GET(self):
        path, q = self._q()
        if path in ("/", "/index.html"):
            return self._send(200, VIEWER, "text/html; charset=utf-8")
        if path == "/hello":
            body = json.dumps({"app": "screenlink", "name": socket.gethostname(), "v": VERSION})
            return self._send(200, body.encode())
        if not self._authed(q):
            return
        if path == "/info":
            mons = [{"w": m["width"], "h": m["height"]} for m in monitors()]
            return self._send(200, json.dumps({"name": socket.gethostname(), "monitors": mons}).encode())
        if path == "/frame":
            try:
                jpg = frame(int(q.get("m", 0)), max(20, min(90, int(q.get("q", 65)))),
                            max(480, min(3840, int(q.get("w", 1600)))))
            except Exception as e:  # e.g. the PC is locked
                return self._send(503, json.dumps({"error": str(e)}).encode())
            return self._send(200, jpg, "image/jpeg")
        self._send(404, b"{}")

    def do_POST(self):
        path, q = self._q()
        if path != "/input" or not self._authed(q):
            if path != "/input":
                self._send(404, b"{}")
            return
        n = int(self.headers.get("Content-Length", 0))
        try:
            evs = json.loads(self.rfile.read(min(n, 200000)) or b"[]")
            m = int(q.get("m", 0))
            for ev in evs if isinstance(evs, list) else [evs]:
                do_input(ev, m)
        except Exception as e:
            return self._send(400, json.dumps({"error": str(e)}).encode())
        self._send(200, b"{}")


def serve(port=PORT):
    srv = ThreadingHTTPServer(("0.0.0.0", port), Handler)
    srv.daemon_threads = True
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv


# ---------------------------------------------------------------- window
def gui():
    import tkinter as tk

    root = tk.Tk()
    root.title("ScreenLink " + VERSION)
    root.geometry("440x330")
    root.configure(bg="#15151b")
    f = ("Segoe UI", 11)
    tk.Label(root, text="ScreenLink is sharing this screen", fg="#fff", bg="#15151b",
             font=("Segoe UI", 14, "bold")).pack(pady=(16, 4))
    tk.Label(root, text="On your iPhone open ScreenLink and tap Scan,\nor open one of these in Safari:",
             fg="#bbb", bg="#15151b", font=f).pack()
    addr = tk.Label(root, fg="#7d9bff", bg="#15151b", font=("Consolas", 13), justify="center")
    addr.pack(pady=6)
    pin = tk.Label(root, fg="#fff", bg="#15151b", font=("Segoe UI", 22, "bold"))
    pin.pack(pady=4)
    status = tk.Label(root, fg="#9a9", bg="#15151b", font=f)
    status.pack(pady=4)
    tk.Label(root, text="If Windows asks about the firewall, tick BOTH Private and Public.",
             fg="#d9a", bg="#15151b", font=("Segoe UI", 9)).pack(pady=(4, 0))
    row = tk.Frame(root, bg="#15151b")
    row.pack(pady=10)

    def refresh():
        ips = local_ips() or ["(no network)"]
        addr.config(text="\n".join("http://%s:%d" % (i, PORT) for i in ips[:4]))
        pin.config(text="PIN  " + conf["pin"])
        now = time.time()
        live = [ip for ip, t in state["viewers"].items() if now - t < 5]
        status.config(text=("Connected: " + ", ".join(live)) if live else "Waiting for your iPhone")
        root.after(1500, refresh)

    def change_pin():
        new_pin()
        refresh()

    tk.Button(row, text="New PIN", command=change_pin, width=12).pack(side="left", padx=6)
    tk.Button(row, text="Quit", command=root.destroy, width=12).pack(side="left", padx=6)
    refresh()
    root.mainloop()


def main():
    try:
        serve()
    except OSError as e:
        msg = "ScreenLink can't use port %d (is it already running?)\n%s" % (PORT, e)
        if WIN and "--console" not in sys.argv:
            ctypes.windll.user32.MessageBoxW(0, msg, "ScreenLink", 0x10)
        else:
            print(msg)
        return
    if "--console" in sys.argv:
        print("ScreenLink %s  PIN %s" % (VERSION, conf["pin"]))
        for i in local_ips():
            print("  http://%s:%d" % (i, PORT))
        try:
            while True:
                time.sleep(3600)
        except KeyboardInterrupt:
            return
    else:
        gui()


if __name__ == "__main__":
    main()
