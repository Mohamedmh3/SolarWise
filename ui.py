"""
SolarWise - Smart Solar Energy Advisor  (Tkinter UI)
====================================================
Run:   python solarwise_ui.py
UI only - standard library, no extra installs.

Screens: Dashboard | My system | Appliances | Best time | Notifications
Runtime results are produced by analysis.py from the pipeline dataset, settings, and appliance table.
"""
import math
import random
import datetime
import tkinter as tk
import tkinter.font as tkfont
from tkinter import ttk


# =====================================================================
#  Runtime data and analysis adapter
# =====================================================================
CITIES = ['Damascus', 'Aleppo', 'Homs', 'Hama', 'Latakia', 'Tartus', 'Daraa', 'Deir ez-Zor']
PRIORITIES = ['Essential', 'Important', 'Flexible']
try:
    from .analysis import analyze, load_appliances, runtime_info, warning
except ImportError:  # Running ui.py directly from its package directory.
    from analysis import analyze, load_appliances, runtime_info, warning

DEFAULT_APPLIANCES = load_appliances()


def get_results(system, appliances, day):
    """Return real dataset/settings/appliance-driven analysis for a UI day."""
    return analyze(system, appliances, day)


def get_warning(today, tomorrow):
    """Return a warning only when the real forecast drops materially."""
    return warning(today, tomorrow)

def fmt_time(t):
    h, m = int(t), int(round((t - int(t)) * 60))
    if m == 60:
        h, m = h + 1, 0
    return f"{h:02d}:{m:02d}"


# ----------------------------------------------------------------- theme --
C = {
    "bg": "#0B1326", "side": "#09101F", "card": "#111C35", "card2": "#172447",
    "border": "#223360", "text": "#EDF1FA", "muted": "#8A96B5", "dim": "#56628A",
    "sun": "#FFB547", "sun_hover": "#FFC870", "ember": "#FF7F3F",
    "sky": "#6FD3FF", "green": "#3FE0A1", "red": "#FF6B81", "amber": "#FFA64D",
}
FONT = "Segoe UI"
KIND = {  # colour + symbol per message type
    "success": (C["green"], "\u2713"), "warn": (C["amber"], "!"),
    "danger": (C["red"], "\u2601"), "info": (C["sky"], "i"),
}
PRIORITY_COLORS = {"Essential": C["red"], "Important": C["sky"], "Flexible": C["green"]}
_FONTS = {}


def F(size, weight="normal"):
    return (FONT, size, weight)


def font_obj(size, weight="normal"):
    key = (size, weight)
    if key not in _FONTS:
        _FONTS[key] = tkfont.Font(family=FONT, size=size, weight=weight)
    return _FONTS[key]


def lerp(c1, c2, t):
    t = max(0.0, min(1.0, t))
    a = [int(c1[i:i + 2], 16) for i in (1, 3, 5)]
    b = [int(c2[i:i + 2], 16) for i in (1, 3, 5)]
    return "#%02x%02x%02x" % tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))


def soc_color(v):
    return C["green"] if v >= 60 else C["sun"] if v >= 30 else C["red"]


def round_rect(cv, x1, y1, x2, y2, r=16, **kw):
    r = max(0, min(r, (x2 - x1) / 2, (y2 - y1) / 2))
    pts = [x1 + r, y1, x1 + r, y1, x2 - r, y1, x2 - r, y1, x2, y1, x2, y1 + r,
           x2, y1 + r, x2, y2 - r, x2, y2 - r, x2, y2, x2 - r, y2, x2 - r, y2,
           x1 + r, y2, x1 + r, y2, x1, y2, x1, y2 - r, x1, y2 - r, x1, y1 + r,
           x1, y1 + r, x1, y1]
    return cv.create_polygon(pts, smooth=True, **kw)


def mask_corners(cv, w, h, r, color):
    """Paint the outside of rounded corners so a full-bleed drawing looks rounded."""
    for cx, cy, a0, corner in ((r, r, 180, (0, 0)), (w - r, r, 270, (w, 0)),
                               (w - r, h - r, 0, (w, h)), (r, h - r, 90, (0, h))):
        pts = list(corner)
        for i in range(0, 91, 6):
            a = math.radians(a0 + i)
            pts += [cx + r * math.cos(a), cy + r * math.sin(a)]
        cv.create_polygon(pts, fill=color, outline=color)


def draw_sun(cv, cx, cy, r):
    for i in range(12):
        a = math.radians(i * 30)
        cv.create_line(cx + (r + 6) * math.cos(a), cy + (r + 6) * math.sin(a),
                       cx + (r + 13) * math.cos(a), cy + (r + 13) * math.sin(a),
                       fill="#FFD98A", width=3, capstyle="round")
    cv.create_oval(cx - r - 3, cy - r - 3, cx + r + 3, cy + r + 3, fill="#7A5A24", outline="")
    cv.create_oval(cx - r, cy - r, cx + r, cy + r, fill=C["sun"], outline="")
    cv.create_oval(cx - r * .55, cy - r * .6, cx + r * .25, cy + r * .2, fill="#FFD27F", outline="")


def draw_cloud(cv, cx, cy, s):
    for dy, col in ((4, "#9AA8C4"), (0, "#E6ECF7")):
        for x1, y1, x2, y2 in ((-1.1, -.2, -.1, .6), (-.6, -.75, .5, .45), (0, -.35, 1.0, .6)):
            cv.create_oval(cx + x1 * s, cy + y1 * s + dy, cx + x2 * s, cy + y2 * s + dy,
                           fill=col, outline="")
        cv.create_rectangle(cx - .7 * s, cy + .1 * s + dy, cx + .6 * s, cy + .6 * s + dy,
                            fill=col, outline="")


def pill(cv, x, y, text, fg, bg, size=10):
    tw = font_obj(size, "bold").measure(text)
    round_rect(cv, x, y - 15, x + tw + 26, y + 15, 15, fill=bg, outline="")
    cv.create_text(x + 13, y, text=text, anchor="w", fill=fg, font=F(size, "bold"))
    return x + tw + 26


# ------------------------------------------------------------ components --
class Card(tk.Canvas):
    """Rounded panel. Put widgets into `.inner`.
    fill=False -> height follows content;  fill=True -> content fills the card."""

    def __init__(self, master, pad=18, radius=16, color=None, border=None,
                 fill=False, height=None):
        super().__init__(master, bg=master.cget("bg"), highlightthickness=0, bd=0,
                         width=1, height=height or 2 * pad + 4)
        self.pad, self.radius, self.fill = pad, radius, fill
        self.color, self.border = color or C["card"], border or C["border"]
        self.inner = tk.Frame(self, bg=self.color)
        self._win = self.create_window(pad, pad, window=self.inner, anchor="nw")
        self.bind("<Configure>", self._redraw)
        if not fill:
            self.inner.bind("<Configure>", self._fit, add="+")
            self.after_idle(self._fit)

    def _fit(self, _e=None):
        h = self.inner.winfo_reqheight() + 2 * self.pad
        if int(float(self.cget("height"))) != h:
            self.configure(height=h)

    def _redraw(self, _e=None):
        w, h = self.winfo_width(), self.winfo_height()
        self.delete("bg")
        round_rect(self, 1, 1, w - 1, h - 1, self.radius, fill=self.color,
                   outline=self.border, tags="bg")
        self.tag_lower("bg")
        self.itemconfigure(self._win, width=max(1, w - 2 * self.pad))
        if self.fill:
            self.itemconfigure(self._win, height=max(1, h - 2 * self.pad))

    def set_border(self, color):
        self.border = color
        self._redraw()


class PillButton(tk.Canvas):
    STYLES = {
        "primary": (C["sun"], C["sun_hover"], C["bg"], ""),
        "ghost": (C["card2"], C["border"], C["text"], C["border"]),
        "danger": ("#3A1E33", "#4A2440", C["red"], "#6A2E48"),
    }

    def __init__(self, master, text, command=None, kind="primary", width=None, height=42):
        width = width or font_obj(10, "bold").measure(text) + 44
        super().__init__(master, width=width, height=height, bg=master.cget("bg"),
                         highlightthickness=0, cursor="hand2")
        self.text, self.command, self.kind = text, command, kind
        self.bind("<Enter>", lambda e: self._draw(True))
        self.bind("<Leave>", lambda e: self._draw(False))
        self.bind("<ButtonRelease-1>", lambda e: self.command and self.command())
        self._draw(False)

    def _draw(self, hover):
        fill, hov, fg, outline = self.STYLES[self.kind]
        w, h = int(self["width"]), int(self["height"])
        self.delete("all")
        round_rect(self, 1, 1, w - 1, h - 1, h / 2, fill=hov if hover else fill,
                   outline=outline or (hov if hover else fill))
        self.create_text(w / 2, h / 2, text=self.text, fill=fg, font=F(10, "bold"))


