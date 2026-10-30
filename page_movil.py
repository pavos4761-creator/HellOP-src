"""Página «Monitor en el móvil»."""
import tkinter as tk

import movil
from widgets import BG, CYAN, F, FG, GREEN, MUTED, PANEL, RED, YELLOW, Card, NeonButton, ScrollFrame, WrapLabel, page_title


class MovilPage(tk.Frame):
    def __init__(self, parent, app):
        super().__init__(parent, bg=BG)
        self.app = app
        self.scroll = ScrollFrame(self)
        self.scroll.pack(fill="both", expand=True, padx=(26, 10), pady=(22, 10))
        st = self.scroll.inner
        page_title(st, "Monitor en el móvil", "Mira CPU, gráfica y temperaturas de tu PC en el móvil mientras juegas.", accent=CYAN).pack(anchor="w", pady=(0, 12))
        c = Card(st, accent=CYAN, title="Cómo funciona")
        c.pack(fill="x", pady=(0, 12))
        for t in ("Enciendes el monitor, escaneas el código con la cámara del móvil (o escribes el enlace) y se abre una página con tus datos en vivo.",
                  "Tu móvil y tu PC deben estar en el mismo Wi-Fi. No sale a Internet ni abre nada en tu router.",
                  "Es solo lectura y lleva una clave al azar dentro del enlace; cambia cada vez que lo enciendes. Se apaga al cerrar HellOP.",
                  "Windows te preguntará si permites el acceso: marca «Redes privadas». La conexión no va cifrada, úsalo en tu casa, no en Wi-Fi públicas."):
            WrapLabel(c.body, text="•  " + t, fg=FG, font=F(10)).pack(fill="x", pady=2)
        self.card = Card(st, accent=CYAN, title="Estado")
        self.card.pack(fill="x", pady=(0, 12))
        self.estado = tk.Label(self.card.body, text="Apagado", font=F(12, True), fg=MUTED, bg=PANEL, anchor="w")
        self.estado.pack(fill="x")
        self.link = tk.Label(self.card.body, text="", font=F(10), fg=CYAN, bg=PANEL, anchor="w", justify="left", wraplength=620, cursor="hand2")
        self.link.pack(fill="x", pady=(4, 6))
        self.qr = tk.Canvas(self.card.body, width=1, height=1, bg=PANEL, highlightthickness=0)
        self.qr.pack(anchor="w", pady=(4, 8))
        self.btn = NeonButton(self.card.body, "Encender", self.alterna, color=CYAN, filled=True, padx=22, pady=9)
        self.btn.pack(anchor="w")
        self.link.bind("<Button-1>", self.copia)
        self.after(1500, self._refresca)

    def on_show(self):
        self.pinta()

    def _refresca(self):
        try:
            if movil.encendido():
                self.pinta(solo_estado=True)
            self.after(1500, self._refresca)
        except tk.TclError:
            pass

    def pinta(self, solo_estado=False):
        if movil.encendido():
            if movil.conectado():
                self.estado.config(text="● Encendido · un móvil está mirando", fg=GREEN)
            else:
                self.estado.config(text="● Encendido · esperando a tu móvil", fg=YELLOW)
            if solo_estado:
                return
            url = movil.enlace()
            self.link.config(text=url + "   (pulsa para copiar)")
            self.btn.set_text("Apagar")
            m = movil.matriz_qr(url)
            self.qr.delete("all")
            if m:
                n, px = len(m), 5
                tot = (n + 4) * px
                self.qr.config(width=tot, height=tot)
                self.qr.create_rectangle(0, 0, tot, tot, fill="#ffffff", outline="")
                for y, fila in enumerate(m):
                    for x, v in enumerate(fila):
                        if v:
                            self.qr.create_rectangle((x + 2) * px, (y + 2) * px, (x + 3) * px, (y + 3) * px, fill="#000000", outline="")
            else:
                self.qr.config(width=1, height=1)
        else:
            self.estado.config(text="Apagado", fg=MUTED)
            self.link.config(text="")
            self.qr.delete("all")
            self.qr.config(width=1, height=1)
            self.btn.set_text("Encender")

    def alterna(self):
        try:
            if movil.encendido():
                movil.apagar()
                self.app.toast("Monitor en el móvil apagado", CYAN)
            else:
                movil.encender()
                self.app.toast("Monitor en el móvil encendido", GREEN)
        except OSError as e:
            self.app.toast(str(e), RED)
        self.pinta()

    def copia(self, _e=None):
        u = movil.enlace()
        if u:
            self.clipboard_clear()
            self.clipboard_append(u)
            self.app.toast("Enlace copiado", GREEN)
