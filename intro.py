"""Intro al abrir HellOP: el logo (capas de chip + núcleo) se dibuja solo, aparece el nombre y una cortina sube y deja ver la app.
Todo se calcula con el reloj (no con el número de fotogramas), así va fluido aunque el PC esté ocupado. Un clic la salta."""
import math
import time
import tkinter as tk

from widgets import BG, CYAN, F, FG, MUTED, mix

TILE = "#0e1119"
A, B = "#6d8bff", "#2fd4c0"
DUR = 2.55


def _ease(t):                                   # suave al empezar y al acabar
    t = max(0.0, min(1.0, t))
    return t * t * (3 - 2 * t)


def _out(t):                                    # frena al llegar
    t = max(0.0, min(1.0, t))
    return 1 - (1 - t) ** 3


def _back(t):                                   # pasa un poco y vuelve (rebote suave)
    t = max(0.0, min(1.0, t))
    c = 1.9
    return 1 + (c + 1) * (t - 1) ** 3 + c * (t - 1) ** 2


def _span(t, a, b):
    return (t - a) / (b - a)


def _camino(x0, y0, x1, y1, r, paso=3.0):
    """Puntos de un rectángulo redondeado, en sentido horario desde justo después de la esquina superior izquierda."""
    pts = []
    esq = ((x1 - r, y0 + r, -90), (x1 - r, y1 - r, 0), (x0 + r, y1 - r, 90), (x0 + r, y0 + r, 180))
    pts.append((x0 + r, y0))
    for i, (cx, cy, a0) in enumerate(esq):
        # lado recto hasta la esquina
        if i == 0:
            pts.append((x1 - r, y0))
        for k in range(1, 13):
            a = math.radians(a0 + 90 * k / 12)
            pts.append((cx + r * math.cos(a), cy + r * math.sin(a)))
        nxt = ((x1, y1 - r), (x0 + r, y1), (x0, y0 + r), (x0 + r, y0))[i]
        pts.append(nxt)
    out, tot = [pts[0]], [0.0]
    for p, q in zip(pts, pts[1:]):
        d = math.dist(p, q)
        if d > 0.01:
            out.append(q)
            tot.append(tot[-1] + d)
    return out, tot


def _tramo(pts, tot, a, b):
    """Puntos del camino entre las distancias a y b (con los extremos interpolados)."""
    def en(d):
        for i in range(1, len(tot)):
            if tot[i] >= d:
                f = (d - tot[i - 1]) / max(1e-9, tot[i] - tot[i - 1])
                (x0, y0), (x1, y1) = pts[i - 1], pts[i]
                return (x0 + (x1 - x0) * f, y0 + (y1 - y0) * f)
        return pts[-1]
    res = [en(a)]
    res += [p for p, d in zip(pts, tot) if a < d < b]
    res.append(en(b))
    return res