class Chip(tk.Canvas):
    def __init__(self, master, text, command=None, selected=False, color=None, height=34):
        w = font_obj(10, "bold").measure(text) + 32
        super().__init__(master, width=w, height=height, bg=master.cget("bg"),
                         highlightthickness=0, cursor="hand2")
        self.text, self.command, self.selected = text, command, selected
        self.color, self.hover = color or C["sun"], False
        self.bind("<Enter>", lambda e: self._hover(True))
        self.bind("<Leave>", lambda e: self._hover(False))
        self.bind("<ButtonRelease-1>", lambda e: self.command and self.command())
        self.draw()

    def _hover(self, v):
        self.hover = v
        self.draw()

    def set_selected(self, v):
        self.selected = v
        self.draw()

    def draw(self):
        w, h = int(self["width"]), int(self["height"])
        self.delete("all")
        if self.selected:
            fill, outline, fg = self.color, self.color, C["bg"]
        else:
            fill = C["card2"]
            outline = self.color if self.hover else C["border"]
            fg = C["text"] if self.hover else C["muted"]
        round_rect(self, 1, 1, w - 1, h - 1, h / 2, fill=fill, outline=outline)
        self.create_text(w / 2, h / 2, text=self.text, fill=fg, font=F(10, "bold"))


class ChipGroup(tk.Frame):
    def __init__(self, master, options, value=None, command=None, per_row=6, colors=None):
        super().__init__(master, bg=master.cget("bg"))
        self.command, self.per_row, self.colors = command, per_row, colors or {}
        self.value, self.chips = value, {}
        self.set_options(options, value)

    def set_options(self, options, value=None):
        for ch in self.chips.values():
            ch.destroy()
        self.chips = {}
        if value is not None:
            self.value = value
        if options and self.value not in options:
            self.value = options[0]
        for i, o in enumerate(options):
            ch = Chip(self, o, command=lambda o=o: self.select(o),
                      selected=(o == self.value), color=self.colors.get(o))
            ch.grid(row=i // self.per_row, column=i % self.per_row,
                    padx=(0, 8), pady=(0, 8), sticky="w")
            self.chips[o] = ch

    def select(self, o, notify=True):
        self.value = o
        for k, ch in self.chips.items():
            ch.set_selected(k == o)
        if notify and self.command:
            self.command(o)


class Segmented(tk.Canvas):
    def __init__(self, master, options, command=None, width=220, height=40):
        super().__init__(master, width=width, height=height, bg=master.cget("bg"),
                         highlightthickness=0, cursor="hand2")
        self.options, self.command, self.value = options, command, options[0]
        self.bind("<ButtonRelease-1>", self._click)
        self.draw()

    def set(self, v):
        self.value = v
        self.draw()

    def draw(self):
        w, h = int(self["width"]), int(self["height"])
        self.delete("all")
        round_rect(self, 1, 1, w - 1, h - 1, h / 2, fill=C["card2"], outline=C["border"])
        seg = (w - 8) / len(self.options)
        for i, o in enumerate(self.options):
            x1 = 4 + i * seg
            on = o == self.value
            if on:
                round_rect(self, x1, 4, x1 + seg, h - 4, (h - 8) / 2, fill=C["sun"], outline="")
            self.create_text(x1 + seg / 2, h / 2, text=o, font=F(10, "bold"),
                             fill=C["bg"] if on else C["muted"])

    def _click(self, e):
        n = len(self.options)
        i = max(0, min(n - 1, int((e.x - 4) / ((int(self["width"]) - 8) / n))))
        if self.options[i] != self.value:
            self.set(self.options[i])
            if self.command:
                self.command(self.options[i])


class Slider(tk.Canvas):
    def __init__(self, master, value=50, command=None):
        super().__init__(master, height=34, width=1, bg=master.cget("bg"),
                         highlightthickness=0, cursor="hand2")
        self.value, self.command = value, command
        self.bind("<Configure>", lambda e: self.draw())
        self.bind("<Button-1>", self._set)
        self.bind("<B1-Motion>", self._set)

    def _set(self, e):
        w = self.winfo_width()
        self.value = int(round(max(0, min(100, (e.x - 14) / max(1, w - 28) * 100))))
        self.draw()
        if self.command:
            self.command(self.value)

    def set(self, v):
        self.value = v
        self.draw()

    def draw(self):
        self.delete("all")
        w, h = self.winfo_width(), self.winfo_height()
        if w < 40:
            return
        p, y = 14, h / 2
        col = soc_color(self.value)
        round_rect(self, p, y - 4, w - p, y + 4, 4, fill=C["card2"], outline="")
        x = p + (w - 2 * p) * self.value / 100
        if x > p + 6:
            round_rect(self, p, y - 4, x, y + 4, 4, fill=col, outline="")
        self.create_oval(x - 11, y - 11, x + 11, y + 11, fill=C["text"], outline=col, width=4)


class Field(tk.Frame):
    def __init__(self, master, label, unit="", value=""):
        super().__init__(master, bg=master.cget("bg"))
        tk.Label(self, text=label, bg=self["bg"], fg=C["muted"], font=F(10)).pack(anchor="w", pady=(0, 6))
        self.box = Card(self, pad=10, radius=12, color=C["card2"])
        self.box.pack(fill="x")
        self.var = tk.StringVar(value=str(value))
        if unit:
            tk.Label(self.box.inner, text=unit, bg=C["card2"], fg=C["muted"],
                     font=F(10, "bold")).pack(side="right", padx=(0, 4))
        self.entry = tk.Entry(self.box.inner, textvariable=self.var, bg=C["card2"], fg=C["text"],
                              insertbackground=C["sun"], relief="flat", bd=0, width=6,
                              highlightthickness=0, font=F(13))
        self.entry.pack(side="left", fill="x", expand=True, padx=(4, 0))
        self.entry.bind("<FocusIn>", lambda e: self.box.set_border(C["sun"]))
        self.entry.bind("<FocusOut>", lambda e: self.box.set_border(C["border"]))

    def number(self, minimum=0.0):
        try:
            v = float(self.var.get().strip().replace(",", "."))
            if v <= minimum:
                raise ValueError
            return v
        except ValueError:
            self.box.set_border(C["red"])
            raise

    def text(self):
        return self.var.get().strip()


class Badge(tk.Canvas):
    def __init__(self, master, symbol, color, size=36):
        bg = master.cget("bg")
        super().__init__(master, width=size, height=size, bg=bg, highlightthickness=0)
        round_rect(self, 1, 1, size - 1, size - 1, size * .34, fill=lerp(color, bg, .8), outline="")
        self.create_text(size / 2, size / 2, text=symbol, fill=color, font=F(int(size * .36), "bold"))


class RingGauge(tk.Canvas):
    def __init__(self, master, size=74, thickness=8):
        super().__init__(master, width=size, height=size, bg=master.cget("bg"), highlightthickness=0)
        self.size, self.t = size, thickness

    def set(self, pct):
        s, t = self.size, self.t
        p = t / 2 + 2
        self.delete("all")
        self.create_oval(p, p, s - p, s - p, outline=C["card2"], width=t)
        ext = -3.6 * pct if pct < 100 else -359.9
        self.create_arc(p, p, s - p, s - p, start=90, extent=ext, style="arc",
                        outline=soc_color(pct), width=t)
        self.create_text(s / 2, s / 2, text=f"{pct:.0f}%", fill=C["text"], font=F(12, "bold"))


def message_row(parent, msg, wrap=260):
    col, sym = KIND[msg["kind"]]
    bg = parent.cget("bg")
    row = tk.Frame(parent, bg=bg)
    row.pack(fill="x", pady=(0, 12))
    Badge(row, sym, col, size=32).pack(side="left", anchor="n")
    tx = tk.Frame(row, bg=bg)
    tx.pack(side="left", fill="x", expand=True, padx=(12, 0))
    tk.Label(tx, text=msg["title"], font=F(10, "bold"), fg=C["text"], bg=bg,
             anchor="w", justify="left", wraplength=wrap).pack(anchor="w")
    tk.Label(tx, text=msg["text"], font=F(9), fg=C["muted"], bg=bg, anchor="w",
             justify="left", wraplength=wrap).pack(anchor="w", pady=(2, 0))
    return row


