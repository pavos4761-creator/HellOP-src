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


def _png(w, h, raw):
    import struct
    import zlib

    def chunk(t, d):
        c = struct.pack(">I", len(d)) + t + d
        return c + struct.pack(">I", zlib.crc32(t + d) & 0xFFFFFFFF)
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 6, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(bytes(raw), 1)) + chunk(b"IEND", b""))


_DISCOS = {}


def disco(master, r, color):
    """Círculo con borde suave (antialias), con caché por tamaño y color."""
    k = (round(r * 2), color)
    img = _DISCOS.get(k)
    if img is None:
        rr = k[0] / 2
        n = int(math.ceil(rr)) * 2 + 4
        c = n / 2
        rgb = bytes(int(color[j:j + 2], 16) for j in (1, 3, 5))
        raw = bytearray()
        for y in range(n):
            raw += b"\x00"
            for x in range(n):
                cov = min(1.0, max(0.0, rr + 0.5 - math.hypot(x + 0.5 - c, y + 0.5 - c)))
                raw += rgb + bytes((int(cov * 255),))
        img = tk.PhotoImage(master=master, data=_png(n, n, raw))
        _DISCOS[k] = img
    return img


class Intro(tk.Canvas):
    """Orden: 1) las partículas llegan en espiral y forman los anillos del logo, 2) el núcleo se enciende con un destello
    y una onda, 3) el nombre entra letra a letra, 4) la capa sube y deja ver la app.
    Los elementos se crean UNA vez y cada fotograma solo se mueven: así va a 120 fotogramas por segundo."""
    FPS = 120

    def __init__(self, app):
        super().__init__(app, bg=FONDO, highlightthickness=0, bd=0)
        self.app = app
        self.place(x=0, y=0, relwidth=1, relheight=1)
        tk.Misc.lift(self)
        self.fin = False
        self.t0 = None
        self.s = 1.15
        import random
        import re
        import tkinter.font as tkfont
        import intro_data
        m = re.match(r"(\d+)x(\d+)", getattr(app, "_geom0", ""))
        self.W0, self.H0 = (int(m.group(1)), int(m.group(2))) if m else (1180, 800)
        W, H = self.W0, self.H0
        self.cx, self.cy = W / 2, H / 2 - 30
        rnd = random.Random(11)
        rings = []
        for x0, r, op, dash, off, w in ((38, 34, 0.55, 300, 0, 7), (56, 24, 0.85, 230, 60, 8)):
            pts, tot = _camino(x0, x0, 200 - x0, 200 - x0, r)
            rings.append(_tramo(pts, tot, off, off + dash))
        self.part = []
        for tr, n in zip(rings, (46, 36)):
            for k in range(n):
                f = k / n
                x, y = tr[min(len(tr) - 1, int(f * (len(tr) - 1)))]
                self.part.append((x, y, rnd.random() * 6.283, 0.55 + rnd.random() * 0.45, rnd.random() * 0.45, 1.3 + rnd.random() * 1.7, f))
        self.motas = [(rnd.random(), rnd.random(), 0.03 + rnd.random() * 0.06, 0.8 + rnd.random() * 1.6, rnd.random() * 6.28) for _ in range(26)]
        self.fuente = tkfont.Font(font=F(32, True))
        self.letras = [("H", BLANCO), ("e", BLANCO), ("l", BLANCO), ("l", BLANCO), ("O", A), ("P", A)]
        self.img_tile = [tk.PhotoImage(master=app, data=d) for d in intro_data.TILE]
        self.img_ring = [tk.PhotoImage(master=app, data=d) for d in intro_data.RING]
        self.img_orb = [tk.PhotoImage(master=app, data=intro_data.ORB_A).zoom(3, 3), tk.PhotoImage(master=app, data=intro_data.ORB_B).zoom(3, 3)]
        self._last, self._vis = {}, {}
        # --- elementos (orden = capas, de abajo arriba) ---
        self.orbs = [self.create_image(0, 0, image=im, anchor="center") for im in self.img_orb]
        self.m_ids = [self.create_oval(0, 0, 1, 1, outline="", fill=FONDO, state="hidden") for _ in self.motas]
        self.tile_id = self.create_image(self.cx, self.cy, image=self.img_tile[0], anchor="center", state="hidden")
        self.glow_ids = [self.create_oval(0, 0, 1, 1, outline="", fill=TILE, state="hidden") for _ in range(16)]
        self.ring_id = self.create_image(self.cx, self.cy, image=self.img_ring[0], anchor="center", state="hidden")
        self.p_ids = [(self.create_oval(0, 0, 1, 1, outline="", fill=FONDO, state="hidden"),
                       self.create_oval(0, 0, 1, 1, outline="", fill=FONDO, state="hidden")) for _ in self.part]
        self.core_id = self.create_image(self.cx, self.cy, anchor="center", state="hidden")
        self.w_ids = [self.create_oval(0, 0, 1, 1, outline=FONDO, fill="", state="hidden") for _ in range(2)]
        ty = self.cy + 100 * self.s + 40
        self.ty = ty
        total = sum(self.fuente.measure(l) for l, _c in self.letras)
        x = W / 2 - total / 2
        self.l_ids = []
        for l, col in self.letras:
            self.l_ids.append((self.create_text(x, ty, text=l, anchor="w", fill=FONDO, font=F(32, True), state="hidden"), x))
            x += self.fuente.measure(l)
        self.tag_id = self.create_text(W / 2, ty + 40, text="Tu PC, al máximo", fill=FONDO, font=F(10), state="hidden")
        self.line_id = self.create_line(0, 0, 1, 1, fill=FONDO, width=2, state="hidden")
        self.bind("<Button-1>", lambda e: self.acaba())
        self.pinta(0.0)

    # ---- ayudas para no tocar lo que no cambia ----
    def _v(self, i, on):
        if self._vis.get(i) != on:
            self._vis[i] = on
            self.itemconfigure(i, state="normal" if on else "hidden")

    def _c(self, i, **kw):
        k = tuple(sorted(kw.items()))
        if self._last.get(i) != k:
            self._last[i] = k
            self.itemconfigure(i, **kw)

    # ---- reloj ----
    def inicia(self):
        tk.Misc.lift(self)
        try:
            import ctypes
            ctypes.windll.winmm.timeBeginPeriod(1)             # relojes de 1 ms en Windows (por defecto son de ~15 ms)
            self._timer = True
        except Exception:  # noqa: BLE001
            self._timer = False
        self.t0 = time.perf_counter()
        self._sig = self.t0
        self.after(int((DUR + 0.7) * 1000), self.acaba)       # pase lo que pase, a los pocos segundos entra solo a la app
        self._frame()

    def _frame(self):
        if self.fin:
            return
        ahora = time.perf_counter()
        t = ahora - self.t0
        try:
            self.pinta(t)
        except tk.TclError:
            self.acaba()
            return
        except Exception:  # noqa: BLE001
            self._anota()
            self.acaba()
            return
        if t >= DUR:
            self.acaba()
            return
        self._sig += 1.0 / self.FPS
        ahora = time.perf_counter()
        if self._sig < ahora - 0.03:                              # si va retrasado, no intenta recuperar: sigue desde ahora
            self._sig = ahora
        self.after(max(1, int((self._sig - ahora) * 1000)), self._frame)

    def _anota(self):
        try:
            import traceback
            from util import APP_DIR
            with open(APP_DIR / "errores.log", "a", encoding="utf-8") as f:
                f.write(time.strftime("%Y-%m-%d %H:%M:%S") + " intro\n" + traceback.format_exc() + "\n")
        except Exception:  # noqa: BLE001
            pass

    def acaba(self):
        if self.fin:
            return
        self.fin = True
        try:
            if getattr(self, "_timer", False):
                import ctypes
                ctypes.windll.winmm.timeEndPeriod(1)
        except Exception:  # noqa: BLE001
            pass
        try:
            self.place_forget()
            self.destroy()
        except tk.TclError:
            pass

    # ---------------------------------------------------------------
    def pinta(self, t):
        W, H, cx, cy, s = self.W0, self.H0, self.cx, self.cy, self.s
        cort = _in(_span(t, 2.7, DUR))
        if cort > 0:
            self.place_configure(y=-int(H * cort))
        # luces de fondo
        paso = int(t * 20)                                  # las luces grandes se mueven despacio: se recolocan 20 veces por segundo
        if paso != getattr(self, "_paso_orbs", -1):
            self._paso_orbs = paso
            for oid, (fx, fy) in zip(self.orbs, ((0.22 + 0.06 * math.sin(t * 0.9), 0.30 + 0.05 * math.cos(t * 0.7)),
                                                  (0.78 + 0.06 * math.cos(t * 0.8), 0.72 + 0.05 * math.sin(t * 0.9)))):
                self.coords(oid, fx * W, fy * H)
        ap = _ease(_span(t, 0.0, 0.7))
        for mid, (x, y0, v, r, ph) in zip(self.m_ids, self.motas):
            y = (y0 - t * v) % 1.0
            vis = ap * (0.5 + 0.5 * math.sin(t * 1.6 + ph)) * min(1.0, y * 6, (1 - y) * 6)
            if vis < 0.03:
                self._v(mid, False)
                continue
            px = x * W + 12 * math.sin(t * 0.8 + ph)
            self.coords(mid, px - r, y * H - r, px + r, y * H + r)
            self._c(mid, fill=mix(FONDO, mix(A, B, x), 0.55 * vis))
            self._v(mid, True)
        # baldosa
        a = _out(_span(t, 0.5, 1.2))
        if a > 0:
            self._c(self.tile_id, image=self.img_tile[min(5, int(a * 5.999))])
            self._v(self.tile_id, True)
        # partículas en espiral
        X = lambda x: cx + (x - 100) * s
        Y = lambda y: cy + (y - 100) * s
        D = max(W, H) * 0.75
        activo = t < 1.4
        for (x, y, ang, vel, retraso, r, f), (h_id, t_id) in zip(self.part, self.p_ids):
            p = _ease(_span(t, retraso, retraso + 0.85))
            vis = min(1.0, p * 3) * (1 - _ease(_span(t, 1.0, 1.35)))
            if not activo or p <= 0 or vis <= 0.02:
                self._v(h_id, False)
                self._v(t_id, False)
                continue
            tx, ty = X(x), Y(y)
            col = mix(A, B, f)
            for i_, dq, al, rr in ((h_id, 0.0, 1.0, r), (t_id, 0.07, 0.35, r * 0.7)):
                q = max(0.0, p - dq)
                rad = (1 - q) * D * vel
                px = tx + rad * math.cos(ang + (1 - q) * 2.2)
                py = ty + rad * math.sin(ang + (1 - q) * 2.2)
                self.coords(i_, px - rr, py - rr, px + rr, py + rr)
                self._c(i_, fill=mix(FONDO, col, 0.9 * vis * al))
                self._v(i_, True)
        # anillos
        fa = _ease(_span(t, 0.85, 1.45))
        if fa > 0:
            self._c(self.ring_id, image=self.img_ring[min(5, int(fa * 5.999))])
            self._v(self.ring_id, True)
        # destello y núcleo
        g = _span(t, 1.35, 1.9)
        if g > 0:
            ge = _out(g)
            fl = max(0.0, 1 - _span(t, 1.4, 1.9))
            for k, gid in enumerate(self.glow_ids):
                i = 16 - k
                r = (36 + 40 * fl) * s * (i / 16)
                self.coords(gid, cx - r, cy - r, cx + r, cy + r)
                self._c(gid, fill=mix(TILE, "#bff7ee", min(1.0, (0.9 * (1 - i / 16) ** 1.7 * ge) + 0.5 * fl * (1 - i / 16))))
                self._v(gid, True)
            r = 15 * s * _back(g)
            if r > 0.5:
                col = mix(mix(A, B, 0.5), "#ffffff", round(0.6 * fl * 4) / 4)
                self._c(self.core_id, image=disco(self.app, r, col))
                self._v(self.core_id, True)
        # ondas
        for wid, ini in zip(self.w_ids, (1.4, 1.62)):
            o = _span(t, ini, ini + 0.9)
            if 0 < o < 1:
                r = (20 + 150 * _out(o)) * s
                self.coords(wid, cx - r, cy - r, cx + r, cy + r)
                self._c(wid, outline=mix(FONDO, B, 0.5 * (1 - o) ** 1.5), width=max(1, 2.5 * s * (1 - o)))
                self._v(wid, True)
            else:
                self._v(wid, False)
        # nombre
        for i, ((lid, x), (_l, col)) in enumerate(zip(self.l_ids, self.letras)):
            e = _out(_span(t, 1.75 + i * 0.06, 2.15 + i * 0.06))
            if e > 0:
                self.coords(lid, x, self.ty + 16 * (1 - e))
                self._c(lid, fill=mix(FONDO, col, e))
                self._v(lid, True)
        m = _ease(_span(t, 2.15, 2.6))
        if m > 0:
            self._c(self.tag_id, fill=mix(FONDO, SUAVE, m))
            self._v(self.tag_id, True)
            ln = _out(_span(t, 2.1, 2.7)) * 70
            self.coords(self.line_id, W / 2 - ln, self.ty + 62, W / 2 + ln, self.ty + 62)
            self._c(self.line_id, fill=mix(FONDO, B, 0.55 * (1 - _span(t, 2.4, 2.7) if t > 2.4 else 1)))
            self._v(self.line_id, True)
