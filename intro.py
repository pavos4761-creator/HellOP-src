"""Intro al abrir HellOP: el logo (capas de chip + núcleo) se dibuja solo, aparece el nombre y una cortina sube y deja ver la app.
Todo se calcula con el reloj (no con el número de fotogramas), así va fluido aunque el PC esté ocupado. Un clic la salta."""
import math
import random
import time
import tkinter as tk

from widgets import F, mix

FONDO = "#090b13"
TILE = "#0e1119"
BLANCO = "#f4f6ff"
SUAVE = "#8a93b5"
A, B = "#6d8bff", "#2fd4c0"
DUR = 3.25


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


def _in(t):                                     # acelera al salir
    t = max(0.0, min(1.0, t))
    return t * t * t


class Intro(tk.Canvas):
    """Orden: 1) las partículas llegan en espiral y forman los anillos del logo, 2) el núcleo se enciende con un destello
    y una onda, 3) el nombre entra letra a letra, 4) la capa sube y deja ver la app."""

    def __init__(self, app):
        super().__init__(app, bg=FONDO, highlightthickness=0, bd=0)
        self.app = app
        self.place(x=0, y=0, relwidth=1, relheight=1)
        tk.Misc.lift(self)
        self.fin = False
        self.t0 = None
        self.s = 1.15
        import re
        m = re.match(r"(\d+)x(\d+)", getattr(app, "_geom0", ""))
        self.W0, self.H0 = (int(m.group(1)), int(m.group(2))) if m else (1180, 800)
        import random
        import tkinter.font as tkfont
        rnd = random.Random(11)
        self.rings = []
        for x0, r, op, dash, off, w in ((38, 34, 0.55, 300, 0, 7), (56, 24, 0.85, 230, 60, 8)):
            pts, tot = _camino(x0, x0, 200 - x0, 200 - x0, r)
            self.rings.append((pts, tot, off, off + dash, op, w))
        # partículas: cada una viaja hasta un punto de los anillos
        self.part = []
        for (pts, tot, a0, a1, op, w), n in zip(self.rings, (46, 36)):
            tr = _tramo(pts, tot, a0, a1)
            for k in range(n):
                f = k / n
                x, y = tr[min(len(tr) - 1, int(f * (len(tr) - 1)))]
                self.part.append((x, y, rnd.random() * 6.283, 0.55 + rnd.random() * 0.45, rnd.random() * 0.45, 1.3 + rnd.random() * 1.7, f))
        self.motas = [(rnd.random(), rnd.random(), 0.03 + rnd.random() * 0.06, 0.8 + rnd.random() * 1.6, rnd.random() * 6.28) for _ in range(40)]
        self.fuente = tkfont.Font(font=F(32, True))
        self.letras = [("H", BLANCO), ("e", BLANCO), ("l", BLANCO), ("l", BLANCO), ("O", A), ("P", A)]
        self.bind("<Button-1>", lambda e: self.acaba())

    def inicia(self):
        tk.Misc.lift(self)
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
            self.after(8, self._frame)

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
        W, H = self.W0, self.H0
        cort = _in(_span(t, 2.7, DUR))
        if cort > 0:
            self.place_configure(y=-int(H * cort))
        cx, cy = W / 2, H / 2 - 30
        self._fondo(t, W, H, cx, cy)
        golpe = 1.0 + 0.05 * math.sin(math.pi * _span(t, 1.45, 1.95)) if 1.45 < t < 1.95 else 1.0
        s = self.s * golpe * (0.9 + 0.1 * _out(_span(t, 0.3, 1.2)))
        X = lambda x: cx + (x - 100) * s
        Y = lambda y: cy + (y - 100) * s
        # baldosa del logo
        ap = _out(_span(t, 0.5, 1.2))
        if ap > 0:
            self._rr(X(10), Y(10), X(190), Y(190), 48 * s, mix(FONDO, TILE, ap), mix(FONDO, "#262c44", ap))
        # partículas en espiral hacia los anillos
        D = max(W, H) * 0.75
        for x, y, ang, vel, retraso, r, f in self.part:
            p = _ease(_span(t, retraso, retraso + 0.85))
            tx, ty = X(x), Y(y)
            if p <= 0:
                continue
            giro = (1 - p) * 2.2
            rad = (1 - p) * D * vel
            px = tx + rad * math.cos(ang + giro)
            py = ty + rad * math.sin(ang + giro)
            q = _ease(_span(t, retraso, retraso + 0.85) - 0.06)
            rq = (1 - q) * D * vel
            qx, qy = tx + rq * math.cos(ang + (1 - q) * 2.2), ty + rq * math.sin(ang + (1 - q) * 2.2)
            vis = min(1.0, p * 3) * (1 - _ease(_span(t, 1.0, 1.35)))
            col = mix(FONDO, mix(A, B, f), 0.85 * vis)
            if vis > 0.02:
                self.create_line(qx, qy, px, py, fill=mix(FONDO, mix(A, B, f), 0.45 * vis), width=max(1, r * 0.8))
                self.create_oval(px - r, py - r, px + r, py + r, outline="", fill=col)
        # anillos: aparecen cuando llegan las partículas
        fa = _ease(_span(t, 0.85, 1.45))
        if fa > 0:
            for pts, tot, a0, a1, op, w in self.rings:
                self._linea(_tramo(pts, tot, a0, a1), w * s, op * fa, X, Y)
        # destello y núcleo
        g = _span(t, 1.35, 1.9)
        if g > 0:
            ge = _out(g)
            fl = max(0.0, 1 - _span(t, 1.4, 1.9))
            for i in range(10, 0, -1):
                r = (36 + 40 * fl) * s * (i / 10)
                self.create_oval(cx - r, cy - r, cx + r, cy + r, outline="",
                                 fill=mix(TILE, "#bff7ee", min(1.0, (0.9 * (1 - i / 10) ** 1.7 * ge) + 0.5 * fl * (1 - i / 10))))
            r = 15 * s * _back(g)
            if r > 0:
                self.create_oval(cx - r, cy - r, cx + r, cy + r, outline="", fill=mix(mix(A, B, 0.5), "#ffffff", 0.6 * fl))
        # ondas que salen del núcleo
        for ini in (1.4, 1.62):
            o = _span(t, ini, ini + 0.9)
            if 0 < o < 1:
                r = (20 + 150 * _out(o)) * s
                self.create_oval(cx - r, cy - r, cx + r, cy + r, outline=mix(FONDO, B, 0.5 * (1 - o) ** 1.5),
                                 width=max(1, 2.5 * s * (1 - o)), fill="")
        # nombre, letra a letra
        ty = cy + 100 * s + 40
        total = sum(self.fuente.measure(l) for l, _c in self.letras)
        x = W / 2 - total / 2
        for i, (l, col) in enumerate(self.letras):
            e = _out(_span(t, 1.75 + i * 0.06, 2.15 + i * 0.06))
            if e > 0:
                self.create_text(x, ty + 16 * (1 - e), text=l, anchor="w", fill=mix(FONDO, col, e), font=F(32, True))
            x += self.fuente.measure(l)
        m = _ease(_span(t, 2.15, 2.6))
        if m > 0:
            self.create_text(W / 2, ty + 40, text="Tu PC, al máximo", fill=mix(FONDO, SUAVE, m), font=F(10))
            ln = _out(_span(t, 2.1, 2.7)) * 70
            self.create_line(W / 2 - ln, ty + 62, W / 2 + ln, ty + 62, fill=mix(FONDO, B, 0.55 * (1 - _span(t, 2.4, 2.7) if t > 2.4 else 1)), width=2)

    def _fondo(self, t, W, H, cx, cy):
        """Luces suaves que se mueven y motas que suben; todo se enciende un poco más con el destello."""
        ap = _ease(_span(t, 0.0, 0.7))
        pico = 1 + 0.9 * max(0.0, 1 - abs(t - 1.55) / 0.35)
        orbs = ((0.22 + 0.06 * math.sin(t * 0.9), 0.30 + 0.05 * math.cos(t * 0.7), 0.30, A, 0.30),
                (0.78 + 0.06 * math.cos(t * 0.8), 0.72 + 0.05 * math.sin(t * 0.9), 0.30, B, 0.24))
        for fx, fy, fr, col, fuerza in orbs:
            R = fr * max(W, H)
            for k in range(13, 1, -1):
                r = R * k / 13
                a = min(0.6, fuerza * ap * pico * (1 - k / 13) ** 1.3 * 0.9)
                self.create_oval(fx * W - r, fy * H - r, fx * W + r, fy * H + r, outline="", fill=mix(FONDO, col, a))
        for x, y0, v, r, ph in self.motas:
            y = (y0 - t * v) % 1.0
            vis = ap * (0.5 + 0.5 * math.sin(t * 1.6 + ph)) * min(1.0, y * 6, (1 - y) * 6)
            px = x * W + 12 * math.sin(t * 0.8 + ph)
            self.create_oval(px - r, y * H - r, px + r, y * H + r, outline="", fill=mix(FONDO, mix(A, B, x), 0.55 * vis))

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