# ------------------------------------------------------- drawn visuals --
class SunArc(tk.Canvas):
    """Dashboard hero: the sun's path across the sky, coloured by expected output."""

    def __init__(self, master, height=214):
        super().__init__(master, height=height, width=1, bg=master.cget("bg"),
                         highlightthickness=0, bd=0)
        self.data = None
        self.bind("<Configure>", lambda e: self.draw())

    def set(self, **data):
        self.data = data
        self.draw()

    def draw(self):
        self.delete("all")
        w, h = self.winfo_width(), self.winfo_height()
        if w < 200 or not self.data:
            return
        d = self.data
        r, day, pv = d["res"], d["day"], d["pv"]
        lvl = r["level"]
        top = "#0E1834"
        glow = {"HIGH": "#5C3B1D", "MEDIUM": "#3F3448", "LOW": "#27344F"}[lvl]
        for y in range(0, h, 3):
            self.create_rectangle(0, y, w, y + 3, fill=lerp(top, glow, (y / h) ** 1.7), outline="")
        rnd = random.Random(3)
        for _ in range(28):
            x, y, s = rnd.uniform(w * .5, w), rnd.uniform(8, h * .5), rnd.choice((1, 1, 1.6))
            self.create_oval(x - s, y - s, x + s, y + s, outline="",
                             fill=lerp("#FFFFFF", top, rnd.uniform(.35, .8)))

        # text side
        head = {"HIGH": "Strong sun", "MEDIUM": "Patchy sun", "LOW": "Cloudy skies"}[lvl]
        body = {
            "HIGH": f"Your {pv:g} kW panels should make about {r['total_gen']:.1f} kWh. "
                    f"Plenty for heavy appliances in the midday window.",
            "MEDIUM": f"Your {pv:g} kW panels should make about {r['total_gen']:.1f} kWh. "
                      f"Run heavy appliances only in the sunniest hours.",
            "LOW": f"Only about {r['total_gen']:.1f} kWh expected, {r['ratio']:.0%} of a "
                   f"clear day. Keep the battery for essentials.",
        }[lvl]
        self.create_text(32, 50, text=f"{head} {day}", anchor="w", fill=C["text"], font=F(24, "bold"))
        self.create_text(32, 80, text=body, anchor="nw", fill="#C9D2E8", font=F(11),
                         width=min(440, w * .44))
        lc = {"HIGH": C["sun"], "MEDIUM": C["amber"], "LOW": C["sky"]}[lvl]
        x = pill(self, 32, h - 36, f"Solar availability: {lvl.title()}", lc, lerp(lc, glow, .8))
        if d.get("best"):
            name, b = d["best"]
            pill(self, x + 10, h - 36,
                 f"{name}  {fmt_time(b['start'])}\u2013{fmt_time(b['end'])}",
                 C["green"], lerp(C["green"], glow, .82))

        # arc side
        x0, x1, horizon = w * .52, w - 56, h - 44
        cx, rx, ry = (x0 + x1) / 2, (x1 - x0) / 2, horizon - 40
        sr, ss = r["sunrise"], r["sunset"]

        def pt(t):
            a = math.pi * (1 - (t - sr) / (ss - sr))
            return cx + rx * math.cos(a), horizon - ry * math.sin(a)

        self.create_line(x0 - 26, horizon, x1 + 26, horizon, fill=lerp(C["sun"], glow, .55))
        dashed = []
        for i in range(61):
            dashed += pt(sr + (ss - sr) * i / 60)
        self.create_line(dashed, fill=C["dim"], dash=(2, 4))
        gen = r["generation"]
        gmax = max(max(gen), .01)
        n = 48
        for i in range(n):
            t0, t1 = sr + (ss - sr) * i / n, sr + (ss - sr) * (i + 1) / n
            f = gen[min(23, int((t0 + t1) / 2))] / gmax
            self.create_line(*pt(t0), *pt(t1), fill=lerp(C["dim"], C["sun"], f),
                             width=2 + 5 * f, capstyle="round")
        if d.get("best"):
            b = d["best"][1]
            s0, s1 = max(sr, b["start"]), min(ss, b["end"])
            seg = []
            for i in range(13):
                seg += pt(s0 + (s1 - s0) * i / 12)
            self.create_line(seg, fill=C["green"], width=9, capstyle="round", smooth=True)
        now = datetime.datetime.now()
        now_h = now.hour + now.minute / 60
        focus = now_h if (day == "today" and sr < now_h < ss) else r["peak_hour"] + .5
        sx, sy = pt(max(sr + .25, min(ss - .25, focus)))
        draw_sun(self, sx, sy, 15)
        if lvl != "HIGH":
            draw_cloud(self, sx + 12, sy + 10, 17 if lvl == "MEDIUM" else 25)
        self.create_text(pt(sr)[0], horizon + 18, text=f"Sunrise {fmt_time(sr)}",
                         fill=C["muted"], font=F(9))
        self.create_text(pt(ss)[0], horizon + 18, text=f"Sunset {fmt_time(ss)}",
                         fill=C["muted"], font=F(9))
        mask_corners(self, w, h, 22, self.master.cget("bg"))


class EnergyChart(tk.Canvas):
    """Hourly solar output (area) vs household demand (steps), with hover readout."""

    def __init__(self, master):
        super().__init__(master, width=1, height=1, bg=master.cget("bg"), highlightthickness=0)
        self.gen = self.dem = None
        self.window = None
        self.geom = None
        self.bind("<Configure>", lambda e: self.draw())
        self.bind("<Motion>", self._hover)
        self.bind("<Leave>", lambda e: self.delete("hover"))

    def set_data(self, gen, dem, window=None):
        self.gen, self.dem, self.window = gen, dem, window
        self.draw()

    def draw(self):
        self.delete("all")
        w, h = self.winfo_width(), self.winfo_height()
        if w < 80 or h < 60 or not self.gen:
            return
        L, R, T, B = 40, 24, 16, 26
        top_v = max(max(self.gen), max(self.dem), .5) * 1.2
        step = .5 if top_v <= 3 else 1.0
        vmax = math.ceil(top_v / step) * step
        X = lambda t: L + t / 24 * (w - L - R)
        Y = lambda v: h - B - v / vmax * (h - T - B)
        self.geom = (L, R, X, Y)
        bg = self["bg"]
        for i in range(int(round(vmax / step)) + 1):
            v = i * step
            self.create_line(L, Y(v), w - R, Y(v), fill=lerp(C["border"], bg, .35))
            self.create_text(L - 8, Y(v), text=f"{v:.1f}", anchor="e", fill=C["dim"], font=F(8))
        for hr in range(0, 25, 3):
            self.create_text(X(hr), h - B + 14, text=f"{hr:02d}:00", fill=C["dim"], font=F(8))
        if self.window:
            s, e = self.window["start"], self.window["end"]
            self.create_rectangle(X(s), T, X(e), h - B, fill=lerp(C["green"], bg, .86), outline="")
            self.create_line(X(s), T, X(s), h - B, fill=lerp(C["green"], bg, .5))
            self.create_line(X(e), T, X(e), h - B, fill=lerp(C["green"], bg, .5))
        pts = []
        for i, g in enumerate(self.gen):
            pts += [X(i + .5), Y(g)]
        base = Y(0)
        area = [X(.5), base, X(.5), base] + pts + [X(23.5), base, X(23.5), base]
        self.create_polygon(area, fill=lerp(C["sun"], bg, .8), outline="", smooth=True)
        self.create_line(pts, fill=C["sun"], width=3, smooth=True)
        steps = []
        for i, dv in enumerate(self.dem):
            steps += [X(i), Y(dv), X(i + 1), Y(dv)]
        self.create_line(steps, fill=C["sky"], width=2, dash=(5, 3))
        pk = max(range(24), key=lambda i: self.gen[i])
        px, py = X(pk + .5), Y(self.gen[pk])
        self.create_oval(px - 5, py - 5, px + 5, py + 5, fill=C["sun"], outline=bg, width=2)
        self.create_text(px, py - 14, text=f"{self.gen[pk]:.1f} kW", fill=C["sun"], font=F(9, "bold"))

    def _hover(self, e):
        self.delete("hover")
        if not self.geom:
            return
        L, R, X, Y = self.geom
        w, h = self.winfo_width(), self.winfo_height()
        hr = int((e.x - L) / max(1, w - L - R) * 24)
        if not 0 <= hr < 24:
            return
        x = X(hr + .5)
        self.create_line(x, 16, x, h - 26, fill=C["muted"], dash=(2, 3), tags="hover")
        for v, col in ((self.gen[hr], C["sun"]), (self.dem[hr], C["sky"])):
            self.create_oval(x - 4, Y(v) - 4, x + 4, Y(v) + 4, fill=col, outline="", tags="hover")
        bx = x + 14 if x < w - 190 else x - 174
        round_rect(self, bx, 18, bx + 160, 94, 10, fill=C["card2"], outline=C["border"], tags="hover")
        self.create_text(bx + 12, 34, text=f"{hr:02d}:00 to {hr + 1:02d}:00", anchor="w",
                         fill=C["text"], font=F(9, "bold"), tags="hover")
        self.create_text(bx + 12, 56, text=f"Solar   {self.gen[hr]:.2f} kW", anchor="w",
                         fill=C["sun"], font=F(9), tags="hover")
        self.create_text(bx + 12, 76, text=f"Home    {self.dem[hr]:.2f} kW", anchor="w",
                         fill=C["sky"], font=F(9), tags="hover")


