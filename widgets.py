"""Piezas visuales con estilo oscuro «gamer»: tarjetas redondeadas, botones con brillo,
insignias, medidores circulares, degradados."""
import sys
import tkinter as tk
import tkinter.font as tkfont
from tkinter import ttk

# ---------------------------------------------------------------- paleta
BG = "#0a0607"
SIDE = "#0f0809"
PANEL = "#170f10"
PANEL2 = "#231518"
BORDER = "#3d2125"
FG = "#fff0e8"
MUTED = "#b4948a"
CYAN = "#ff5a2e"
PINK = "#ffb02e"
GREEN = "#39ff88"
YELLOW = "#ffd23f"
RED = "#ff3b3b"
VIOLET = "#e0245e"

FONT = "Segoe UI"
MONO = "Consolas"
GRADIENT = (CYAN, VIOLET, PINK)


def F(size=10, bold=False):
    return (FONT, size, "bold" if bold else "normal")


# ---------------------------------------------------------------- utilidades de color
def _rgb(h):
    h = h.lstrip("#")
    return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)


def mix(c1, c2, t):
    a, b = _rgb(c1), _rgb(c2)
    return "#%02x%02x%02x" % tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))


def gradient_color(stops, t):
    t = max(0.0, min(1.0, t))
    seg = t * (len(stops) - 1)
    i = min(int(seg), len(stops) - 2)
    return mix(stops[i], stops[i + 1], seg - i)


def _bg_of(widget):
    try:
        return widget.cget("bg")
    except tk.TclError:
        return BG


def round_rect(cv, x1, y1, x2, y2, r, **kw):
    r = max(1, min(r, (x2 - x1) / 2, (y2 - y1) / 2))
    pts = [x1 + r, y1, x2 - r, y1, x2, y1, x2, y1 + r, x2, y2 - r, x2, y2, x2 - r, y2,
           x1 + r, y2, x1, y2, x1, y2 - r, x1, y1 + r, x1, y1]
    return cv.create_polygon(pts, smooth=True, **kw)


# ---------------------------------------------------------------- estilos ttk
def setup_styles(root):
    s = ttk.Style(root)
    try:
        s.theme_use("clam")
    except tk.TclError:
        pass
    for name, col in (("Neon", CYAN), ("Green", GREEN), ("Pink", PINK)):
        s.configure(f"{name}.Horizontal.TProgressbar", troughcolor=PANEL2, background=col,
                    bordercolor=BG, lightcolor=col, darkcolor=col, thickness=10)
    s.configure("Vertical.TScrollbar", troughcolor=BG, background=PANEL2, bordercolor=BG,
                arrowcolor=MUTED, lightcolor=PANEL2, darkcolor=PANEL2, gripcount=0, width=10)
    s.map("Vertical.TScrollbar", background=[("active", BORDER)])


# ---------------------------------------------------------------- botón
class NeonButton(tk.Canvas):
    """Botón redondeado con borde de color y brillo al pasar el ratón."""

    def __init__(self, parent, text, command=None, color=CYAN, filled=False, font=None, padx=18, pady=8):
        self.color, self.filled, self.command, self.enabled = color, filled, command, True
        self._text, self._font = text, tkfont.Font(font=font or F(10, True))
        self._padx, self._pady, self._hover = padx, pady, False
        super().__init__(parent, bg=_bg_of(parent), highlightthickness=0, bd=0, cursor="hand2")
        self._resize()
        self.bind("<Enter>", lambda e: self._set_hover(True))
        self.bind("<Leave>", lambda e: self._set_hover(False))
        self.bind("<ButtonRelease-1>", self._click)

    def _resize(self):
        w = self._font.measure(self._text) + self._padx * 2 + 4
        h = self._font.metrics("linespace") + self._pady * 2 + 4
        self.configure(width=w, height=h)
        self._draw()

    def _draw(self):
        self.delete("all")
        w, h = int(self["width"]), int(self["height"])
        c, bg = self.color, _bg_of(self.master)
        if not self.enabled:
            round_rect(self, 2, 2, w - 2, h - 2, 12, fill=PANEL2, outline=BORDER)
            fg = MUTED
        elif self.filled:
            if self._hover:
                round_rect(self, 0, 0, w, h, 14, fill=mix(c, bg, 0.65), outline="")
            round_rect(self, 2, 2, w - 2, h - 2, 12, fill=mix(c, "#ffffff", 0.35) if self._hover else c, outline="")
            fg = BG
        else:
            if self._hover:
                round_rect(self, 0, 0, w, h, 14, fill=mix(c, bg, 0.8), outline="")
            round_rect(self, 2, 2, w - 2, h - 2, 12, fill=mix(c, PANEL2, 0.78) if self._hover else PANEL2,
                       outline=c, width=1)
            fg = FG if self._hover else c
        self.create_text(w / 2, h / 2, text=self._text, fill=fg, font=self._font)
        self.configure(cursor="hand2" if self.enabled else "arrow")

    def _set_hover(self, flag):
        self._hover = flag
        self._draw()

    def _click(self, e):
        if self.enabled and self.command and 0 <= e.x <= int(self["width"]) and 0 <= e.y <= int(self["height"]):
            self.command()

    def set_enabled(self, flag):
        self.enabled = flag
        self._draw()

    def set_text(self, text):
        self._text = text
        self._resize()

    def set_color(self, color):
        self.color = color
        self._draw()


