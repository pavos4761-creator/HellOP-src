"""Página «Puntuación HellOP»: la nota de tu PC con medalla, lo que te resta puntos y tus logros."""
import math
import tkinter as tk

import puntuacion
from widgets import (BG, CYAN, F, FG, GREEN, MUTED, PANEL, PANEL2, PINK, RED, YELLOW, Card, NeonButton, ScrollFrame, WrapLabel, mix,
                     page_title)


class ScoreRing(tk.Canvas):
    """Anillo que se llena hasta la nota, con la medalla debajo."""

    def __init__(self, parent, size=190):
        super().__init__(parent, width=size, height=size + 30, bg=PANEL, highlightthickness=0, bd=0)
        self.size, self.target, self.shown, self.medal = size, 0, 0.0, ("—", MUTED)
        self._draw()

    def set(self, score, medal):
        self.target, self.medal = score, medal
        self.shown = 0.0
        self._step()

    def _step(self):
        d = self.target - self.shown
        if abs(d) < 0.7:
            self.shown = self.target
            self._draw()
            return
        self.shown += max(0.7, d * 0.12)
        self._draw()
        self.after(25, self._step)

    def _draw(self):
        try:
            self.delete("all")
        except tk.TclError:
            return
        s, pad = self.size, 14
        box = (pad, pad, s - pad, s - pad)
        name, col = self.medal
        self.create_arc(*box, start=90, extent=-359.9, style="arc", outline=PANEL2, width=14)
        if self.shown > 0.5:
            self.create_arc(*box, start=90, extent=-3.599 * self.shown, style="arc", outline=col, width=14)
        self.create_text(s / 2, s / 2 - 6, text=f"{self.shown:.0f}", fill=FG, font=F(int(s / 3.4), True))
        self.create_text(s / 2, s / 2 + s / 5, text="de 100", fill=MUTED, font=F(9))
        self.create_text(s / 2, s + 12, text=name.upper(), fill=col, font=F(13, True))


class ScorePage(tk.Frame):
    def __init__(self, parent, app):
        super().__init__(parent, bg=BG)
        self.app = app
        self.busy = False
        top = tk.Frame(self, bg=BG)
        top.pack(fill="x", padx=26, pady=(22, 6))
        page_title(top, "Puntuación HellOP", "Una nota para tu PC según lo bien configurado que está, con medallas y logros.", accent=YELLOW).pack(anchor="w")
        row = tk.Frame(top, bg=BG)
        row.pack(fill="x", pady=(12, 4))
        self.btn = NeonButton(row, "★   CALCULAR MI PUNTUACIÓN", self.run, color=YELLOW, filled=True, font=F(13, True), padx=30, pady=11)
        self.btn.pack(side="left")
        self.msg = tk.Label(row, text="", font=F(10), fg=MUTED, bg=BG)
        self.msg.pack(side="left", padx=16)
        self.scroll = ScrollFrame(self)
        self.scroll.pack(fill="both", expand=True, padx=(26, 10), pady=(8, 10))
        self.body = self.scroll.inner
        c = Card(self.body, accent=MUTED, title="Qué mide (y qué no)")
        c.pack(fill="x")
        for t in ("Mide lo bien configurado que está tu PC: monitor a sus Hz, RAM en dual y con su perfil, juegos en SSD, plan de energía, "
                  "programas de inicio, espacio libre y programas de fondo.",
                  "NO mide la potencia de tu equipo: un PC modesto bien ajustado puede sacar más nota que uno caro mal configurado.",
                  "Cada punto que pierdes tiene su arreglo a un clic."):
            WrapLabel(c.body, text="•  " + t, font=F(9), fg=MUTED).pack(fill="x", pady=1)
        self.res = tk.Frame(self.body, bg=BG)
        self.res.pack(fill="x", pady=(12, 0))
        self._loaded = False

    def on_show(self):
        if not self._loaded:
            self._loaded = True
            self.run()

    def run(self):
        if self.busy:
            return
        self.busy = True
        self.btn.set_enabled(False)
        self.msg.config(text="Calculando…", fg=YELLOW)
        self.app.bg(lambda: puntuacion.calcular(lambda s: self.app.ui(lambda: self.msg.config(text=s, fg=YELLOW))), self._done, self._fail)

    def _fail(self, e):
        self.busy = False
        self.btn.set_enabled(True)
        self.msg.config(text=f"Error: {e}", fg=RED)

    def _done(self, r):
        self.busy = False
        self.btn.set_enabled(True)
        self.msg.config(text="✓ Listo", fg=GREEN)
        for w in self.res.winfo_children():
            w.destroy()
        name, col = r["medal"]
        c = Card(self.res, accent=col)
        c.pack(fill="x", pady=(0, 12))
        line = tk.Frame(c.body, bg=PANEL)
        line.pack(fill="x")
        ring = ScoreRing(line)
        ring.pack(side="left", padx=(0, 24))
        ring.set(r["score"], r["medal"])
        side = tk.Frame(line, bg=PANEL)
        side.pack(side="left", fill="x", expand=True)
        tk.Label(side, text="Lo que te resta puntos" if r["perdidos"] else "¡Tu PC está al máximo!", font=F(12, True), fg=FG, bg=PANEL,
                 anchor="w").pack(fill="x", pady=(0, 6))
        if not r["perdidos"]:
            WrapLabel(side, text="No encuentro nada que mejorar en lo que mido. Buen trabajo.", font=F(10), fg=GREEN).pack(fill="x")
        for title, pts, fix in r["perdidos"][:6]:
            rr = tk.Frame(side, bg=PANEL)
            rr.pack(fill="x", pady=2)
            tk.Label(rr, text=f"−{pts}", font=F(11, True), fg=RED, bg=PANEL, width=4, anchor="w").pack(side="left")
            WrapLabel(rr, text=title, font=F(10), fg=FG).pack(side="left", fill="x", expand=True)
            if fix and fix[0] == "goto":
                NeonButton(rr, fix[2], lambda k=fix[1]: self.app.show(k), color=CYAN, padx=10, pady=3, font=F(9, True)).pack(side="right")
        lg = Card(self.res, accent=PINK, title=f"Logros  ({sum(1 for x in r['logros'] if x['date'])}/{len(r['logros'])})")
        lg.pack(fill="x", pady=(0, 12))
        for x in r["logros"]:
            on = bool(x["date"])
            rr = tk.Frame(lg.body, bg=PANEL)
            rr.pack(fill="x", pady=2)
            tk.Label(rr, text="★" if on else "☆", font=F(14, True), fg=YELLOW if on else MUTED, bg=PANEL, width=2).pack(side="left")
            tk.Label(rr, text=x["title"], font=F(10, True), fg=FG if on else MUTED, bg=PANEL, width=18, anchor="w").pack(side="left")
            tk.Label(rr, text=x["desc"] + (f"   ({x['date']})" if on else ""), font=F(9), fg=MUTED, bg=PANEL, anchor="w").pack(side="left")
            if x["id"] in r["nuevos"]:
                tk.Label(rr, text="  ¡NUEVO!", font=F(8, True), fg=GREEN, bg=PANEL).pack(side="left")