class Timeline(tk.Canvas):
    """Best-time page: one block per daylight hour, brighter = more sun."""

    def __init__(self, master):
        super().__init__(master, height=112, width=1, bg=master.cget("bg"), highlightthickness=0)
        self.data = None
        self.bind("<Configure>", lambda e: self.draw())

    def set(self, gen, best, alt, show_now):
        self.data = (gen, best, alt, show_now)
        self.draw()

    def draw(self):
        self.delete("all")
        w = self.winfo_width()
        if w < 100 or not self.data:
            return
        gen, best, alt, show_now = self.data
        s0, s1, top, bh = 5, 20, 30, 46
        X = lambda t: 6 + (t - s0) / (s1 - s0) * (w - 12)
        gmax = max(max(gen), .01)
        for hr in range(s0, s1):
            f = gen[hr] / gmax
            col = lerp(C["card2"], C["sun"], f ** .8) if gen[hr] > .02 else C["card2"]
            round_rect(self, X(hr) + 2, top, X(hr + 1) - 2, top + bh, 8, fill=col, outline="")
            self.create_text((X(hr) + X(hr + 1)) / 2, top + bh + 16, text=f"{hr:02d}",
                             fill=C["dim"], font=F(8))
        for win, col, label, width in ((alt, C["sky"], "Alternative", 2), (best, C["green"], "Best", 3)):
            if not win:
                continue
            a, b = X(max(s0, win["start"])), X(min(s1, win["end"]))
            round_rect(self, a - 1, top - 5, b + 1, top + bh + 5, 10, fill="", outline=col, width=width)
            self.create_text((a + b) / 2, top - 16, text=label, fill=col, font=F(9, "bold"))
        if show_now:
            n = datetime.datetime.now()
            t = n.hour + n.minute / 60
            if s0 <= t <= s1:
                self.create_line(X(t), top - 6, X(t), top + bh + 6, fill=C["red"], width=2)


class FlowDiagram(tk.Canvas):
    """My-system page: animated energy flow sun -> panels -> inverter -> home / battery."""

    def __init__(self, master, app):
        super().__init__(master, width=1, height=1, bg=master.cget("bg"), highlightthickness=0)
        self.app, self.phase, self.paths = app, 0.0, []
        self.bind("<Configure>", lambda e: self.draw())
        self.after(60, self._animate)

    def draw(self):
        self.delete("all")
        w, h = self.winfo_width(), self.winfo_height()
        if w < 200 or h < 200:
            return
        s, r = self.app.system, self.app.res["today"]
        pos = {"sun": (.17, .2), "pv": (.17, .55), "inv": (.53, .55), "home": (.8, .24), "bat": (.8, .86)}
        P = {k: (x * w, y * h) for k, (x, y) in pos.items()}
        self.paths = []
        for a, b, col in (("sun", "pv", C["sun"]), ("pv", "inv", C["sun"]),
                          ("inv", "home", C["sky"]), ("inv", "bat", C["green"])):
            (x1, y1), (x2, y2) = P[a], P[b]
            self.create_line(x1, y1, x2, y2, fill=lerp(col, self["bg"], .7), width=3)
            self.paths.append((x1, y1, x2, y2, col))
        nodes = {
            "sun": ("Sun", f"{max(r['weather']['irradiance']):.0f} W/m\u00b2 peak", C["sun"]),
            "pv": ("Solar panels", f"{s['pv_kw']:g} kW", C["sun"]),
            "inv": ("Inverter", f"{s['inverter_kw']:g} kW max", C["ember"]),
            "home": ("Home", f"{r['total_demand']:.1f} kWh/day", C["sky"]),
            "bat": ("Battery", f"{s['soc']}% of {s['battery_kwh']:g} kWh", soc_color(s["soc"])),
        }
        bw, bh = min(184, w * .31), 74
        for k, (title, value, col) in nodes.items():
            x, y = P[k]
            round_rect(self, x - bw / 2, y - bh / 2, x + bw / 2, y + bh / 2, 14,
                       fill=C["card2"], outline=lerp(col, C["card2"], .45), width=2, tags="node")
            ix, iy = x - bw / 2 + 26, y
            if k == "sun":
                self.create_oval(ix - 11, iy - 11, ix + 11, iy + 11, fill=col, outline="", tags="node")
            elif k == "pv":
                for gx in range(3):
                    for gy in range(2):
                        self.create_rectangle(ix - 13 + gx * 9, iy - 9 + gy * 9, ix - 6 + gx * 9,
                                              iy - 2 + gy * 9, fill=col, outline="", tags="node")
            elif k == "inv":
                self.create_text(ix, iy, text="\u26a1", fill=col, font=F(18, "bold"), tags="node")
            elif k == "home":
                self.create_polygon(ix - 12, iy - 1, ix, iy - 12, ix + 12, iy - 1, fill=col, tags="node")
                self.create_rectangle(ix - 8, iy - 1, ix + 8, iy + 11, fill=col, outline="", tags="node")
            else:
                self.create_rectangle(ix - 13, iy - 8, ix + 11, iy + 8, outline=col, width=2, tags="node")
                self.create_rectangle(ix + 11, iy - 3, ix + 14, iy + 3, fill=col, outline="", tags="node")
                self.create_rectangle(ix - 11, iy - 6, ix - 11 + 20 * s["soc"] / 100, iy + 6,
                                      fill=col, outline="", tags="node")
            self.create_text(ix + 22, y - 11, text=title, anchor="w", fill=C["muted"],
                             font=F(9), tags="node")
            self.create_text(ix + 22, y + 10, text=value, anchor="w", fill=C["text"],
                             font=F(10, "bold"), tags="node")

    def _animate(self):
        self.phase = (self.phase + .01) % 1
        self.delete("dot")
        if self.winfo_ismapped():
            for x1, y1, x2, y2, col in self.paths:
                for k in range(3):
                    t = (self.phase + k / 3) % 1
                    x, y = x1 + (x2 - x1) * t, y1 + (y2 - y1) * t
                    self.create_oval(x - 4, y - 4, x + 4, y + 4, fill=col, outline="", tags="dot")
            self.tag_raise("node")
        self.after(40, self._animate)


class Toast(tk.Toplevel):
    """In-app notification that slides in at the bottom-right of the window."""

    def __init__(self, app, title, text, kind="info"):
        super().__init__(app)
        self.app = app
        self.overrideredirect(True)
        self.attributes("-topmost", True)
        key = "#010203"
        try:
            self.attributes("-transparentcolor", key)
            bg = key
        except tk.TclError:
            bg = C["bg"]
        self.configure(bg=bg)
        col, sym = KIND[kind]
        W = 380
        cv = tk.Canvas(self, width=W, height=100, bg=bg, highlightthickness=0)
        cv.pack()
        cv.create_text(80, 28, text=title, anchor="w", fill=C["text"], font=F(11, "bold"))
        body = cv.create_text(80, 42, text=text, anchor="nw", fill=C["muted"], font=F(9), width=W - 110)
        H = max(92, cv.bbox(body)[3] + 18)
        cv.configure(height=H)
        cv.create_text(W - 18, 18, text="\u2715", fill=C["dim"], font=F(10))
        cv.create_text(40, H / 2, text=sym, fill=col, font=F(18, "bold"), tags="badge")
        round_rect(cv, 2, 2, W - 2, H - 2, 16, fill=C["card2"], outline=lerp(col, C["card2"], .4),
                   width=2, tags="back")
        round_rect(cv, 16, H / 2 - 24, 64, H / 2 + 24, 14, fill=lerp(col, C["card2"], .78), outline="", tags="back")
        cv.tag_lower("back")
        cv.bind("<Button-1>", lambda e: self.close())
        self.W, self.H, self.alpha = W, H, 0.0
        self.place_me()
        self._fade(1)
        self.after(5200, self.close)

    def place_me(self):
        i = self.app.toasts.index(self) if self in self.app.toasts else len(self.app.toasts)
        x = self.app.winfo_rootx() + self.app.winfo_width() - self.W - 24
        y = self.app.winfo_rooty() + self.app.winfo_height() - (self.H + 12) * (i + 1) - 12
        self.geometry(f"+{x}+{y}")

    def _fade(self, direction):
        self.alpha = max(0.0, min(1.0, self.alpha + .12 * direction))
        try:
            self.attributes("-alpha", self.alpha)
        except tk.TclError:
            pass
        if 0 < self.alpha < 1:
            self.after(16, lambda: self._fade(direction))
        elif self.alpha <= 0:
            self._destroy()

    def close(self):
        if self.winfo_exists():
            self._fade(-1) if self.alpha > 0 else self._destroy()

    def _destroy(self):
        if self in self.app.toasts:
            self.app.toasts.remove(self)
        if self.winfo_exists():
            self.destroy()
        for t in self.app.toasts:
            t.place_me()