# ---------------------------------------------------------------- insignia
def badge(parent, text, color, bg=None):
    font = tkfont.Font(font=F(8, True))
    w = font.measure(text) + 18
    h = font.metrics("linespace") + 8
    cv = tk.Canvas(parent, width=w, height=h, bg=bg or _bg_of(parent), highlightthickness=0, bd=0)
    round_rect(cv, 0, 0, w, h, h // 2, fill=mix(color, PANEL, 0.82), outline=color)
    cv.create_text(w / 2, h / 2, text=text, fill=color, font=font)
    return cv


# ---------------------------------------------------------------- etiquetas
class WrapLabel(tk.Label):
    """Etiqueta que ajusta el texto al ancho disponible."""

    def __init__(self, parent, text="", fg=FG, bg=PANEL, font=None, **kw):
        super().__init__(parent, text=text, fg=fg, bg=bg, font=font or F(10), anchor="w",
                         justify="left", wraplength=300, **kw)
        self.bind("<Configure>", lambda e: self.config(wraplength=max(80, e.width - 2)))


# ---------------------------------------------------------------- tarjeta redondeada
class Card(tk.Canvas):
    """Tarjeta con esquinas redondeadas, borde sutil y marca de color a la izquierda.
    El contenido va en `.body`."""

    def __init__(self, parent, accent=CYAN, title=None, pad=14, radius=14):
        super().__init__(parent, bg=_bg_of(parent), highlightthickness=0, bd=0, height=40)
        self.accent, self.pad, self.radius = accent, pad, radius
        self._inset = pad + 8
        self.body = tk.Frame(self, bg=PANEL)
        self._win = self.create_window(self._inset, pad, window=self.body, anchor="nw")
        if title:
            tk.Label(self.body, text=title, font=F(11, True), fg=accent, bg=PANEL).pack(anchor="w", pady=(0, 8))
        self.bind("<Configure>", self._redraw)
        self.body.bind("<Configure>", self._fit)

    def _fit(self, e=None):
        want = self.body.winfo_reqheight() + 2 * self.pad
        if want != int(float(self["height"])):
            self.configure(height=want)

    def _redraw(self, e):
        w, h = e.width, e.height
        self.itemconfigure(self._win, width=max(20, w - self._inset - self.pad))
        self.delete("bg")
        round_rect(self, 1, 1, w - 1, h - 1, self.radius, fill=PANEL, outline=BORDER, tags="bg")
        r = self.radius
        self.create_line(7, r, 7, h - r, fill=self.accent, width=3, capstyle="round", tags="bg")
        self.tag_lower("bg")


# ---------------------------------------------------------------- medidor circular
class Gauge(tk.Canvas):
    """Medidor circular animado (0-100 %)."""

    def __init__(self, parent, label, size=150, color=CYAN):
        super().__init__(parent, width=size, height=size + 22, bg=_bg_of(parent), highlightthickness=0, bd=0)
        self.size, self.label, self.color = size, label, color
        self.value, self._shown = 0.0, 0.0
        self._draw(0)

    def set(self, value):
        self.value = max(0.0, min(100.0, float(value)))
        self._animate()

    def _animate(self):
        diff = self.value - self._shown
        if abs(diff) < 0.6:
            self._shown = self.value
            self._draw(self._shown)
            return
        self._shown += diff * 0.25
        self._draw(self._shown)
        self.after(25, self._animate)

    def _color(self, v):
        return GREEN if v < 60 else YELLOW if v < 85 else RED

    def _draw(self, v):
        self.delete("all")
        s, pad = self.size, 14
        box = (pad, pad, s - pad, s - pad)
        self.create_arc(*box, start=225, extent=-270, style="arc", outline=PANEL2, width=12)
        if v > 0.5:
            col = self._color(v)
            self.create_arc(*box, start=225, extent=-270 * v / 100, style="arc", outline=col, width=12)
        self.create_text(s / 2, s / 2 - 4, text=f"{v:.0f}%", fill=FG, font=F(int(s / 6), True))
        self.create_text(s / 2, s / 2 + s / 6, text="en uso", fill=MUTED, font=F(8))
        self.create_text(s / 2, s + 8, text=self.label, fill=self.color, font=F(10, True))


class MiniBar(tk.Canvas):
    """Barra fina redondeada con etiqueta (para el menú lateral)."""

    def __init__(self, parent, label, color=CYAN, width=190):
        super().__init__(parent, width=width, height=34, bg=_bg_of(parent), highlightthickness=0, bd=0)
        self.label, self.color, self.w = label, color, width
        self.set(0)

    def set(self, v):
        v = max(0.0, min(100.0, float(v)))
        self.delete("all")
        self.create_text(0, 7, text=self.label, anchor="w", fill=MUTED, font=F(8, True))
        self.create_text(self.w, 7, text=f"{v:.0f}%", anchor="e", fill=FG, font=F(8, True))
        round_rect(self, 0, 18, self.w, 26, 4, fill=PANEL2, outline="")
        if v > 1:
            col = GREEN if v < 60 else YELLOW if v < 85 else RED
            round_rect(self, 0, 18, max(8, self.w * v / 100), 26, 4, fill=col, outline="")


# ---------------------------------------------------------------- degradado y títulos
class GradientBar(tk.Canvas):
    def __init__(self, parent, height=3, stops=GRADIENT, width=None):
        super().__init__(parent, height=height, bg=_bg_of(parent), highlightthickness=0, bd=0,
                         **({"width": width} if width else {}))
        self.stops = stops
        self.bind("<Configure>", self._draw)

    def _draw(self, e):
        self.delete("all")
        w = max(2, e.width)
        step = 4
        for x in range(0, w, step):
            self.create_rectangle(x, 0, x + step, e.height, fill=gradient_color(self.stops, x / w), outline="")


def page_title(parent, title, subtitle=None, accent=CYAN):
    f = tk.Frame(parent, bg=BG)
    row = tk.Frame(f, bg=BG)
    row.pack(anchor="w")
    tk.Frame(row, bg=accent, width=5, height=30).pack(side="left", padx=(0, 12))
    tk.Label(row, text=title, font=F(24, True), fg=FG, bg=BG).pack(side="left")
    if subtitle:
        tk.Label(f, text=subtitle, font=F(10), fg=MUTED, bg=BG, anchor="w", justify="left").pack(anchor="w", pady=(4, 0))
    GradientBar(f, height=2, width=120).pack(anchor="w", pady=(10, 0))
    return f


# ---------------------------------------------------------------- tablas de datos
def kv_rows(parent, rows, key_width=18):
    """Filas «etiqueta: valor» en dos columnas dentro de `parent`."""
    f = tk.Frame(parent, bg=PANEL)
    f.pack(fill="x")
    f.columnconfigure(1, weight=1)
    for i, (k, v) in enumerate(rows):
        tk.Label(f, text=k, fg=MUTED, bg=PANEL, font=F(9), anchor="nw", justify="left",
                 wraplength=key_width * 8).grid(row=i, column=0, sticky="nw", padx=(0, 14), pady=3)
        WrapLabel(f, text=str(v), font=F(10)).grid(row=i, column=1, sticky="ew", pady=3)
    return f


# ---------------------------------------------------------------- scroll
class ScrollFrame(tk.Frame):
    def __init__(self, parent, bg=BG):
        super().__init__(parent, bg=bg)
        self.canvas = tk.Canvas(self, bg=bg, highlightthickness=0, bd=0)
        self.vsb = ttk.Scrollbar(self, orient="vertical", command=self.canvas.yview)
        self.inner = tk.Frame(self.canvas, bg=bg)
        self._win = self.canvas.create_window((0, 0), window=self.inner, anchor="nw")
        self.inner.bind("<Configure>", lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all")))
        self.canvas.bind("<Configure>", lambda e: self.canvas.itemconfigure(self._win, width=e.width))
        self.canvas.configure(yscrollcommand=self.vsb.set)
        self.canvas.pack(side="left", fill="both", expand=True)
        self.vsb.pack(side="right", fill="y")

    def clear(self):
        for w in self.inner.winfo_children():
            w.destroy()
        self.canvas.yview_moveto(0)


def install_mousewheel(root):
    """Rueda del ratón: desplaza el ScrollFrame que haya bajo el puntero."""
    def target(e):
        try:
            w = root.winfo_containing(e.x_root, e.y_root)
        except (KeyError, tk.TclError):
            return None
        while w is not None:
            if isinstance(w, ScrollFrame):
                return w
            w = w.master
        return None

    def on_wheel(e):
        sf = target(e)
        if sf:
            step = -e.delta if sys.platform == "darwin" else -int(e.delta / 120)
            sf.canvas.yview_scroll(step or (-1 if e.delta > 0 else 1), "units")

    def on_linux(e, d):
        sf = target(e)
        if sf:
            sf.canvas.yview_scroll(d, "units")

    root.bind_all("<MouseWheel>", on_wheel)
    root.bind_all("<Button-4>", lambda e: on_linux(e, -1))
    root.bind_all("<Button-5>", lambda e: on_linux(e, 1))


# ---------------------------------------------------------------- casilla
class CheckBox(tk.Frame):
    """Casilla neón dibujada a mano (no depende de símbolos de la tipografía)."""

    def __init__(self, parent, text, var, bg=PANEL, fg=FG, font=None):
        super().__init__(parent, bg=bg)
        self.var, self._fg, self._bg, self._disabled = var, fg, bg, False
        self.box = tk.Canvas(self, width=20, height=20, bg=bg, highlightthickness=0, bd=0, cursor="hand2")
        self.box.pack(side="left", anchor="n", padx=(0, 8), pady=1)
        self.lbl = tk.Label(self, text=text, bg=bg, fg=fg, font=font or F(10), anchor="w", justify="left",
                            cursor="hand2", bd=0, highlightthickness=0)
        if text:
            self.lbl.pack(side="left", fill="x", expand=True)
            self.lbl.bind("<Configure>", lambda e: self.lbl.config(wraplength=max(80, e.width - 2)))
        for w in (self.box, self.lbl):
            w.bind("<Button-1>", self._toggle)
        var.trace_add("write", lambda *a: self._draw())
        self._draw()

    def _toggle(self, _e=None):
        if not self._disabled:
            self.var.set(not self.var.get())

    def _draw(self):
        c, on = self.box, bool(self.var.get())
        c.delete("all")
        col = MUTED if self._disabled else CYAN
        if on:
            round_rect(c, 1, 1, 19, 19, 5, fill=col if not self._disabled else PANEL2, outline=col)
            c.create_line(5, 10, 9, 14, 15, 6, fill=BG, width=2.5, capstyle="round", joinstyle="round")
        else:
            round_rect(c, 1, 1, 19, 19, 5, fill=PANEL2, outline=BORDER if self._disabled else MUTED)

    def config(self, **kw):
        if "state" in kw:
            self._disabled = kw.pop("state") == "disabled"
            self.lbl.config(fg=MUTED if self._disabled else self._fg)
            self.box.config(cursor="arrow" if self._disabled else "hand2")
            self._draw()
        if kw:
            super().config(**kw)

    configure = config


def checkbox(parent, text, var, bg=PANEL, fg=FG, font=None):
    return CheckBox(parent, text, var, bg=bg, fg=fg, font=font)
