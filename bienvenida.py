"""Pantalla «Bienvenido a Pro»: animación morada que sale al activar una clave, en el idioma de Windows.

Solo se traduce este mensaje (no toda la app). Si el idioma no está en la lista (o es de los que Tk no dibuja bien:
árabe, hebreo, hindi, tailandés) sale en inglés.
"""
import math
import os
import random
import time
import tkinter as tk
import tkinter.font as tkfont

from util import IS_WIN
from widgets import F, mix

# código de idioma -> (título, subtítulo)
TEXTOS = {
    "es": ("Bienvenido a Pro", "Todas las funciones están desbloqueadas"),
    "en": ("Welcome to Pro", "All features are unlocked"),
    "ru": ("Добро пожаловать в Pro", "Все функции разблокированы"),
    "uk": ("Ласкаво просимо до Pro", "Усі функції розблоковано"),
    "pt": ("Bem-vindo ao Pro", "Todas as funções estão desbloqueadas"),
    "fr": ("Bienvenue dans Pro", "Toutes les fonctions sont débloquées"),
    "de": ("Willkommen bei Pro", "Alle Funktionen sind freigeschaltet"),
    "it": ("Benvenuto in Pro", "Tutte le funzioni sono sbloccate"),
    "nl": ("Welkom bij Pro", "Alle functies zijn ontgrendeld"),
    "pl": ("Witamy w Pro", "Wszystkie funkcje są odblokowane"),
    "tr": ("Pro'ya hoş geldin", "Tüm özellikler açıldı"),
    "cs": ("Vítejte v Pro", "Všechny funkce jsou odemčeny"),
    "ro": ("Bun venit în Pro", "Toate funcțiile sunt deblocate"),
    "sv": ("Välkommen till Pro", "Alla funktioner är upplåsta"),
    "da": ("Velkommen til Pro", "Alle funktioner er låst op"),
    "no": ("Velkommen til Pro", "Alle funksjoner er låst opp"),
    "fi": ("Tervetuloa Pro-versioon", "Kaikki ominaisuudet on avattu"),
    "hu": ("Üdvözlünk a Pro-ban", "Minden funkció feloldva"),
    "el": ("Καλώς ήρθες στο Pro", "Όλες οι λειτουργίες είναι ξεκλειδωμένες"),
    "id": ("Selamat datang di Pro", "Semua fitur telah terbuka"),
    "vi": ("Chào mừng đến với Pro", "Tất cả tính năng đã được mở khóa"),
    "zh": ("欢迎使用 Pro", "所有功能已解锁"),
    "ja": ("Pro へようこそ", "すべての機能が解除されました"),
    "ko": ("Pro에 오신 것을 환영합니다", "모든 기능이 잠금 해제되었습니다"),
}
# identificador de idioma de Windows (los 10 bits bajos del LANGID) -> código
_LANGID = {0x0a: "es", 0x09: "en", 0x19: "ru", 0x22: "uk", 0x16: "pt", 0x0c: "fr", 0x07: "de", 0x10: "it", 0x13: "nl",
           0x15: "pl", 0x1f: "tr", 0x05: "cs", 0x18: "ro", 0x1d: "sv", 0x06: "da", 0x14: "no", 0x7c: "no", 0x0b: "fi",
           0x0e: "hu", 0x08: "el", 0x21: "id", 0x2a: "vi", 0x04: "zh", 0x11: "ja", 0x12: "ko"}


def idioma():
    """Código de idioma de Windows de la persona (HELLOP_LANG lo fuerza, para pruebas)."""
    forzado = os.environ.get("HELLOP_LANG", "").strip().lower()[:2]
    if forzado:
        return forzado
    try:
        if IS_WIN:
            import ctypes
            return _LANGID.get(ctypes.windll.kernel32.GetUserDefaultUILanguage() & 0x3FF, "en")
        import locale
        return (locale.getlocale()[0] or "en")[:2].lower()
    except Exception:  # noqa: BLE001
        return "en"


def textos():
    return TEXTOS.get(idioma(), TEXTOS["en"])


# Colores propios (la app sigue en verde mientras suena la animación)
import widgets

