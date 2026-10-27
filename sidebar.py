"""Barra lateral «neón cristal»: un panel flotante de esquinas redondeadas con luces de color difuminadas detrás.

Tk no sabe desenfocar ni hacer transparencias, así que TODO el panel (fondo, luces, menú, barras en vivo) se pinta en un solo lienzo:
las luces son una cuadrícula fina de rectángulos cuyo color sube suavemente cerca de cada luz, y como el menú también se dibuja
encima (no son widgets con fondo propio) se ve el brillo detrás de cada entrada.
"""
import math
import tkinter as tk

import anim
from widgets import BORDER, CYAN, VIOLET, F, FG, GREEN, MUTED, PANEL2, PINK, RED, SIDE, YELLOW, _bg_of, glow_image, mix, round_rect

PASO = 28          # alto de cada fila de menú
CABECERA = 30      # alto de cada título de sección
VIVO = 76          # alto de la zona «en vivo» de abajo


class _Entrada:
    """Cada entrada del menú (misma interfaz que tenía el antiguo NavItem)."""

    def __init__(self, barra, key, icon, text):
        self.b, self.key, self.icon, self.text = barra, key, icon, text
        self.hov = self.act = 0.0
        self.active = self.hgoal = False
        self.pro = False
        self.dot, self.pulse = None, 0.0

    def set_active(self, on):
        self.active = on
        self.b._anima()

    def set_pro(self, on):
        self.pro = on
        self.b._dibuja(self)

    def set_dot(self, color):
        self.dot = color
        self.b._dibuja(self)

    def beat(self, phase):
        if self.dot:
            self.pulse = phase
            self.b._dibuja(self)


class _Barra:
    """Barrita CPU/RAM de la zona en vivo."""

    def __init__(self, barra, nombre, color, fila):
        self.b, self.nombre, self.color, self.fila, self.v = barra, nombre, color, fila, 0.0

    def set(self, v):
        self.v = max(0.0, min(100.0, float(v)))
        self.b._dibuja_vivo()


class _Etiqueta:
    def __init__(self, barra):
        self.b, self.fg = barra, MUTED

    def config(self, **kw):
        if "fg" in kw:
            self.fg = kw["fg"]
            self.b._dibuja_vivo()