class NavItem(tk.Frame):
    def __init__(self, master, icon, text, command):
        super().__init__(master, bg=C["side"], cursor="hand2")
        self.active = False
        self.bar = tk.Frame(self, bg=C["side"], width=4)
        self.bar.pack(side="left", fill="y")
        self.icon = tk.Label(self, text=icon, font=F(13), width=2, bg=C["side"], fg=C["muted"])
        self.icon.pack(side="left", padx=(14, 8), pady=10)
        self.lbl = tk.Label(self, text=text, font=F(11, "bold"), bg=C["side"], fg=C["muted"])
        self.lbl.pack(side="left")
        self.badge = tk.Label(self, text="", font=F(8, "bold"), bg=C["red"], fg=C["bg"], padx=6)
        for wdg in (self, self.icon, self.lbl, self.badge):
            wdg.bind("<Button-1>", lambda e: command())
            wdg.bind("<Enter>", lambda e: self._paint(hover=True))
            wdg.bind("<Leave>", lambda e: self._paint())

    def set_active(self, v):
        self.active = v
        self._paint()

    def set_badge(self, n):
        if n:
            self.badge.config(text=str(n))
            self.badge.pack(side="right", padx=12)
        else:
            self.badge.pack_forget()

    def _paint(self, hover=False):
        bg = C["card"] if self.active else ("#0F1830" if hover else C["side"])
        fg = C["text"] if (self.active or hover) else C["muted"]
        for wdg in (self, self.icon, self.lbl):
            wdg.config(bg=bg)
        self.icon.config(fg=C["sun"] if self.active else fg)
        self.lbl.config(fg=fg)
        self.bar.config(bg=C["sun"] if self.active else bg)


# ----------------------------------------------------------------- pages --
class Page(tk.Frame):
    def __init__(self, parent, app):
        super().__init__(parent, bg=C["bg"])
        self.app = app
        self.build()

    def header(self, title, subtitle):
        h = tk.Frame(self, bg=C["bg"])
        h.pack(fill="x", pady=(0, 18))
        left = tk.Frame(h, bg=C["bg"])
        left.pack(side="left")
        tk.Label(left, text=title, font=F(21, "bold"), fg=C["text"], bg=C["bg"]).pack(anchor="w")
        tk.Label(left, text=subtitle, font=F(10), fg=C["muted"], bg=C["bg"]).pack(anchor="w", pady=(2, 0))
        self.header_right = tk.Frame(h, bg=C["bg"])
        self.header_right.pack(side="right")

    def body(self):
        b = tk.Frame(self, bg=C["bg"])
        b.pack(fill="both", expand=True)
        return b

    def build(self):
        pass

    def refresh(self):
        pass


class Metric(tk.Frame):
    def __init__(self, master, label, gauge=False):
        super().__init__(master, bg=master.cget("bg"))
        bg = self["bg"]
        if gauge:
            self.gauge = RingGauge(self)
            self.gauge.pack(side="left", padx=(0, 14))
        box = tk.Frame(self, bg=bg)
        box.pack(side="left", fill="x", expand=True)
        tk.Label(box, text=label, font=F(10), fg=C["muted"], bg=bg).pack(anchor="w")
        row = tk.Frame(box, bg=bg)
        row.pack(anchor="w", pady=(4, 2))
        self.val = tk.Label(row, font=F(22, "bold"), fg=C["text"], bg=bg)
        self.val.pack(side="left")
        self.unit = tk.Label(row, font=F(10, "bold"), fg=C["muted"], bg=bg)
        self.unit.pack(side="left", anchor="s", pady=(0, 6), padx=(4, 0))
        self.note = tk.Label(box, font=F(9), fg=C["muted"], bg=bg)
        self.note.pack(anchor="w")

    def set(self, value, unit="", note="", color=None):
        self.val.config(text=value)
        self.unit.config(text=unit)
        self.note.config(text=note, fg=color or C["muted"])


class Dashboard(Page):
    def build(self):
        self.header("Energy dashboard", "When to use electricity, based on your panels and the weather")
        self.seg = Segmented(self.header_right, ["Today", "Tomorrow"],
                             command=lambda v: self.app.set_day(v.lower()))
        self.seg.pack(side="right")
        self.date_lbl = tk.Label(self.header_right, font=F(10, "bold"), fg=C["muted"], bg=C["bg"])
        self.date_lbl.pack(side="right", padx=16)

        b = self.body()
        for c in range(3):
            b.columnconfigure(c, weight=1, uniform="d")
        b.rowconfigure(2, weight=1)
        b.rowconfigure(3, weight=0)
        self.arc = SunArc(b)
        self.arc.grid(row=0, column=0, columnspan=3, sticky="ew")

        strip = Card(b, pad=20)
        strip.grid(row=1, column=0, columnspan=3, sticky="ew", pady=16)
        inn = strip.inner
        self.m = {}
        for i, (key, label) in enumerate((("gen", "Solar production"), ("use", "Home consumption"),
                                          ("bal", "Energy balance"), ("bat", "Battery at start"))):
            inn.columnconfigure(i * 2, weight=1)
            if i:
                tk.Frame(inn, bg=C["border"], width=1).grid(row=0, column=i * 2 - 1, sticky="ns", padx=18)
            self.m[key] = Metric(inn, label, gauge=(key == "bat"))
            self.m[key].grid(row=0, column=i * 2, sticky="w")

        chart_card = Card(b, fill=True, height=320)
        chart_card.grid(row=2, column=0, columnspan=2, sticky="nsew", padx=(0, 8))
        top = tk.Frame(chart_card.inner, bg=C["card"])
        top.pack(fill="x", pady=(0, 8))
        tk.Label(top, text="Solar output vs home demand", font=F(13, "bold"), fg=C["text"],
                 bg=C["card"]).pack(side="left")
        for txt, col in (("\u25a0 Best window", C["green"]), ("\u2505 Home demand", C["sky"]),
                         ("\u2501 Solar", C["sun"])):
            tk.Label(top, text=txt, font=F(9, "bold"), fg=col, bg=C["card"]).pack(side="right", padx=(12, 0))
        self.chart = EnergyChart(chart_card.inner)
        self.chart.pack(fill="both", expand=True)

        self.rec_card = Card(b, fill=True, height=320)
        self.rec_card.grid(row=2, column=2, sticky="nsew", padx=(8, 0))
        tk.Label(self.rec_card.inner, text="What to do", font=F(13, "bold"), fg=C["text"],
                 bg=C["card"]).pack(anchor="w", pady=(0, 12))
        self.rec_box = tk.Frame(self.rec_card.inner, bg=C["card"])
        self.rec_box.pack(fill="both", expand=True)

        source_card = Card(b, pad=14)
        source_card.grid(row=4, column=0, columnspan=3, sticky="ew", pady=(16, 0))
        self.source_label = tk.Label(source_card.inner, anchor="w", justify="left",
                                      font=F(9), fg=C["muted"], bg=C["card"])
        self.source_label.pack(fill="x")


    def refresh(self):
        app = self.app
        r, s = app.res[app.day], app.system
        self.seg.set(app.day.title())
        analyzed_date = datetime.date.fromisoformat(r["analyzed_date"])
        self.date_lbl.config(text=analyzed_date.strftime("%A %d %B %Y"))
        focus = app.focus_window(app.day)
        self.arc.set(res=r, day=app.day, pv=s["pv_kw"], best=focus)

        gen = r["generation"]
        self.m["gen"].set(f"{r['total_gen']:.1f}", "kWh",
                          f"Peak {max(gen):.1f} kW around {r['peak_hour']:02d}:00", C["sun"])
        self.m["use"].set(f"{r['total_demand']:.1f}", "kWh",
                          f"Includes {r['scheduled_energy']:.1f} kWh of planned appliances")
        bal = r["balance"]
        self.m["bal"].set(f"{bal:+.1f}", "kWh",
                          "Surplus: run flexible loads on sun" if bal >= 0
                          else "Deficit: battery will cover the gap",
                          C["green"] if bal >= 0 else C["red"])
        full = r["battery_full_at"]
        self.m["bat"].gauge.set(s["soc"])
        self.m["bat"].set(f"{s['battery_kwh'] * s['soc'] / 100:.1f}", "kWh",
                          f"Full by {full:02d}:00" if full else "Won't fill up today",
                          C["green"] if full else C["amber"])
        self.chart.set_data(gen, r["demand"], focus[1] if focus else None)
        info = app.runtime_info
        self.source_label.config(
            text=(f"REAL DATA  |  {info['source']}  |  {info['location']}  |  "
                  f"{info['dataset']}  |  {info['date_start']} to {info['date_end']}\n"
                  f"Forecast model: {info['model']} ({info['artifact']})  |  "
                  f"{info['features']} notebook features  |  {info['modeled_note']}")
        )

        for wdg in self.rec_box.winfo_children():
            wdg.destroy()
        msgs = ([app.warning] if app.warning else []) + r["recommendations"]
        for m in msgs[:3]:
            message_row(self.rec_box, m, wrap=250)
        if len(msgs) > 3:
            link = tk.Label(self.rec_box, text=f"See all {len(msgs)} tips in Notifications", cursor="hand2",
                            font=F(9, "bold"), fg=C["sun"], bg=C["card"])
            link.pack(anchor="w", pady=(2, 0))
            link.bind("<Button-1>", lambda e: app.show("alerts"))


