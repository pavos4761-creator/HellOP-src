"""Piezas visuales con estilo oscuro «gamer»: tarjetas redondeadas, botones con brillo,
insignias, medidores circulares, degradados."""
import os
import sys
import tkinter as tk
import tkinter.font as tkfont
from tkinter import ttk

# ---------------------------------------------------------------- paleta
def _es_pro():
    """¿Con clave PRO (o creador)? Entonces la app se ve en morado. HELLOP_THEME=pro|green fuerza uno (pruebas)."""
    forzado = os.environ.get("HELLOP_THEME", "").strip().lower()
    if forzado in ("pro", "green"):
        return forzado == "pro"
    try:
        import licencia
        return licencia.status()["level"] in ("owner", "pro")
    except Exception:  # noqa: BLE001
        return False


PRO_THEME = _es_pro()

# colores del tema PRO que se pueden elegir: (BG, SIDE, PANEL, PANEL2, BORDER, FG, MUTED, principal, secundario, terciario)
ACENTOS = {
    "morado": ("#08040f", "#0e0818", "#150d24", "#1f1336", "#43296f", "#f3eaff", "#a894c8", "#a855f7", "#e879f9", "#7c5cff"),
    "azul":   ("#040a14", "#07101e", "#0c1830", "#132446", "#254a80", "#eaf3ff", "#8fa8c8", "#3b9eff", "#38e1ff", "#6c7bff"),
    "rojo":   ("#0f0405", "#190709", "#240c0f", "#361318", "#6f2a30", "#ffecee", "#c89499", "#ff3b5c", "#ff8a3d", "#ff6b9a"),
    "dorado": ("#0d0902", "#171004", "#211707", "#33240b", "#6e5320", "#fff6e0", "#c8b48a", "#ffc233", "#ffe08a", "#ff9f1c"),
}


def acento_actual():
    """Color elegido por el usuario PRO (tema.json). HELLOP_ACCENT lo fuerza en pruebas."""
    nombre = os.environ.get("HELLOP_ACCENT", "").strip().lower()
    if nombre not in ACENTOS:
        try:
            import json
            from util import APP_DIR
            nombre = str(json.loads((APP_DIR / "tema.json").read_text("utf-8")).get("acento", "")).lower()
        except Exception:  # noqa: BLE001
            nombre = ""
    return nombre if nombre in ACENTOS else "morado"


def guardar_acento(nombre):
    import json
    from util import APP_DIR
    if nombre not in ACENTOS:
        raise ValueError("Color desconocido")
    APP_DIR.mkdir(parents=True, exist_ok=True)
    (APP_DIR / "tema.json").write_text(json.dumps({"acento": nombre}), "utf-8")


def _hue(c):
    import colorsys
    r, g, b = int(c[1:3], 16) / 255, int(c[3:5], 16) / 255, int(c[5:7], 16) / 255
    return colorsys.rgb_to_hsv(r, g, b)[0]


ACENTO = acento_actual() if PRO_THEME else "verde"
if PRO_THEME:      # PRO: el color que haya elegido (morado por defecto)
    BG, SIDE, PANEL, PANEL2, BORDER, FG, MUTED, CYAN, PINK, VIOLET = ACENTOS[ACENTO]
    GREEN = "#5bff9a"            # el verde queda solo para «correcto / ok»
    HUE_SHIFT = (_hue(CYAN) - 0.42) % 1.0       # cuánto girar el tono del logo (verde ≈ 0,42)
else:              # GRATIS: verde
    BG, SIDE, PANEL, PANEL2, BORDER = "#040a07", "#07120c", "#0c1a12", "#132a1d", "#1f4a32"
    FG, MUTED = "#eafff2", "#8fb8a0"
    CYAN, PINK, VIOLET = "#19e68c", "#b6ff3c", "#00c2a8"
    GREEN = "#5bff9a"
    HUE_SHIFT = 0.0
YELLOW = "#ffd23f"
RED = "#ff4d5e"

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