NEGRO, PUR, MAG, IND, BLANCO, VERDE = "#07030f", "#a855f7", "#e879f9", "#7c5cff", "#ffffff", "#19e68c"
if widgets.PRO_THEME:     # si ya eres PRO, la animación usa el color que elegiste
    NEGRO, PUR, MAG, IND = widgets.BG, widgets.CYAN, widgets.PINK, widgets.VIOLET
PURO = mix(NEGRO, PUR, 0.28)          # color oscuro del interior de la onda
DURACION = 8.0
LANZAR = 1.0          # a los 1,0 s se empieza a abrir en segundo plano la app morada


def _ease(t):
    t = max(0.0, min(1.0, t))
    return 1 - (1 - t) ** 3


class Bienvenida(tk.Canvas):
    """Explosión que tiñe la pantalla de verde a morado poco a poco, el fondo se difumina y aparece «Bienvenido a PRO»."""

    def __init__(self, parent, logo, on_done, bg0="#000000", on_launch=None):
        super().__init__(parent, bg=bg0, highlightthickness=0, bd=0)
        self.place(x=0, y=0, relwidth=1, relheight=1)
        tk.Misc.lift(self)
        self.on_done, self.bg0, self.on_launch, self._launched = on_done, bg0, on_launch, False
        self.t0, self.done, self.parts = time.time(), False, []
        self.titulo = textos()[0].replace("Pro", "PRO")
        self._burst = False
        self.bind("<Button-1>", lambda e: self._skip())
        self.after(16, self._tick)

    def _skip(self):
        if time.time() - self.t0 > 1.5 and not self.done:
            self.t0 = min(self.t0, time.time() - (DURACION - 1.2))

    def _nacer(self, cx, cy):
        for _ in range(150):
            a, v = random.uniform(0, 6.283), random.uniform(3.0, 14.0)
            self.parts.append([cx, cy, math.cos(a) * v, math.sin(a) * v, random.uniform(1.2, 3.6), random.uniform(0.8, 1.8),
                               random.choice((PUR, MAG, IND, BLANCO, MAG, PUR))])

    def _tick(self):
        if self.done:
            return
        try:
            t = time.time() - self.t0
            w, h = self.winfo_width(), self.winfo_height()
            if w < 50 or h < 50:
                self.after(16, self._tick)
                return
            cx, cy = w / 2, h / 2
            fo = max(0.0, min(1.0, (t - (DURACION - 0.5)) / 0.5))        # al final se funde con el fondo de la app morada

            def m(a, b, x):
                return mix(mix(a, b, x), NEGRO, fo)
            if not self._launched and t >= LANZAR:
                self._launched = True
                if self.on_launch:
                    self.on_launch()
            if not self._burst and t > 0.35:
                self._burst = True
                self._nacer(cx, cy)
            self.delete("all")
            base = mix(self.bg0, VERDE, 0.14)                                 # el verde de la app gratis
            self.create_rectangle(0, 0, w, h, fill=m(base, base, 0), outline="")
            maxr = math.hypot(w, h) / 2 * 1.15
            # --- la explosión: un círculo morado que crece desde el centro, con borde difuminado ---
            p = (t - 0.35) / 2.7
            dif = _ease((t - 2.4) / 1.2)                                 # después, el fondo se difumina y se oscurece
            inner = mix(PURO, NEGRO, dif)
            if t < 0.5:                                                   # destello de la chispa inicial
                r = 10 + 90 * _ease(t / 0.5)
                self.create_oval(cx - r, cy - r, cx + r, cy + r, fill=m(base, MAG, 1 - t / 0.5 * 0.4), outline="")
            if p > 0:
                R = _ease(p) * maxr
                for j in range(14):                                       # borde suave: del verde al morado
                    r = R + (14 - j) * 9
                    self.create_oval(cx - r, cy - r, cx + r, cy + r, fill=m(base, inner, (j + 1) / 15), outline="")
                self.create_oval(cx - R, cy - R, cx + R, cy + R, fill=m(inner, inner, 0), outline="")
                if p < 1:
                    for k, (c, wd) in enumerate(((MAG, 4), (PUR, 2), (VERDE, 1))):
                        r = R + k * 5
                        self.create_oval(cx - r, cy - r, cx + r, cy + r, outline=m(base, c, 0.9 - 0.2 * p), width=wd)
                # brillo interior que se va apagando hacia el centro
                for j in range(8):
                    r = R * (0.2 + 0.1 * j)
                    self.create_oval(cx - r, cy - r, cx + r, cy + r, outline=m(inner, PUR, 0.16 * (1 - dif) * (1 - j / 8)))
            # chispas
            for q in self.parts:
                q[0] += q[2]
                q[1] += q[3]
                q[2] *= 0.96
                q[3] = q[3] * 0.96 + 0.05
                q[5] -= 0.011
                if q[5] <= 0:
                    continue
                vida, r = min(1.0, q[5]), q[4] * (0.5 + 0.5 * min(1.0, q[5]))
                self.create_oval(q[0] - r, q[1] - r, q[0] + r, q[1] + r, fill=m(inner, q[6], vida), outline="")
            self.parts = [q for q in self.parts if q[5] > 0]
            # el mensaje, letra a letra, con brillo que lo recorre y puntos que giran
            if t > 2.9:
                fnt = tkfont.Font(font=F(40, True))
                total = fnt.measure(self.titulo)
                x0 = cx - total / 2
                pro_i = self.titulo.find("PRO")
                if t > 3.2:                                               # halo que respira detrás del texto
                    ha = _ease((t - 3.2) / 1.2)
                    for i in range(6):
                        rx, ry = total / 2 + 30 + i * 16 + 6 * math.sin(t * 2), 46 + i * 11
                        self.create_oval(cx - rx, cy - ry, cx + rx, cy + ry, outline=m(inner, PUR, ha * max(0.0, 0.34 - 0.05 * i)))
                ciclo = (t - 4.6) % 2.6
                sx = x0 - 80 + (ciclo / 1.1) * (total + 160) if t > 4.6 and ciclo < 1.1 else -9999
                for i, ch in enumerate(self.titulo):
                    if ch == " ":
                        continue
                    ai = _ease((t - 3.0 - i * 0.045) / 0.55)
                    if ai <= 0:
                        continue
                    x = x0 + fnt.measure(self.titulo[:i])
                    es_pro = pro_i >= 0 and pro_i <= i < pro_i + 3
                    col = m(inner, mix(MAG, BLANCO, 0.25) if es_pro else BLANCO, ai)
                    k = max(0.0, 1 - abs(x + 14 - sx) / 80)
                    if k > 0:
                        col = m(inner, "#f5d0fe", min(1.0, ai) * (0.55 + 0.45 * k)) if k > 0.05 else col
                    self.create_text(x, cy + 22 * (1 - ai), anchor="w", text=ch, fill=col, font=F(40, True))
                a3 = _ease((t - 4.2) / 0.9)
                if a3 > 0:                                                # línea con degradado que se abre desde el centro
                    ancho = (total / 2 + 20) * a3
                    for i in range(48):
                        xa = cx - ancho + 2 * ancho * i / 48
                        c = mix(IND, MAG, i / 23) if i < 24 else mix(MAG, IND, (i - 24) / 23)
                        self.create_rectangle(xa, cy + 52, xa + 2 * ancho / 48 + 1, cy + 56, fill=m(inner, c, a3), outline="")
                if t > 5.0:                                               # tres puntos que giran
                    la = _ease((t - 5.0) / 0.6)
                    for d in range(3):
                        ang = t * 4.2 + d * 2.094
                        px, py = cx + 15 * math.cos(ang), cy + 92 + 15 * math.sin(ang)
                        self.create_oval(px - 3.2, py - 3.2, px + 3.2, py + 3.2, fill=m(inner, (PUR, MAG, IND)[d], la), outline="")
                if t > 3.4 and random.random() < 0.5:                     # chispas que suben desde el texto
                    self.parts.append([cx + random.uniform(-total / 2, total / 2), cy + 20, random.uniform(-0.3, 0.3), random.uniform(-2.2, -0.8),
                                       random.uniform(1.2, 2.6), random.uniform(0.9, 1.6), random.choice((PUR, MAG, BLANCO))])
            if t >= DURACION:
                self.done = True
                self.on_done()
                return
            self.after(16, self._tick)
        except tk.TclError:
            self.done = True
