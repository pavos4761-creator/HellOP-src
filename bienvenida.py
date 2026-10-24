"""Pantalla «Bienvenido a Pro»: animación morada que sale al activar una clave, en el idioma de Windows.

Solo se traduce este mensaje (no toda la app). Si el idioma no está en la lista (o es de los que Tk no dibuja bien:
árabe, hebreo, hindi, tailandés) sale en inglés.
"""
import math
import os
import random
import time
import tkinter as tk

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


# Colores propios (la app puede seguir en verde mientras suena la animación)
NEGRO, PUR, MAG, IND, BLANCO, SUAVE = "#07030f", "#a855f7", "#e879f9", "#7c5cff", "#ffffff", "#c7b2ee"
DURACION = 5.6


def _ease(t):
    t = max(0.0, min(1.0, t))
    return 1 - (1 - t) ** 3


class Bienvenida(tk.Canvas):
    """Capa a pantalla completa: ondas, chispas, logo morado y el mensaje que aparece con un fundido."""

    def __init__(self, parent, logo, on_done, bg0="#000000"):
        super().__init__(parent, bg=NEGRO, highlightthickness=0, bd=0)
        self.place(x=0, y=0, relwidth=1, relheight=1)
        tk.Misc.lift(self)
        self.logo, self.on_done, self.bg0 = logo, on_done, bg0
        self.t0, self.done, self.parts = time.time(), False, []
        self.titulo, self.sub = textos()
        self._burst = False
        self.bind("<Button-1>", lambda e: self._skip())
        self.after(16, self._tick)

    def _skip(self):
        if time.time() - self.t0 > 1.6 and not self.done:
            self.t0 -= DURACION          # salta directo al final

    def _nacer(self, w, h):
        cx, cy = w / 2, h * 0.40
        for _ in range(130):
            a, v = random.uniform(0, 6.283), random.uniform(2.0, 11.0)
            self.parts.append([cx, cy, math.cos(a) * v, math.sin(a) * v, random.uniform(1.2, 3.8), random.uniform(0.9, 1.9),
                               random.choice((PUR, MAG, IND, BLANCO, MAG, PUR)), random.uniform(0, 6.28)])
        for _ in range(45):                                       # polvo que sube durante toda la escena
            self.parts.append([random.uniform(0, w), random.uniform(0, h), 0, -random.uniform(0.25, 0.9),
                               random.uniform(1, 2.4), 99, random.choice((PUR, IND, MAG)), random.uniform(0, 6.28)])

    def _tick(self):
        if self.done:
            return
        try:
            t = time.time() - self.t0
            w, h = self.winfo_width(), self.winfo_height()
            if w < 50 or h < 50:
                self.after(16, self._tick)
                return
            if not self._burst and t > 0.25:
                self._burst = True
                self._nacer(w, h)
            fo = max(0.0, min(1.0, (t - (DURACION - 0.7)) / 0.7))      # fundido a negro al final

            def m(a, b, x):
                return mix(mix(a, b, x), "#000000", fo)
            self.delete("all")
            cx, cy = w / 2, h * 0.40
            fondo = m(self.bg0, NEGRO, _ease(t / 0.6))
            self.create_rectangle(0, 0, w, h, fill=fondo, outline="")
            # ondas de luz que salen del centro
            for k in range(4):
                p = (t - 0.25 - k * 0.22) / 1.8
                if 0 < p < 1:
                    r = _ease(p) * max(w, h) * 0.75
                    self.create_oval(cx - r, cy - r, cx + r, cy + r, outline=m(fondo, PUR if k % 2 else MAG, (1 - p) * 0.9),
                                     width=max(1, int(5 * (1 - p))))
            # resplandor que respira detrás del logo
            if t > 0.4:
                a = _ease((t - 0.4) / 0.8)
                for i in range(7):
                    r = 56 + i * 12 + 6 * math.sin(t * 2.2)
                    self.create_oval(cx - r, cy - r, cx + r, cy + r, outline=m(fondo, PUR, a * max(0.0, 0.5 - 0.07 * i)))
            # chispas
            for q in self.parts:
                q[0] += q[2]
                q[1] += q[3]
                if q[5] != 99:                                       # las del estallido frenan y caen un poco
                    q[2] *= 0.965
                    q[3] = q[3] * 0.965 + 0.06
                    q[5] -= 0.012
                    vida = max(0.0, min(1.0, q[5]))
                else:
                    vida = 0.35 + 0.65 * (0.5 + 0.5 * math.sin(t * 2 + q[7]))
                    if q[1] < -4:
                        q[1] = h + 4
                if vida <= 0:
                    continue
                r = q[4] * (0.5 + 0.5 * vida)
                self.create_oval(q[0] - r, q[1] - r, q[0] + r, q[1] + r, fill=m(fondo, q[6], vida), outline="")
            self.parts = [q for q in self.parts if q[5] == 99 or q[5] > 0]
            if self.logo is not None and t > 0.5:
                self.create_image(cx, cy - 6 * (1 - _ease((t - 0.5) / 0.9)) * 6, image=self.logo)
            # título y subtítulo
            ty = h * 0.40 + 118
            a1 = _ease((t - 1.0) / 0.9)
            if a1 > 0:
                self.create_text(cx, ty + 22 * (1 - a1), text=self.titulo, fill=m(fondo, BLANCO, a1), font=F(40, True))
            a2 = _ease((t - 1.9) / 0.8)
            if a2 > 0:
                self.create_text(cx, ty + 62, text=self.sub, fill=m(fondo, SUAVE, a2), font=F(14))
            a3 = _ease((t - 1.5) / 1.0)
            if a3 > 0:                                              # barra con degradado que se abre desde el centro
                ancho = 320 * a3
                for i in range(40):
                    x0 = cx - ancho + (2 * ancho) * i / 40
                    c = m(IND, MAG, i / 39) if i < 20 else m(MAG, IND, (i - 20) / 19)
                    self.create_rectangle(x0, ty + 92, x0 + (2 * ancho) / 40 + 1, ty + 96, fill=m(fondo, c, a3), outline="")
            if t >= DURACION:
                self.done = True
                self.on_done()
                return
            self.after(16, self._tick)
        except tk.TclError:
            self.done = True