def glow_image(cv, w, h, r, base, orbs, cell=5, hueco=None):
    """Fondo con «luces» difuminadas como UNA sola imagen (rápida de dibujar), con las esquinas redondeadas transparentes.
    Tk no tiene desenfoque: se calcula una imagen pequeña, un píxel por celda, y se agranda. Antes se pintaban miles de rectángulos
    y la ventana iba lenta; una imagen cuesta lo mismo que un solo dibujo.
    orbs: lista de (x, y, radio, color, fuerza) con x e y de 0 a 1 respecto al tamaño. hueco: zona tapada por el contenido (se salta)."""
    w, h = int(w), int(h)
    cw, ch = -(-w // cell), -(-h // cell)
    b0 = _rgb(base)
    luces = [(ox * w, oy * h, rad, _rgb(col), fz) for ox, oy, rad, col, fz in orbs]
    filas = []
    for j in range(ch):
        py = j * cell + cell / 2
        fila = []
        for i in range(cw):
            px = i * cell + cell / 2
            if hueco and hueco[0] <= px <= hueco[2] and hueco[1] <= py <= hueco[3]:
                fila.append(base)
                continue
            r_, g_, b_ = b0
            for lx, ly, rad, col, fz in luces:
                d2 = (px - lx) ** 2 + (py - ly) ** 2
                if d2 < rad * rad:
                    k = fz * (1 - (d2 ** 0.5) / rad) ** 2
                    r_ += (col[0] - r_) * k
                    g_ += (col[1] - g_) * k
                    b_ += (col[2] - b_) * k
            fila.append("#%02x%02x%02x" % (int(r_), int(g_), int(b_)))
        filas.append("{" + " ".join(fila) + "}")
    chica = tk.PhotoImage(master=cv, width=cw, height=ch)
    chica.put(" ".join(filas))
    img = chica.zoom(cell, cell)
    r = int(max(1, min(r, w / 2, h / 2)))
    for dy in range(r):                       # esquinas: lo que cae fuera del arco se vuelve transparente
        for dx in range(r):
            if (r - dx - 0.5) ** 2 + (r - dy - 0.5) ** 2 > (r - 0.5) ** 2:
                for x, y in ((dx, dy), (w - 1 - dx, dy), (dx, h - 1 - dy), (w - 1 - dx, h - 1 - dy)):
                    img.transparency_set(x, y, True)
    return img


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
        self._t, self._job, self._press = 0.0, None, False      # _t: 0 = reposo, 1 = ratón encima (transición suave)
        super().__init__(parent, bg=_bg_of(parent), highlightthickness=0, bd=0, cursor="hand2")
        self._resize()
        self.bind("<Enter>", lambda e: self._set_hover(True))
        self.bind("<Leave>", lambda e: self._set_hover(False))
        self.bind("<ButtonPress-1>", self._down)
        self.bind("<ButtonRelease-1>", self._click)
        self.bind("<Destroy>", self._stop)

    def _resize(self):
        w = self._font.measure(self._text) + self._padx * 2 + 4
        h = self._font.metrics("linespace") + self._pady * 2 + 4
        self.configure(width=w, height=h)
        self._draw()

    def _draw(self):
        self.delete("all")
        w, h = int(self["width"]), int(self["height"])
        c, bg, t = self.color, _bg_of(self.master), self._t
        dy = 1 if self._press else 0
        if not self.enabled:
            round_rect(self, 2, 2, w - 2, h - 2, 12, fill=PANEL2, outline=BORDER)
            fg = MUTED
        elif self.filled:
            if t > 0.03:                                                     # halo de brillo que crece al acercar el ratón
                round_rect(self, 0, 0, w, h, 14, fill=mix(bg, c, 0.35 * t), outline="")
            round_rect(self, 2, 2 + dy, w - 2, h - 2 + dy, 12, fill=mix(c, "#ffffff", 0.30 * t), outline="")
            fg = BG
        else:
            if t > 0.03:
                round_rect(self, 0, 0, w, h, 14, fill=mix(bg, c, 0.22 * t), outline="")
            round_rect(self, 2, 2 + dy, w - 2, h - 2 + dy, 12, fill=mix(PANEL2, c, 0.22 * t), outline=mix(c, "#ffffff", 0.25 * t), width=1)
            fg = mix(c, FG, t)
        self.create_text(w / 2, h / 2 + dy, text=self._text, fill=fg, font=self._font)
        self.configure(cursor="hand2" if self.enabled else "arrow")

    def _set_hover(self, flag):
        self._hover = flag
        if self._job is None:
            self._job = self.after(16, self._anim)

    def _anim(self):
        self._job = None
        goal = 1.0 if self._hover else 0.0
        self._t += (goal - self._t) * 0.35
        if abs(goal - self._t) < 0.03:
            self._t = goal
        else:
            self._job = self.after(16, self._anim)
        try:
            self._draw()
        except tk.TclError:
            pass

    def _stop(self, _e=None):
        if self._job is not None:
            try:
                self.after_cancel(self._job)
            except tk.TclError:
                pass
            self._job = None

    def _down(self, _e):
        if self.enabled:
            self._press = True
            self._draw()

    def _click(self, e):
        self._press = False
        self._draw()
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

    def __init__(self, parent, accent=CYAN, title=None, pad=14, radius=22, strip=True, fill=None, line=None, orbs=None):
        super().__init__(parent, bg=_bg_of(parent), highlightthickness=0, bd=0, height=40)
        self.accent, self.pad, self.radius, self.strip = accent, pad, radius, strip
        self.fill, self.line, self.orbs = fill or PANEL, line or BORDER, orbs
        self._inset = pad + (8 if strip else 0)
        self.body = tk.Frame(self, bg=self.fill)
        self._win = self.create_window(self._inset, pad, window=self.body, anchor="nw")
        if title:
            tk.Label(self.body, text=title, font=F(11, True), fg=accent, bg=self.fill).pack(anchor="w", pady=(0, 8))
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
        round_rect(self, 1, 1, w - 1, h - 1, self.radius, fill=self.fill, outline=self.line, tags="bg")
        r = self.radius
        if self.orbs and w > 60 and h > 40:
            if getattr(self, "_glow_key", None) != (w, h):
                self._glow_key, self._glow_img = (w, h), glow_image(self, w, h, r, self.fill, self.orbs, cell=6)
            self.create_image(0, 0, image=self._glow_img, anchor="nw", tags="bg")
            round_rect(self, 1, 1, w - 1, h - 1, r, fill="", outline=self.line, tags="bg")
        if self.strip:
            self.create_line(9, r, 9, h - r, fill=self.accent, width=3, capstyle="round", tags="bg")
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
    """Barra de degradado. Con animate=True el color «fluye» de izquierda a derecha."""

    def __init__(self, parent, height=3, stops=GRADIENT, width=None, animate=False):
        super().__init__(parent, height=height, bg=_bg_of(parent), highlightthickness=0, bd=0,
                         **({"width": width} if width else {}))
        self.stops, self.animate, self.phase, self._ids, self._wd = stops, animate, 0.0, [], 0
        self._loop = tuple(stops) + (stops[0],)               # degradado circular para que no se vea el salto
        self.bind("<Configure>", self._draw)
        if animate:
            self.after(80, self._tick)

    def _col(self, i, n):
        return gradient_color(self._loop if self.animate else self.stops, ((i / max(1, n)) + self.phase) % 1.0)

    def _draw(self, e):
        self.delete("all")
        self._wd = w = max(2, e.width)
        step = 6 if self.animate else 4
        self._ids = []
        n = len(range(0, w, step))
        for k, x in enumerate(range(0, w, step)):
            self._ids.append(self.create_rectangle(x, 0, x + step, e.height, fill=self._col(k, n), outline=""))

    def _tick(self):
        try:
            self.phase = (self.phase + 0.006) % 1.0
            n = len(self._ids)
            for k, rid in enumerate(self._ids):
                self.itemconfigure(rid, fill=self._col(k, n))
            self.after(80, self._tick)
        except tk.TclError:
            pass


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


# ---------------------------------------------------------------- chispas animadas
class SparkField(tk.Canvas):
    """Zona animada: aura que «respira» detrás del logo y chispas verdes que suben."""

    def __init__(self, parent, logo=None, bg=SIDE, n=26):
        super().__init__(parent, bg=bg, highlightthickness=0, bd=0, height=60)
        self._bgc, self.logo, self.n, self.t, self.parts = bg, logo, n, 0.0, []
        self.bind("<Configure>", self._reset)
        self.after(60, self._tick)

    def _reset(self, e):
        import random
        self.parts = [[random.uniform(0, max(1, e.width)), random.uniform(0, max(1, e.height)), random.uniform(0.25, 0.9),
                       random.uniform(1.2, 2.8), random.uniform(0, 6.28), random.choice((CYAN, PINK, VIOLET))] for _ in range(self.n)]

    def _tick(self):
        try:
            self.delete("all")
            w, h = self.winfo_width(), self.winfo_height()
            self.t += 0.06
            import math
            cx, cy = w / 2, h / 2
            if h > 90 and w > 90:                                           # aura que respira
                pulse = 0.5 + 0.5 * math.sin(self.t)
                for i in range(6):
                    r = 34 + i * 7 + 4 * pulse
                    self.create_oval(cx - r, cy - r, cx + r, cy + r, outline=mix(self._bgc, CYAN, max(0.0, 0.30 - 0.045 * i + 0.08 * pulse)))
            for p in self.parts:
                p[1] -= p[2]
                p[0] += math.sin(self.t + p[4]) * 0.25
                if p[1] < -4:
                    p[1], p[0] = h + 4, (p[0] % max(1, w))
                tw = 0.35 + 0.65 * (0.5 + 0.5 * math.sin(self.t * 2 + p[4]))
                r = p[3]
                self.create_oval(p[0] - r, p[1] - r, p[0] + r, p[1] + r, fill=mix(self._bgc, p[5], tw), outline="")
            if self.logo is not None and h > 90 and w > 90:
                self.create_image(cx, cy, image=self.logo)
            self.after(60, self._tick)
        except tk.TclError:
            pass


# ---------------------------------------------------------------- logo con aura que respira
class PulseLogo(tk.Canvas):
    """El logo con anillos de luz que se expanden suavemente."""

    def __init__(self, parent, image, size=76, bg=SIDE):
        super().__init__(parent, width=size, height=size, bg=bg, highlightthickness=0, bd=0)
        self.image, self.size, self._bgc, self.t = image, size, bg, 0.0
        self._job = None
        self.bind("<Destroy>", lambda e: self._stop())
        self._tick()

    def _stop(self):
        if self._job is not None:
            try:
                self.after_cancel(self._job)
            except tk.TclError:
                pass
            self._job = None

    def _tick(self):
        import math
        try:
            self.delete("all")
            c = self.size / 2
            for k in range(3):                                  # tres anillos desfasados que nacen del logo y se apagan
                ph = (self.t + k / 3) % 1.0
                r = 24 + ph * (c - 26)
                self.create_oval(c - r, c - r, c + r, c + r, outline=mix(self._bgc, CYAN, 0.55 * (1 - ph) ** 1.5), width=2)
            self.create_image(c, c, image=self.image)
            self.t = (self.t + 0.012) % 1.0
            self._job = self.after(50, self._tick)
        except tk.TclError:
            pass


# ---------------------------------------------------------------- logo en el color del tema
def themed_logo(img, force=False):
    """En PRO pasa el logo (verde) a morado girando el tono de cada pixel. En GRATIS lo deja igual.
    Si algo falla devuelve el logo original: nunca debe impedir que la app arranque."""
    if not (PRO_THEME or force):
        return img
    try:
        import colorsys
        out = img.copy()
        w, h = img.width(), img.height()
        for y in range(h):
            x = 0
            while x < w:
                if img.transparency_get(x, y):
                    x += 1
                    continue
                run = []
                x0 = x
                while x < w and not img.transparency_get(x, y):
                    r, g, b = img.get(x, y)
                    hh, ss, vv = colorsys.rgb_to_hsv(r / 255, g / 255, b / 255)
                    r2, g2, b2 = colorsys.hsv_to_rgb((hh + (HUE_SHIFT if PRO_THEME else 0.33)) % 1.0, ss, vv)
                    run.append("#%02x%02x%02x" % (int(r2 * 255), int(g2 * 255), int(b2 * 255)))
                    x += 1
                out.put("{" + " ".join(run) + "}", to=(x0, y))
        return out
    except Exception:  # noqa: BLE001
        return img


class PillBar(tk.Canvas):
    """Barra fina con extremos redondeados (0-100 %)."""

    def __init__(self, parent, color=CYAN, pct=0.0, bg=None, height=7):
        super().__init__(parent, bg=bg or _bg_of(parent), width=10, height=height, highlightthickness=0, bd=0)
        self.color, self.pct, self._h = color, pct, height
        self.bind("<Configure>", lambda e: self._draw())

    def set(self, pct, color=None):
        self.pct = max(0.0, min(100.0, float(pct)))
        if color:
            self.color = color
        self._draw()

    def _draw(self):
        self.delete("all")
        w, h = max(10, self.winfo_width()), self._h
        round_rect(self, 0, 0, w, h, h / 2, fill=mix(_bg_of(self), "#ffffff", 0.10), outline="")
        if self.pct > 0:
            round_rect(self, 0, 0, max(h, w * self.pct / 100), h, h / 2, fill=self.color, outline="")


class PanelRedondo(tk.Canvas):
    """Panel que llena todo el alto, con esquinas redondeadas y borde de color suave (la barra lateral). El contenido va en `.body`."""

    def __init__(self, parent, fill=None, line=None, radius=26, margen=8):
        super().__init__(parent, bg=_bg_of(parent), highlightthickness=0, bd=0)
        self.fill, self.line, self.radius, self.margen = fill or SIDE, line or BORDER, radius, margen
        self.body = tk.Frame(self, bg=self.fill)
        self._win = self.create_window(margen + 2, margen + 2, window=self.body, anchor="nw")
        self.bind("<Configure>", self._redraw)

    def _redraw(self, e):
        w, h, m = e.width, e.height, self.margen
        self.delete("bg")
        round_rect(self, 1, 1, w - 1, h - 1, self.radius, fill=self.fill, outline=self.line, tags="bg")
        self.itemconfigure(self._win, width=max(20, w - 2 * m - 4), height=max(20, h - 2 * m - 4))
        self.tag_lower("bg")


class PanelGlow(tk.Canvas):
    """Cuadro de esquinas redondeadas con luces de color difuminadas en el borde (el contenido va en `.body`).
    Como el contenido tapa el centro, la luz se ve como un resplandor suave alrededor."""

    def __init__(self, parent, fill=None, line=None, radius=28, margen=16, orbs=None):
        super().__init__(parent, bg=_bg_of(parent), highlightthickness=0, bd=0)
        self.fill, self.line, self.radius, self.margen = fill or BG, line or BORDER, radius, margen
        self.orbs = orbs or [(0.12, 0.02, 520, CYAN, 0.70), (0.92, 0.99, 500, PINK, 0.55)]
        self.body = tk.Frame(self, bg=self.fill)
        self._win = self.create_window(margen, margen, window=self.body, anchor="nw")
        self._job = None
        self.bind("<Configure>", self._conf)

    def _conf(self, e):
        w, h, m = e.width, e.height, self.margen
        self.itemconfigure(self._win, width=max(20, w - 2 * m), height=max(20, h - 2 * m))
        if self._job:
            self.after_cancel(self._job)
        self._job = self.after(60, self._pinta)

    def _pinta(self):
        self._job = None
        try:
            w, h, m = self.winfo_width(), self.winfo_height(), self.margen
            if w < 60 or h < 60:
                return
            self.delete("bg")
            if getattr(self, "_glow_key", None) != (w, h):
                self._glow_key = (w, h)
                self._glow_img = glow_image(self, w, h, self.radius, self.fill, self.orbs, cell=5, hueco=(m + 6, m + 6, w - m - 6, h - m - 6))
            self.create_image(0, 0, image=self._glow_img, anchor="nw", tags="bg")
            round_rect(self, 1, 1, w - 1, h - 1, self.radius, fill="", outline=self.line, tags="bg")
            self.tag_lower("bg")
        except tk.TclError:
            pass
