"""Página «Doctor»: eliges el síntoma y mira tu PC para decirte las causas más probables."""
import time
import tkinter as tk
from tkinter import ttk

import doctor
from widgets import BG, CYAN, F, FG, GREEN, MUTED, PANEL, PINK, RED, YELLOW, Card, NeonButton, ScrollFrame, WrapLabel, badge, page_title

COL = {"bad": RED, "warn": YELLOW, "info": CYAN}
ETIQ = {"bad": "GRAVE", "warn": "REVISAR", "info": "PISTA"}


class DoctorPage(tk.Frame):
    def __init__(self, parent, app):
        super().__init__(parent, bg=BG)
        self.app, self.hechos, self.t_hechos, self.gen = app, None, 0, 0
        self.scroll = ScrollFrame(self)
        self.scroll.pack(fill="both", expand=True, padx=(26, 10), pady=(22, 10))
        self.stage = self.scroll.inner

    def on_show(self):
        self.gen += 1
        self.portada()

    def _limpia(self):
        for w in self.stage.winfo_children():
            w.destroy()
        self.scroll.canvas.yview_moveto(0)

    def portada(self):
        self._limpia()
        page_title(self.stage, "Doctor", "Dime qué te pasa y miro tu PC para decirte por qué. Cada causa sale de un dato real de tu equipo.", accent=PINK).pack(anchor="w", pady=(0, 14))
        grid = tk.Frame(self.stage, bg=BG)
        grid.pack(fill="x")
        for i, (k, ic, t, d) in enumerate(doctor.SINTOMAS):
            c = Card(grid, accent=PINK, pad=14)
            c.grid(row=i // 2, column=i % 2, sticky="nsew", padx=(0, 10), pady=(0, 10))
            grid.grid_columnconfigure(i % 2, weight=1, uniform="s")
            tk.Label(c.body, text=f"{ic}  {t}", font=F(12, True), fg=FG, bg=PANEL, anchor="w").pack(fill="x")
            tk.Label(c.body, text=d, font=F(9), fg=MUTED, bg=PANEL, anchor="w", justify="left", wraplength=300).pack(fill="x", pady=(2, 8))
            NeonButton(c.body, "Diagnosticar", lambda k=k: self.diagnostica(k), color=PINK, padx=14, pady=5, font=F(9, True)).pack(anchor="w")
            for w in (c, c.body):
                w.bind("<Button-1>", lambda e, k=k: self.diagnostica(k))
        tk.Label(self.stage, text="Tarda unos 15 segundos. Solo lee: no cambia nada en tu PC.", font=F(9), fg=MUTED, bg=BG).pack(anchor="w", pady=(4, 0))

    def diagnostica(self, sintoma):
        self.gen += 1
        g = self.gen
        if self.hechos and time.time() - self.t_hechos < 180:
            self.resultado(sintoma)
            return
        self._limpia()
        page_title(self.stage, "Mirando tu PC…", f"Síntoma: {doctor.NOMBRES[sintoma]}", accent=PINK).pack(anchor="w", pady=(0, 12))
        pb = ttk.Progressbar(self.stage, style="Neon.Horizontal.TProgressbar", mode="indeterminate", length=380)
        pb.pack(anchor="w")
        pb.start(12)
        tk.Label(self.stage, text="Temperaturas, latencia de drivers, errores de Windows, memoria y programas de fondo…", font=F(10), fg=MUTED, bg=BG).pack(anchor="w", pady=8)

        def listo(h):
            if g != self.gen:
                return
            self.hechos, self.t_hechos = h, time.time()
            self.resultado(sintoma)
        self.app.bg(doctor.recoger, listo, lambda e: (self.portada(), self.app.toast(f"No pude mirar tu PC: {e}", RED)))

    def resultado(self, sintoma):
        self._limpia()
        page_title(self.stage, doctor.NOMBRES[sintoma], "Esto es lo más probable en tu PC, de más a menos.", accent=PINK).pack(anchor="w", pady=(0, 12))
        lista = doctor.para(sintoma, doctor.causas(self.hechos))
        if not lista:
            c = Card(self.stage, accent=GREEN)
            c.pack(fill="x", pady=(0, 10))
            WrapLabel(c.body, fg=FG, text="No veo nada raro en tu PC para este síntoma. Si pasa solo en un juego, mira sus ajustes de vídeo y verifica sus archivos. "
                                         "Para algo más fino, usa «Diagnóstico» mientras juegas.").pack(fill="x")
        for n, c in enumerate(lista):
            card = Card(self.stage, accent=COL[c["sev"]], pad=14)
            card.pack(fill="x", pady=(0, 10))
            top = tk.Frame(card.body, bg=PANEL)
            top.pack(fill="x")
            tk.Label(top, text=("1.  " if n == 0 else f"{n + 1}.  ") + c["titulo"], font=F(11, True), fg=FG, bg=PANEL, anchor="w", justify="left", wraplength=560).pack(side="left", fill="x", expand=True)
            badge(top, "LO MÁS PROBABLE" if n == 0 else ETIQ[c["sev"]], COL[c["sev"]]).pack(side="right")
            WrapLabel(card.body, text=c["detalle"], fg=MUTED, font=F(10)).pack(fill="x", pady=(6, 0))
            if c["fix"]:
                _g, page, txt = c["fix"]
                NeonButton(card.body, txt, lambda p=page: self.app.show(p), color=COL[c["sev"]], padx=14, pady=5, font=F(9, True)).pack(anchor="w", pady=(8, 0))
        row = tk.Frame(self.stage, bg=BG)
        row.pack(fill="x", pady=10)
        NeonButton(row, "← Otro síntoma", self.portada, color=PINK, padx=16, pady=8).pack(side="left")
        NeonButton(row, "Volver a medir", lambda: (setattr(self, "hechos", None), self.diagnostica(sintoma)), color=CYAN, padx=16, pady=8).pack(side="left", padx=10)