class Intro(tk.Canvas):
    def __init__(self, app):
        super().__init__(app, bg=BG, highlightthickness=0, bd=0)
        self.app = app
        self.place(x=0, y=0, relwidth=1, relheight=1)
        tk.Misc.lift(self)
        self.fin = False
        self.t0 = None
        self.s = 1.15                                   # el logo ocupa 180·s px
        self.rings = []
        for x0, r, ancho, op, dash, off, w in ((38, 34, 7, 0.45, 300, 0, 7), (56, 24, 8, 0.75, 230, 60, 8)):
            pts, tot = _camino(x0, x0, 200 - x0, 200 - x0, r)
            self.rings.append((pts, tot, off, off + dash, op, w))
        self.bind("<Button-1>", lambda e: self.acaba())
        self.after(30, self._arranca)

    def _arranca(self):
        self.t0 = time.perf_counter()
        self._frame()

    def _frame(self):
        if self.fin:
            return
        t = time.perf_counter() - self.t0
        try:
            self.pinta(t)
        except tk.TclError:
            return
        if t >= DUR:
            self.acaba()
        else:
            self.after(10, self._frame)

    def acaba(self):
        if self.fin:
            return
        self.fin = True
        try:
            self.place_forget()
            self.destroy()
        except tk.TclError:
            pass

    # ---------------------------------------------------------------
    def pinta(self, t):
        self.delete("all")
        if not getattr(self, "H0", None):
            self.H0, self.W0 = max(300, self.app.winfo_height()), max(300, self.app.winfo_width())
        W, H = self.W0, self.H0
        # cortina final: la capa sube y deja ver la app
        cort = _ease(_span(t, 2.0, DUR))
        if cort > 0:
            self.place_configure(y=-int(self.H0 * cort))
        s = self.s * (0.88 + 0.12 * _out(_span(t, 0.0, 0.7)))
        cx, cy = W / 2, H / 2 - 34
        k = 180 * s / 180                             # escala SVG(200) → píxeles: 1 unidad = s px
        X = lambda x: cx + (x - 100) * s
        Y = lambda y: cy + (y - 100) * s
        # baldosa
        ap = _out(_span(t, 0.0, 0.5))
        if ap > 0:
            col = mix(BG, TILE, ap)
            self._rr(X(10), Y(10), X(190), Y(190), 48 * s, col, mix(BG, mix(TILE, "#ffffff", 0.10), ap))
        # anillos que se dibujan solos
        horario = ((0.30, 1.05), (0.55, 1.30))
        for (pts, tot, a0, a1, op, w), (ta, tb) in zip(self.rings, horario):
            p = _ease(_span(t, ta, tb))
            if p <= 0:
                continue
            tr = _tramo(pts, tot, a0, a0 + (a1 - a0) * p)
            self._linea(tr, w * s, op, X, Y)
        # núcleo y brillo
        g = _span(t, 0.95, 1.45)
        if g > 0:
            ge = _out(g)
            for i in range(9, 0, -1):
                r = 34 * s * (i / 9) * (0.6 + 0.4 * ge)
                self.create_oval(cx - r, cy - r, cx + r, cy + r, outline="", fill=mix(TILE, "#9ff3e6", 0.9 * (1 - i / 9) ** 1.8 * ge))
            r = 15 * s * _back(g)
            if r > 0:
                self.create_oval(cx - r, cy - r, cx + r, cy + r, outline="", fill=mix(A, B, 0.5))
        # onda que sale del núcleo
        o = _span(t, 1.35, 1.95)
        if 0 < o < 1:
            r = (18 + 70 * _out(o)) * s
            self.create_oval(cx - r, cy - r, cx + r, cy + r, outline=mix(TILE, B, 0.55 * (1 - o)), width=max(1, 2 * s * (1 - o)), fill="")
        # nombre
        n = _ease(_span(t, 1.35, 1.85))
        if n > 0:
            ty = cy + 100 * s + 34 + 10 * (1 - n)
            self.create_text(W / 2 - 1, ty, text="Hell", anchor="e", fill=mix(BG, FG, n), font=F(30, True))
            self.create_text(W / 2 - 1, ty, text="OP", anchor="w", fill=mix(BG, CYAN, n), font=F(30, True))
            m = _ease(_span(t, 1.55, 2.0))
            self.create_text(W / 2, ty + 34, text="Tu PC, al máximo", fill=mix(BG, MUTED, m), font=F(10))

    def _rr(self, x0, y0, x1, y1, r, fill, outline):
        pts = []
        for cx, cy, a0 in ((x1 - r, y0 + r, -90), (x1 - r, y1 - r, 0), (x0 + r, y1 - r, 90), (x0 + r, y0 + r, 180)):
            for k in range(0, 13):
                a = math.radians(a0 + 90 * k / 12)
                pts += [cx + r * math.cos(a), cy + r * math.sin(a)]
        self.create_polygon(pts, fill=fill, outline=outline, width=1)

    def _linea(self, tr, ancho, op, X, Y):
        """Trazo con degradado diagonal (de A a B) y semitransparencia imitada mezclando con la baldosa."""
        n = len(tr)
        paso = max(1, n // 40)
        for i in range(0, n - 1, paso):
            seg = tr[i:i + paso + 1]
            mx = sum(p[0] + p[1] for p in seg) / len(seg) / 400
            col = mix(TILE, mix(A, B, max(0, min(1, mx))), op)
            self.create_line([c for p in seg for c in (X(p[0]), Y(p[1]))], fill=col, width=ancho, capstyle="round", joinstyle="round")