class SystemPage(Page):
    def build(self):
        self.header("My solar system", "Your panels, inverter and battery. Every recommendation uses these")
        b = self.body()
        b.columnconfigure(0, weight=5, uniform="s")
        b.columnconfigure(1, weight=6, uniform="s")
        b.rowconfigure(0, weight=1)

        form = Card(b, fill=True, pad=24)
        form.grid(row=0, column=0, sticky="nsew", padx=(0, 8))
        f = form.inner
        tk.Label(f, text="System details", font=F(14, "bold"), fg=C["text"], bg=C["card"]).pack(anchor="w")
        tk.Label(f, text="Use the numbers printed on your equipment.", font=F(10),
                 fg=C["muted"], bg=C["card"]).pack(anchor="w", pady=(2, 18))
        grid = tk.Frame(f, bg=C["card"])
        grid.pack(fill="x")
        grid.columnconfigure(0, weight=1, uniform="g")
        grid.columnconfigure(1, weight=1, uniform="g")
        s = self.app.system
        self.f_pv = Field(grid, "Solar panels (total)", "kW", s["pv_kw"])
        self.f_inv = Field(grid, "Inverter rating", "kW", s["inverter_kw"])
        self.f_bat = Field(grid, "Battery capacity", "kWh", s["battery_kwh"])
        self.f_pv.grid(row=0, column=0, sticky="ew", padx=(0, 8), pady=(0, 14))
        self.f_inv.grid(row=0, column=1, sticky="ew", padx=(8, 0), pady=(0, 14))
        self.f_bat.grid(row=1, column=0, sticky="ew", padx=(0, 8), pady=(0, 14))

        socrow = tk.Frame(f, bg=C["card"])
        socrow.pack(fill="x", pady=(6, 0))
        tk.Label(socrow, text="Battery charge right now", font=F(10), fg=C["muted"],
                 bg=C["card"]).pack(side="left")
        self.soc_lbl = tk.Label(socrow, font=F(11, "bold"), fg=C["text"], bg=C["card"])
        self.soc_lbl.pack(side="right")
        self.slider = Slider(f, s["soc"], command=lambda v: self.soc_lbl.config(
            text=f"{v}%", fg=soc_color(v)))
        self.slider.pack(fill="x", pady=(4, 16))

        tk.Label(f, text="Location", font=F(10), fg=C["muted"], bg=C["card"]).pack(anchor="w", pady=(0, 8))
        self.city = ChipGroup(f, CITIES, s["city"], per_row=4)
        self.city.pack(anchor="w")

        self.insight = tk.Label(f, font=F(10), fg=C["muted"], bg=C["card"], justify="left",
                                anchor="w", wraplength=420)
        self.insight.pack(anchor="w", fill="x", pady=(12, 0))
        btns = tk.Frame(f, bg=C["card"])
        btns.pack(side="bottom", anchor="w", pady=(16, 0))
        PillButton(btns, "Save and recalculate", self.save).pack(side="left")
        PillButton(btns, "Undo changes", self.load, kind="ghost").pack(side="left", padx=10)

        flow = Card(b, fill=True, pad=24)
        flow.grid(row=0, column=1, sticky="nsew", padx=(8, 0))
        tk.Label(flow.inner, text="How energy moves through your home", font=F(14, "bold"),
                 fg=C["text"], bg=C["card"]).pack(anchor="w")
        tk.Label(flow.inner, text="Live picture of today with your current settings.",
                 font=F(10), fg=C["muted"], bg=C["card"]).pack(anchor="w", pady=(2, 0))
        self.flow = FlowDiagram(flow.inner, self.app)
        self.flow.pack(fill="both", expand=True, pady=(8, 0))
        self.load()

    def load(self):
        s = self.app.system
        self.f_pv.var.set(f"{s['pv_kw']:g}")
        self.f_inv.var.set(f"{s['inverter_kw']:g}")
        self.f_bat.var.set(f"{s['battery_kwh']:g}")
        for fld in (self.f_pv, self.f_inv, self.f_bat):
            fld.box.set_border(C["border"])
        self.slider.set(s["soc"])
        self.soc_lbl.config(text=f"{s['soc']}%", fg=soc_color(s["soc"]))
        self.city.select(s["city"], notify=False)
        self.refresh()

    def save(self):
        vals, bad = {}, []
        for key, fld, name in (("pv_kw", self.f_pv, "Solar panels"), ("inverter_kw", self.f_inv, "Inverter"),
                               ("battery_kwh", self.f_bat, "Battery")):
            try:
                vals[key] = fld.number()
            except ValueError:
                bad.append(name)
        if bad:
            self.app.toast("Check your numbers", f"{', '.join(bad)}: enter a number above zero, like 3 or 5.5.",
                           "danger")
            return
        vals["soc"], vals["city"] = self.slider.value, self.city.value
        self.app.system.update(vals)
        self.app.refresh_all()
        self.app.toast("System saved", "Recommendations now use your new settings.", "success")

    def refresh(self):
        s = self.app.system
        notes = [f"Usable energy in the battery right now: {s['battery_kwh'] * s['soc'] / 100:.1f} kWh."]
        if s["inverter_kw"] < s["pv_kw"]:
            notes.append(f"Your inverter is smaller than your panels, so output is capped at "
                         f"{s['inverter_kw']:g} kW on sunny middays.")
        self.insight.config(text="\n".join(notes))
        self.flow.draw()


class AppliancesPage(Page):
    def build(self):
        self.header("Appliances", "The devices you use and how much power each one draws on average")
        b = self.body()
        b.columnconfigure(0, weight=7, uniform="a")
        b.columnconfigure(1, weight=4, uniform="a")
        b.rowconfigure(0, weight=1)

        tcard = Card(b, fill=True, pad=22)
        tcard.grid(row=0, column=0, sticky="nsew", padx=(0, 8))
        top = tk.Frame(tcard.inner, bg=C["card"])
        top.pack(fill="x", pady=(0, 14))
        tk.Label(top, text="Your devices", font=F(14, "bold"), fg=C["text"], bg=C["card"]).pack(side="left")
        PillButton(top, "Remove", self.remove, kind="danger", height=36).pack(side="right")
        PillButton(top, "Run today on/off", self.toggle, kind="ghost", height=36).pack(side="right", padx=8)
        cols = ("name", "power", "duration", "priority", "run")
        self.tree = ttk.Treeview(tcard.inner, columns=cols, show="headings", style="SW.Treeview",
                                 selectmode="browse")
        for c, txt, wd, anc in (("name", "Appliance", 200, "w"), ("power", "Power", 90, "center"),
                                ("duration", "Runs for", 90, "center"),
                                ("priority", "Priority", 120, "center"), ("run", "Run today", 100, "center")):
            self.tree.heading(c, text=txt, anchor=anc)
            self.tree.column(c, width=wd, anchor=anc, stretch=(c == "name"))
        self.tree.tag_configure("odd", background=C["card"])
        self.tree.tag_configure("even", background="#142040")
        self.tree.pack(fill="both", expand=True)
        self.tree.bind("<Double-1>", lambda e: self.toggle())
        tk.Label(tcard.inner, text="Double-click a row to switch 'Run today' on or off.",
                 font=F(9), fg=C["dim"], bg=C["card"]).pack(anchor="w", pady=(10, 0))

        fcard = Card(b, fill=True, pad=22)
        fcard.grid(row=0, column=1, sticky="nsew", padx=(8, 0))
        f = fcard.inner
        tk.Label(f, text="Add a device", font=F(14, "bold"), fg=C["text"], bg=C["card"]).pack(anchor="w", pady=(0, 14))
        self.f_name = Field(f, "Name", "", "")
        self.f_name.pack(fill="x", pady=(0, 12))
        row = tk.Frame(f, bg=C["card"])
        row.pack(fill="x", pady=(0, 12))
        row.columnconfigure(0, weight=1, uniform="r")
        row.columnconfigure(1, weight=1, uniform="r")
        self.f_power = Field(row, "Average power", "kW", "1.0")
        self.f_dur = Field(row, "Runs for", "h", "1.0")
        self.f_power.grid(row=0, column=0, sticky="ew", padx=(0, 6))
        self.f_dur.grid(row=0, column=1, sticky="ew", padx=(6, 0))
        tk.Label(f, text="Priority", font=F(10), fg=C["muted"], bg=C["card"]).pack(anchor="w", pady=(0, 8))
        self.prio = ChipGroup(f, PRIORITIES, "Flexible", per_row=3, colors=PRIORITY_COLORS)
        self.prio.pack(anchor="w")
        self.run_chip = Chip(f, "\u2713 Run today", selected=True, color=C["green"])
        self.run_chip.command = lambda: self.run_chip.set_selected(not self.run_chip.selected)
        self.run_chip.pack(anchor="w", pady=(4, 14))
        PillButton(f, "Add device", self.add).pack(anchor="w")

        legend = tk.Frame(f, bg=C["card"])
        legend.pack(side="bottom", fill="x")
        for p, txt in (("Essential", "Runs no matter what, like the fridge"),
                       ("Important", "Can wait a few hours"),
                       ("Flexible", "SolarWise moves it to the sunniest time")):
            r = tk.Frame(legend, bg=C["card"])
            r.pack(fill="x", pady=3)
            tk.Label(r, text="\u25cf", fg=PRIORITY_COLORS[p], bg=C["card"], font=F(10)).pack(side="left")
            tk.Label(r, text=f"{p}: {txt}", fg=C["muted"], bg=C["card"], font=F(9)).pack(side="left", padx=6)

    def refresh(self):
        sel = self.tree.selection()
        self.tree.delete(*self.tree.get_children())
        for i, a in enumerate(self.app.appliances):
            self.tree.insert("", "end", iid=str(i), tags=("odd" if i % 2 else "even",), values=(
                a["name"], f"{a['power']:g} kW", f"{a['duration']:g} h", a["priority"],
                "\u25cf  Yes" if a.get("run") else "\u25cb  No"))
        if sel and self.tree.exists(sel[0]):
            self.tree.selection_set(sel[0])

    def _selected(self):
        sel = self.tree.selection()
        if not sel:
            self.app.toast("Pick a device first", "Click a row in the table, then try again.", "warn")
            return None
        return int(sel[0])

    def toggle(self):
        i = self._selected()
        if i is not None:
            a = self.app.appliances[i]
            a["run"] = not a.get("run")
            self.app.refresh_all()

    def remove(self):
        i = self._selected()
        if i is not None:
            name = self.app.appliances.pop(i)["name"]
            self.app.refresh_all()
            self.app.toast("Device removed", f"{name} is no longer in your list.", "info")

    def add(self):
        name = self.f_name.text()
        if not name:
            self.f_name.box.set_border(C["red"])
            self.app.toast("Name the device", "Type a name like 'Oven' or 'Electric kettle'.", "danger")
            return
        try:
            power, dur = self.f_power.number(), self.f_dur.number()
        except ValueError:
            self.app.toast("Check your numbers", "Power and time must be numbers above zero.", "danger")
            return
        self.app.appliances.append({"name": name, "power": power, "duration": dur,
                                    "priority": self.prio.value, "run": self.run_chip.selected})
        self.f_name.var.set("")
        self.app.refresh_all()
        self.app.toast("Device added", f"{name} ({power:g} kW) is in your list.", "success")


