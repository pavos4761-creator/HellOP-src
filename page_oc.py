"""Página «Overclock»: guía segura (undervolt y subidas pequeñas) adaptada a TU equipo."""
import tkinter as tk
from tkinter import ttk

import bios
import oc
from util import DEMO
from widgets import (BG, CYAN, F, FG, GREEN, MUTED, PANEL, PINK, RED, VIOLET, YELLOW, Card, NeonButton, ScrollFrame,
                     WrapLabel, page_title)

COL = {"green": GREEN, "red": RED, "yellow": YELLOW, "cyan": CYAN}


class OcPage(tk.Frame):
    def __init__(self, parent, app):
        super().__init__(parent, bg=BG)
        self.app = app
        top = tk.Frame(self, bg=BG)
        top.pack(fill="x", padx=26, pady=(22, 6))
        page_title(top, "Overclock seguro",
                   "Más rendimiento de tu gráfica, procesador y RAM con pasos adaptados a TU equipo, límites seguros y pruebas.",
                   accent=YELLOW).pack(anchor="w")
        row = tk.Frame(top, bg=BG)
        row.pack(fill="x", pady=(14, 4))
        self.btn = NeonButton(row, "⚙   GENERAR MI GUÍA DE OVERCLOCK", self.run, color=YELLOW, filled=True, font=F(14, True), padx=34, pady=12)
        self.btn.pack(side="left")
        self.msg = tk.Label(row, text="", font=F(10), fg=MUTED, bg=BG)
        self.msg.pack(side="left", padx=16)
        self.pb = ttk.Progressbar(top, style="Neon.Horizontal.TProgressbar", mode="indeterminate", length=320)
        self.scroll = ScrollFrame(self)
        self.scroll.pack(fill="both", expand=True, padx=(26, 10), pady=(8, 10))
        intro = Card(self.scroll.inner, accent=YELLOW)
        intro.pack(fill="x")
        WrapLabel(intro.body, fg=MUTED,
                  text="HellOP no cambia nada en este apartado: es una guía de pasos para hacer tú con herramientas gratuitas "
                       "(MSI Afterburner, la BIOS, OCCT). Pulsa el botón y leo tu equipo para darte los pasos exactos de tu procesador, "
                       "tu gráfica y tu RAM, con límites seguros y cómo volver atrás.").pack(fill="x")
        self.body = tk.Frame(self.scroll.inner, bg=BG)
        self.body.pack(fill="x", pady=(10, 0))

    def run(self):
        self.btn.set_enabled(False)
        self.msg.config(text="Leyendo tu equipo…", fg=CYAN)
        self.pb.pack(anchor="w", pady=(6, 0))
        self.pb.start(12)
        cached = self.app.pages["bios"].guide

        def work():
            g = cached or bios.build_guide()
            return g, oc.build(g)

        self.app.bg(work, self.done, self.fail)

    def fail(self, e):
        self.pb.stop()
        self.pb.pack_forget()
        self.btn.set_enabled(True)
        self.msg.config(text=f"No pude leer tu equipo: {e}", fg=RED)

    def done(self, res):
        guide, (summary, sections) = res
        self.app.pages["bios"].guide = guide
        self.pb.stop()
        self.pb.pack_forget()
        self.btn.set_enabled(True)
        self.btn.set_text("↻   GENERAR DE NUEVO")
        self.msg.config(text="Guía lista: " + summary, fg=GREEN)
        for w in self.body.winfo_children():
            w.destroy()
        for label, title, steps, color in sections:
            c = Card(self.body, accent=COL.get(color, CYAN), title=f"{label}  ·  {title}")
            c.pack(fill="x", pady=6)
            for i, s in enumerate(steps, 1):
                row = tk.Frame(c.body, bg=PANEL)
                row.pack(fill="x", pady=2)
                tk.Label(row, text=f"{i}.", font=F(10, True), fg=COL.get(color, CYAN), bg=PANEL, width=3, anchor="ne").pack(side="left", anchor="n")
                WrapLabel(row, text=s, font=F(10), fg=FG).pack(side="left", fill="x", expand=True)