class BarraLateral(tk.Canvas):
    def __init__(self, parent, sections, on_select):
        super().__init__(parent, bg=_bg_of(parent), highlightthickness=0, bd=0)
        self.on_select, self.off, self._job, self._rz = on_select, 0, None, None
        self.filas = []          # ("h", titulo) | ("i", entrada)
        self.nav = {}
        y = 0
        for titulo, items in sections:
            self.filas.append(["h", titulo, y])
            y += CABECERA
            for key, icon, text in items:
                e = _Entrada(self, key, icon, text)
                self.nav[key] = e
                e.fila = ["i", e, y]
                self.filas.append(e.fila)
                y += PASO
        self.alto_total = y
        self.live_lbl = _Etiqueta(self)
        self.bar_cpu = _Barra(self, "CPU", CYAN, 0)
        self.bar_ram = _Barra(self, "RAM", PINK, 1)
        self.bind("<Configure>", self._al_cambiar)
        self.bind("<Motion>", self._motion)
        self.bind("<Leave>", lambda e: self._hover(None))
        self.bind("<Button-1>", self._click)
        self.bind("<MouseWheel>", lambda e: self._rueda(-1 if e.delta > 0 else 1))
        self.bind("<Button-4>", lambda e: self._rueda(-1))
        self.bind("<Button-5>", lambda e: self._rueda(1))

    # ---- geometría ----
    def _vista(self):
        h = max(100, self.winfo_height())
        return 18, h - VIVO - 10        # (arriba, abajo) de la zona del menú

    def _max_off(self):
        a, b = self._vista()
        return max(0, self.alto_total - (b - a))

    def _y(self, fila):
        return self._vista()[0] + fila[2] - self.off

    def _visible(self, y, alto):
        a, b = self._vista()
        return y >= a - 1 and y + alto <= b + 1

    # ---- fondo ----
    def _al_cambiar(self, e):
        if self._rz:
            self.after_cancel(self._rz)
        self._rz = self.after(60, self._repinta)

    def _repinta(self):
        self._rz = None
        try:
            w, h = self.winfo_width(), self.winfo_height()
            if w < 60 or h < 100:
                return
            self.off = min(self.off, self._max_off())
            self.delete("bg")
            borde = mix(BORDER, CYAN, 0.35)
            if getattr(self, "_glow_key", None) != (w, h):
                self._glow_key = (w, h)
                self._glow_img = glow_image(self, w, h, 28, SIDE,
                                            [(0.1, 0.04, 380, CYAN, 0.50), (0.95, 0.97, 360, PINK, 0.38), (0.55, 0.5, 260, VIOLET, 0.10)], cell=5)
            self.create_image(0, 0, image=self._glow_img, anchor="nw", tags="bg")
            round_rect(self, 1, 1, w - 1, h - 1, 28, fill="", outline=borde, tags="bg")
            self.tag_lower("bg")
            self._dibuja_todo()
        except tk.TclError:
            pass

    # ---- dibujo ----
    def _dibuja_todo(self):
        self.delete("fila")
        self.delete("thumb")
        for f in self.filas:
            if f[0] == "i":
                self._dibuja(f[1])
            else:
                self._cabecera(f)
        w = self.winfo_width()
        mo = self._max_off()
        if mo:
            a, b = self._vista()
            alto = b - a
            th = max(24, alto * alto / self.alto_total)
            ty = a + (alto - th) * (self.off / mo)
            round_rect(self, w - 11, ty, w - 8, ty + th, 1.5, fill=mix(SIDE, MUTED, 0.45), outline="", tags="thumb")
        self._dibuja_vivo()

    def _cabecera(self, f):
        y = self._y(f)
        if self._visible(y, CABECERA - 6):
            self.create_text(26, y + 17, text=f[1], anchor="w", fill=mix(SIDE, MUTED, 0.9), font=F(8, True), tags="fila")

    def _dibuja(self, e):
        fila = e.fila
        tag = "e_" + e.key
        try:
            self.delete(tag)
            y = self._y(fila)
            if not self._visible(y, PASO):
                return
            w = self.winfo_width()
            k = max(e.hov * 0.5, e.act)
            if k > 0.02:
                round_rect(self, 12, y + 1, w - 12, y + PASO - 1, 13, fill=mix(SIDE, CYAN, 0.07 * e.hov + 0.22 * e.act),
                           outline=mix(SIDE, CYAN, 0.55 * e.act) if e.act > 0.1 else "", tags=(tag, "fila"))
            if e.act > 0.02:
                hg = 4 + 14 * e.act
                round_rect(self, 12, y + PASO / 2 - hg / 2, 15, y + PASO / 2 + hg / 2, 1.5, fill=CYAN, outline="", tags=(tag, "fila"))
            col = mix(mix(MUTED, FG, e.hov), CYAN, e.act)
            self.create_text(33, y + PASO / 2, text=e.icon, fill=col, font=F(11, True), tags=(tag, "fila"))
            self.create_text(52, y + PASO / 2, text=e.text, anchor="w", fill=col, font=F(10, True), tags=(tag, "fila"))
            if e.pro:
                self.create_text(w - 24, y + PASO / 2, text="PRO", anchor="e", fill=mix(SIDE, YELLOW, 0.8), font=F(7, True), tags=(tag, "fila"))
            if e.dot:
                a = 0.45 + 0.55 * (0.5 + 0.5 * math.sin(e.pulse))
                r = 4 + 1.5 * (0.5 + 0.5 * math.sin(e.pulse))
                cx, cy = w - 30, y + PASO / 2
                self.create_oval(cx - r - 3, cy - r - 3, cx + r + 3, cy + r + 3, fill=mix(SIDE, e.dot, 0.18 * a), outline="", tags=(tag, "fila"))
                self.create_oval(cx - r, cy - r, cx + r, cy + r, fill=mix(SIDE, e.dot, a), outline="", tags=(tag, "fila"))
        except tk.TclError:
            pass

    def _dibuja_vivo(self):
        try:
            self.delete("vivo")
            w, h = self.winfo_width(), self.winfo_height()
            if w < 60:
                return
            y0 = h - VIVO
            self.create_line(22, y0 - 6, w - 22, y0 - 6, fill=mix(SIDE, MUTED, 0.2), tags="vivo")
            self.create_text(24, y0 + 8, text="●  EN VIVO", anchor="w", fill=self.live_lbl.fg, font=F(8, True), tags="vivo")
            for b in (self.bar_cpu, self.bar_ram):
                y = y0 + 24 + b.fila * 22
                self.create_text(24, y, text=b.nombre, anchor="w", fill=MUTED, font=F(8, True), tags="vivo")
                self.create_text(w - 24, y, text=f"{b.v:.0f}%", anchor="e", fill=FG, font=F(8, True), tags="vivo")
                round_rect(self, 24, y + 9, w - 24, y + 14, 2.5, fill=mix(SIDE, "#ffffff", 0.1), outline="", tags="vivo")
                if b.v > 1:
                    col = GREEN if b.v < 60 else YELLOW if b.v < 85 else RED
                    round_rect(self, 24, y + 9, 24 + max(6, (w - 48) * b.v / 100), y + 14, 2.5, fill=col, outline="", tags="vivo")
        except tk.TclError:
            pass

    # ---- ratón y animación ----
    def _en(self, y):
        for f in self.filas:
            if f[0] == "i":
                fy = self._y(f)
                if fy <= y < fy + PASO and self._visible(fy, PASO):
                    return f[1]
        return None

    def _motion(self, e):
        self._hover(self._en(e.y))

    def _hover(self, ent):
        cambio = False
        for e in self.nav.values():
            g = e is ent
            if e.hgoal != g:
                e.hgoal, cambio = g, True
        self.configure(cursor="hand2" if ent else "")
        if cambio:
            self._anima()

    def _click(self, e):
        ent = self._en(e.y)
        if ent:
            self.on_select(ent.key)

    def _rueda(self, d):
        mo = self._max_off()
        if not mo:
            return
        nuevo = max(0, min(mo, self.off + d * PASO))
        if nuevo != self.off:
            self.off = nuevo
            self._dibuja_todo()

    def _anima(self):
        seguir = False
        for e in self.nav.values():
            gh, ga = float(e.hgoal), float(e.active)
            if not anim.ENABLED:
                e.hov, e.act = gh, ga
            else:
                e.hov += (gh - e.hov) * 0.3
                e.act += (ga - e.act) * 0.25
                if abs(gh - e.hov) < 0.02 and abs(ga - e.act) < 0.02:
                    e.hov, e.act = gh, ga
                else:
                    seguir = True
            if (e.hov, e.act) != getattr(e, "_pint", None):
                e._pint = (e.hov, e.act)
                self._dibuja(e)
        if seguir and self._job is None:
            self._job = self.after(16, self._paso)

    def _paso(self):
        self._job = None
        self._anima()