class BestTimePage(Page):
    def build(self):
        self.header("Best time to run", "Pick a device and SolarWise finds the sunniest slot for it")
        self.seg = Segmented(self.header_right, ["Today", "Tomorrow"],
                             command=lambda v: self.app.set_day(v.lower()))
        self.seg.pack(side="right")
        b = self.body()
        self.chips = ChipGroup(b, [], command=lambda v: self.refresh(), per_row=7)
        self.chips.pack(anchor="w", pady=(0, 10))

        hero = self.hero = Card(b, pad=28, radius=22, border="#2B6A5C")
        hero.pack(fill="x")
        h = hero.inner
        left = tk.Frame(h, bg=C["card"])
        left.pack(side="left", fill="x", expand=True)
        self.h_label = tk.Label(left, font=F(11), fg=C["muted"], bg=C["card"])
        self.h_label.pack(anchor="w")
        self.h_time = tk.Label(left, font=F(40, "bold"), fg=C["green"], bg=C["card"])
        self.h_time.pack(anchor="w")
        self.h_sub = tk.Label(left, font=F(11), fg=C["text"], bg=C["card"])
        self.h_sub.pack(anchor="w")
        PillButton(h, "\u23f0  Remind me", self.notify, width=160, height=46).pack(side="right", anchor="n")

        stats = Card(b, pad=20)
        stats.pack(fill="x", pady=16)
        self.m = {}
        for i, (k, lab) in enumerate((("solar", "Expected sun power"), ("need", "Device needs"),
                                      ("surplus", "Left over"), ("cover", "Covered by solar"))):
            stats.inner.columnconfigure(i * 2, weight=1)
            if i:
                tk.Frame(stats.inner, bg=C["border"], width=1).grid(row=0, column=i * 2 - 1, sticky="ns", padx=18)
            self.m[k] = Metric(stats.inner, lab)
            self.m[k].grid(row=0, column=i * 2, sticky="w")

        tl = Card(b, pad=22)
        tl.pack(fill="x")
        top = tk.Frame(tl.inner, bg=C["card"])
        top.pack(fill="x")
        tk.Label(top, text="Sun through the day", font=F(13, "bold"), fg=C["text"], bg=C["card"]).pack(side="left")
        tk.Label(top, text="Brighter blocks mean more solar power", font=F(9), fg=C["dim"],
                 bg=C["card"]).pack(side="right")
        self.timeline = Timeline(tl.inner)
        self.timeline.pack(fill="x", pady=(10, 0))
        self.alt_lbl = tk.Label(tl.inner, font=F(10), fg=C["sky"], bg=C["card"])
        self.alt_lbl.pack(anchor="w", pady=(6, 0))

    def current(self):
        r = self.app.res[self.app.day]
        name = self.chips.value
        a = next((x for x in self.app.appliances if x["name"] == name), None)
        return r, a, r["windows"].get(name, (None, None))

    def refresh(self):
        self.seg.set(self.app.day.title())
        names = [a["name"] for a in self.app.appliances if a["name"] in self.app.res[self.app.day]["windows"]]
        self.chips.set_options(names, self.chips.value)
        r, a, (best, alt) = self.current()
        if not a or not best:
            self.h_label.config(text="Nothing to schedule yet")
            self.h_time.config(text="--:--", fg=C["dim"])
            self.h_sub.config(text="Add a Flexible or Important device on the Appliances page.")
            return
        ok = best["surplus"] >= 0
        self.hero.set_border("#2B6A5C" if ok else "#6A4A22")
        self.h_label.config(text=f"Best time {self.app.day} for your {a['name'].lower()}")
        self.h_time.config(text=f"{fmt_time(best['start'])} \u2013 {fmt_time(best['end'])}",
                           fg=C["green"] if ok else C["amber"])
        self.h_sub.config(text=(f"Uses {a['power']:g} kW for {a['duration']:g} h, fully on sunshine."
                                if ok else f"Uses {a['power']:g} kW for {a['duration']:g} h. Part of it "
                                           f"will come from the battery."))
        cover = max(0.0, min(1.0, (best["solar"] - best["demand"]) / a["power"]))
        self.m["solar"].set(f"{best['solar']:.1f}", "kW", "average over the slot", C["sun"])
        self.m["need"].set(f"{a['power']:.1f}", "kW", "plus the rest of the house")
        self.m["surplus"].set(f"{best['surplus']:+.1f}", "kW", "extra solar" if ok else "taken from battery",
                              C["green"] if ok else C["red"])
        self.m["cover"].set(f"{cover:.0%}", "", "of this device's energy", C["green"] if cover >= 1 else C["amber"])
        self.timeline.set(r["generation"], best, alt, self.app.day == "today")
        self.alt_lbl.config(text=(f"Alternative: {fmt_time(alt['start'])} \u2013 {fmt_time(alt['end'])}, "
                                  f"{alt['surplus']:+.1f} kW left over") if alt else "")

    def notify(self):
        r, a, (best, _) = self.current()
        if not a or not best:
            return
        span = f"{fmt_time(best['start'])} \u2013 {fmt_time(best['end'])}"
        self.app.add_reminder(a["name"], best, self.app.day)
        self.app.toast("Reminder set", f"We'll notify you at {fmt_time(best['start'])} to run the "
                                       f"{a['name'].lower()}.", "success")
        self.app.after(3500, lambda: self.app.toast(
            f"Time to run the {a['name'].lower()}",
            f"Sun is strong now ({best['solar']:.1f} kW). Best until {fmt_time(best['end'])}. "
            f"(Preview of the real reminder)", "info"))


class AlertsPage(Page):
    def build(self):
        self.header("Notifications", "Weather warnings, reminders you set and battery tips")
        PillButton(self.header_right, "Clear my reminders", self.clear, kind="ghost").pack(side="right")
        self.box = self.body()

    def refresh(self):
        for wdg in self.box.winfo_children():
            wdg.destroy()
        items = self.app.all_alerts()
        if not items:
            tk.Label(self.box, text="No notifications. SolarWise will warn you here before a cloudy day.",
                     font=F(11), fg=C["muted"], bg=C["bg"]).pack(anchor="w", pady=20)
            return
        for it in items[:7]:
            col, sym = KIND[it["kind"]]
            card = Card(self.box, pad=16, border=lerp(col, C["card"], .7) if it["kind"] == "danger" else None)
            card.pack(fill="x", pady=(0, 10))
            inn = card.inner
            Badge(inn, sym, col, size=42).pack(side="left", anchor="n")
            tx = tk.Frame(inn, bg=C["card"])
            tx.pack(side="left", fill="x", expand=True, padx=14)
            tk.Label(tx, text=it["title"], font=F(12, "bold"), fg=C["text"], bg=C["card"]).pack(anchor="w")
            tk.Label(tx, text=it["text"], font=F(10), fg=C["muted"], bg=C["card"], justify="left",
                     wraplength=720).pack(anchor="w", pady=(2, 0))
            tk.Label(inn, text=it["when"], font=F(9), fg=C["dim"], bg=C["card"]).pack(side="right", anchor="n")

    def clear(self):
        self.app.reminders.clear()
        self.app.refresh_all()


# ------------------------------------------------------------------- app --
class SolarWiseApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("SolarWise  |  Smart Solar Energy Advisor")
        self.geometry("1380x900")
        self.minsize(1240, 840)
        self.configure(bg=C["bg"])
        self.system = {"pv_kw": 3.0, "inverter_kw": 3.0, "battery_kwh": 5.0, "soc": 70, "city": "Damascus"}
        self.appliances = [dict(a) for a in DEFAULT_APPLIANCES]
        self.runtime_info = runtime_info()
        self.day = "tomorrow"
        self.reminders, self.toasts, self.fired = [], [], set()
        self._style()
        self.recompute()
        self._build()
        self.show("dashboard")
        self.after(900, self._startup_alert)
        self.after(20000, self._tick)

    # -- data
    def recompute(self):
        self.res = {d: get_results(self.system, self.appliances, d) for d in ("today", "tomorrow")}
        self.warning = get_warning(self.res["today"], self.res["tomorrow"])

    def focus_window(self, day):
        """(name, window) of the most important device the user plans to run."""
        w = self.res[day]["windows"]
        runs = [a for a in self.appliances if a.get("run") and a["name"] in w and w[a["name"]][0]]
        runs.sort(key=lambda a: (a["priority"] != "Flexible", -a["power"]))
        return (runs[0]["name"], w[runs[0]["name"]][0]) if runs else None

    def all_alerts(self):
        items = [dict(r, when="Set by you") for r in reversed(self.reminders)]
        if self.warning:
            items.append(dict(self.warning, when="Tomorrow"))
        for rec in self.res["tomorrow"]["recommendations"]:
            if rec["kind"] in ("success", "warn") and ":" in rec["title"]:
                items.append(dict(kind=rec["kind"], title=f"Tomorrow, {rec['title']}", text=rec["text"],
                                  when="Tomorrow"))
        full = self.res["today"]["battery_full_at"]
        if full:
            items.append(dict(kind="info", title=f"Battery should be full by {full:02d}:00 today",
                              text="Use heavy appliances after that so no sunshine goes to waste.", when="Today"))
        return items

    def add_reminder(self, name, win, day):
        date = datetime.date.today() + datetime.timedelta(days=1 if day == "tomorrow" else 0)
        at = datetime.datetime.combine(date, datetime.time()) + datetime.timedelta(hours=win["start"])
        self.reminders.append({"kind": "success", "at": at, "name": name,
                               "title": f"Reminder: {name} at {fmt_time(win['start'])} {day}",
                               "text": f"Best slot {fmt_time(win['start'])} \u2013 {fmt_time(win['end'])} "
                                       f"with about {win['solar']:.1f} kW of sun."})
        self.update_sidebar()

    # -- ui
    def _style(self):
        st = ttk.Style(self)
        st.theme_use("clam")
        st.configure("SW.Treeview", background=C["card"], fieldbackground=C["card"], foreground=C["text"],
                     rowheight=40, borderwidth=0, font=F(11))
        st.configure("SW.Treeview.Heading", background=C["card2"], foreground=C["muted"], relief="flat",
                     font=F(10, "bold"), padding=(10, 9), borderwidth=0)
        st.map("SW.Treeview", background=[("selected", "#3A2F1C")], foreground=[("selected", C["sun"])])
        st.map("SW.Treeview.Heading", background=[("active", C["border"])])
        st.layout("SW.Treeview", [("SW.Treeview.treearea", {"sticky": "nswe"})])

    def _build(self):
        side = tk.Frame(self, bg=C["side"], width=248)
        side.pack(side="left", fill="y")
        side.pack_propagate(False)
        tk.Frame(self, bg=C["border"], width=1).pack(side="left", fill="y")

        logo = tk.Canvas(side, height=96, bg=C["side"], highlightthickness=0)
        logo.pack(fill="x")
        cx, cy = 42, 56
        logo.create_arc(cx - 22, cy - 22, cx + 22, cy + 22, start=0, extent=180, style="arc",
                        outline=C["dim"], dash=(2, 3))
        logo.create_line(cx - 28, cy, cx + 28, cy, fill=C["sun"], width=2)
        logo.create_oval(cx + 2, cy - 26, cx + 16, cy - 12, fill=C["sun"], outline="")
        logo.create_text(80, 42, text="SolarWise", anchor="w", fill=C["text"], font=F(17, "bold"))
        logo.create_text(81, 64, text="Solar first, battery last", anchor="w", fill=C["muted"], font=F(9))

        self.nav = {}
        for key, icon, text in (("dashboard", "\u25d0", "Dashboard"), ("system", "\u2699", "My system"),
                                ("appliances", "\u26a1", "Appliances"), ("besttime", "\u25f7", "Best time"),
                                ("alerts", "\u2691", "Notifications")):
            item = NavItem(side, icon, text, lambda k=key: self.show(k))
            item.pack(fill="x", padx=12, pady=2)
            self.nav[key] = item

        foot = tk.Frame(side, bg=C["side"])
        foot.pack(side="bottom", fill="x", padx=16, pady=18)
        bcard = Card(foot, pad=14, color=C["card"])
        bcard.pack(fill="x")
        tk.Label(bcard.inner, text="Battery now", font=F(9), fg=C["muted"], bg=C["card"]).pack(anchor="w")
        self.side_bat = tk.Canvas(bcard.inner, height=30, bg=C["card"], highlightthickness=0)
        self.side_bat.pack(fill="x", pady=(6, 0))
        self.side_bat.bind("<Configure>", lambda e: self.update_sidebar())
        self.side_loc = tk.Label(foot, font=F(9), fg=C["muted"], bg=C["side"])
        self.side_loc.pack(anchor="w", pady=(12, 0))
        tk.Label(foot, text="AI4Climate hackathon, Team 7", font=F(8), fg=C["dim"],
                 bg=C["side"]).pack(anchor="w", pady=(2, 0))

        content = tk.Frame(self, bg=C["bg"])
        content.pack(side="left", fill="both", expand=True, padx=28, pady=22)
        content.rowconfigure(0, weight=1)
        content.columnconfigure(0, weight=1)
        self.pages = {}
        for key, cls in (("dashboard", Dashboard), ("system", SystemPage), ("appliances", AppliancesPage),
                         ("besttime", BestTimePage), ("alerts", AlertsPage)):
            p = cls(content, self)
            p.grid(row=0, column=0, sticky="nsew")
            self.pages[key] = p
        for p in self.pages.values():
            p.refresh()
        self.update_sidebar()

    def update_sidebar(self):
        s = self.system
        cv = self.side_bat
        cv.delete("all")
        w = cv.winfo_width()
        if w > 40:
            col = soc_color(s["soc"])
            round_rect(cv, 1, 4, w - 60, 26, 7, fill=C["card2"], outline=C["border"])
            cv.create_rectangle(w - 60, 11, w - 56, 19, fill=C["border"], outline="")
            fill_w = (w - 66) * s["soc"] / 100
            if fill_w > 6:
                round_rect(cv, 4, 7, 4 + fill_w, 23, 5, fill=col, outline="")
            cv.create_text(w - 2, 15, text=f"{s['soc']}%", anchor="e", fill=C["text"], font=F(11, "bold"))
        self.side_loc.config(text=f"\u2316  {s['city']}, Syria")
        self.nav["alerts"].set_badge(len(self.all_alerts()))

    def show(self, key):
        for k, item in self.nav.items():
            item.set_active(k == key)
        self.pages[key].tkraise()
        self.pages[key].refresh()

    def set_day(self, day):
        self.day = day
        self.pages["dashboard"].refresh()
        self.pages["besttime"].refresh()

    def refresh_all(self):
        self.recompute()
        for p in self.pages.values():
            p.refresh()
        self.update_sidebar()

    def toast(self, title, text, kind="info"):
        t = Toast(self, title, text, kind)
        self.toasts.append(t)
        t.place_me()

    def _startup_alert(self):
        if self.warning:
            self.toast(self.warning["title"], self.warning["text"], "danger")

    def _tick(self):
        """Every 20 s: fire reminders whose time has come, and today's best-slot alerts."""
        now = datetime.datetime.now()
        for r in self.reminders:
            if not r.get("fired") and now >= r["at"]:
                r["fired"] = True
                self.toast(f"Time to run the {r['name'].lower()}", r["text"], "success")
        h = now.hour + now.minute / 60
        for a in self.appliances:
            best = self.res["today"]["windows"].get(a["name"], (None, None))[0]
            key = (now.date(), a["name"])
            if a.get("run") and best and key not in self.fired and 0 <= h - best["start"] < .1:
                self.fired.add(key)
                self.toast(f"Good time for the {a['name'].lower()}",
                           f"About {best['solar']:.1f} kW of sun until {fmt_time(best['end'])}.", "success")
        self.after(20000, self._tick)


if __name__ == "__main__":
    SolarWiseApp().mainloop()
