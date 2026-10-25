"""Página «Qué pieza mejorar»: te dice qué te frena y si te compensa gastar dinero."""
import threading
import time
import tkinter as tk
from tkinter import messagebox, ttk

import cuello
import fps
from util import DEMO
from widgets import (BG, CYAN, F, FG, GREEN, MUTED, PANEL, PANEL2, BORDER, PINK, RED, YELLOW, Card, NeonButton, ScrollFrame, WrapLabel,
                     kv_rows, page_title)

COL = {"green": GREEN, "yellow": YELLOW, "red": RED, "cyan": CYAN}
PRIO_COL = {0: RED, 1: YELLOW, 2: CYAN, 3: GREEN}


class CuelloPage(tk.Frame):
    def __init__(self, parent, app):
        super().__init__(parent, bg=BG)
        self.app = app
        self.busy = False
        self.stop = None
        self.m = None
        top = tk.Frame(self, bg=BG)
        top.pack(fill="x", padx=26, pady=(22, 6))
        page_title(top, "Qué pieza mejorar", "Detecta qué te frena de verdad y te dice si te compensa gastar dinero (o no).", accent=PINK).pack(anchor="w")
        self.scroll = ScrollFrame(self)
        self.scroll.pack(fill="both", expand=True, padx=(26, 10), pady=(8, 10))
        root = self.scroll.inner
        c = Card(root, accent=YELLOW, title="Cómo funciona")
        c.pack(fill="x", pady=(0, 12))
        for t in ("Primero miro tu RAM, tus discos y dónde están tus juegos. Eso lo sé sin medir nada.",
                  "Para saber si limita la GRÁFICA o el PROCESADOR hay que medir un juego (30 s con PresentMon). Sin medir no adivino.",
                  "Te digo qué hacer primero y qué NO comprar. Si tu PC no tiene un cuello claro, te lo digo: ahorrarás dinero.",
                  "Es una guía basada en tus datos, no una garantía: cada juego se comporta distinto."):
            WrapLabel(c.body, text="•  " + t, font=F(9), fg=MUTED).pack(fill="x", pady=1)
        sel = Card(root, accent=CYAN, title="Juego a medir (opcional, pero es lo que da la respuesta más útil)")
        sel.pack(fill="x", pady=(0, 12))
        row = tk.Frame(sel.body, bg=PANEL)
        row.pack(fill="x")
        self.var = tk.StringVar(value=fps.KNOWN_GAMES[0])
        tk.Entry(row, textvariable=self.var, font=("Consolas", 11), bg=PANEL2, fg=FG, insertbackground=FG, relief="flat",
                 highlightthickness=1, highlightbackground=BORDER, highlightcolor=CYAN, width=38).pack(side="left", ipady=6, padx=(0, 10))
        NeonButton(row, "↻  Juegos abiertos", self.refresh_candidates, color=CYAN, padx=14, pady=6, font=F(10, True)).pack(side="left")
        self.chips = tk.Frame(sel.body, bg=PANEL)
        self.chips.pack(fill="x", pady=(8, 0))
        bar = tk.Frame(root, bg=BG)
        bar.pack(fill="x", pady=(0, 8))
        self.b_an = NeonButton(bar, "◎  ANALIZAR SIN MEDIR", lambda: self.analyze(False), color=PINK, filled=True, font=F(11, True), padx=20, pady=8)
        self.b_an.pack(side="left")
        self.b_me = NeonButton(bar, "▶  MEDIR UN JUEGO (30 s) Y ANALIZAR", lambda: self.analyze(True), color=GREEN, font=F(11, True), padx=20, pady=8)
        self.b_me.pack(side="left", padx=10)
        self.msg = tk.Label(bar, text="", font=F(10), fg=MUTED, bg=BG)
        self.msg.pack(side="left", padx=10)
        self.pb = ttk.Progressbar(root, style="Neon.Horizontal.TProgressbar", mode="determinate", maximum=100, length=420)
        self.body = tk.Frame(root, bg=BG)
        self.body.pack(fill="x")

    def on_show(self):
        self.refresh_candidates()

    def refresh_candidates(self):
        for w in self.chips.winfo_children():
            w.destroy()
        names = fps.running_candidates()
        if names and names[0] in fps.KNOWN_GAMES:
            self.var.set(names[0])
        for n in names[:6]:
            NeonButton(self.chips, n, lambda n_=n: self.var.set(n_), color=GREEN if n in fps.KNOWN_GAMES else MUTED, padx=10, pady=4,
                       font=F(9, True)).pack(side="left", padx=(0, 6), pady=2)

    # ------------------------------------------------------------------
    def _prog(self, p, m):
        self.pb["value"] = int(p * 100)
        self.msg.config(text=m, fg=CYAN)

    def _end(self):
        self.busy, self.stop = False, None
        self.pb.pack_forget()
        self.b_an.set_enabled(True)
        self.b_me.set_text("▶  MEDIR UN JUEGO (30 s) Y ANALIZAR")
        self.b_me.set_enabled(True)

    def _fail(self, e):
        self._end()
        self.msg.config(text=("✗ " + str(e)) if isinstance(e, fps.FpsError) else f"✗ Error: {type(e).__name__}: {e}", fg=RED)

    def analyze(self, measure):
        if self.busy:
            if self.stop:
                self.stop.set()
            return
        proc = self.var.get().strip()
        if measure:
            if not proc.lower().endswith(".exe"):
                self.msg.config(text="Escribe el programa del juego, por ejemplo VALORANT-Win64-Shipping.exe", fg=YELLOW)
                return
            if not DEMO and not fps.have_presentmon() and not messagebox.askyesno(
                    "Descargar PresentMon", "Para medir hace falta PresentMon, una herramienta gratuita de Intel (≈1 MB).\n\n"
                    "Se descarga una sola vez y se comprueba su huella SHA256.\n\n¿Descargarla ahora?"):
                return
        self.busy, self.stop = True, threading.Event()
        self.b_an.set_enabled(False)
        if measure:
            self.b_me.set_text("■  Cancelar")
        else:
            self.b_me.set_enabled(False)
        self.pb["value"] = 0
        self.pb.pack(anchor="w", pady=(0, 6), before=self.body)
        stop = self.stop

        def work():
            m = None
            if measure:
                fps.ensure_presentmon()
                for i in range(5, 0, -1):
                    if stop.is_set():
                        raise fps.FpsError("Medición cancelada")
                    self.app.ui(self._prog, 0, f"Vuelve al juego (Alt+Tab): empiezo en {i}…")
                    time.sleep(1)
                ft, g, c = fps.capture(proc, 30, lambda p, msg: self.app.ui(self._prog, p, msg), stop, 0)
                m = fps.analyze(ft, g, c)
            return cuello.run(m, lambda s: self.app.ui(self._prog, 0, s)), m

        self.app.bg(work, self._done, self._fail)

    def _done(self, res):
        self._end()
        (txt, col), items, specs = res[0]
        self.m = res[1]
        self.msg.config(text="✓ Listo", fg=GREEN)
        for w in self.body.winfo_children():
            w.destroy()
        c = Card(self.body, accent=COL[col], title="Mi conclusión")
        c.pack(fill="x", pady=(0, 12))
        WrapLabel(c.body, text=txt, font=F(12, True), fg=COL[col]).pack(fill="x")
        kv_rows(c.body, specs + ([("Medido", f"{self.m['avg']:.0f} FPS medios · 1 % low {self.m['low1']:.0f} · gráfica al {self.m.get('gpu_pct', '?')} %")]
                                 if self.m else []), key_width=14)
        for it in items:
            col = PRIO_COL[it["prio"]]
            card = Card(self.body, accent=col)
            card.pack(fill="x", pady=(0, 8))
            head = tk.Frame(card.body, bg=PANEL)
            head.pack(fill="x")
            tk.Label(head, text=it["part"].upper(), font=F(8, True), fg=MUTED, bg=PANEL).pack(side="left")
            tk.Label(head, text="   " + cuello.PRIO_TXT[it["prio"]], font=F(8, True), fg=col, bg=PANEL).pack(side="left")
            if it["cost"]:
                tk.Label(head, text="   coste: " + it["cost"], font=F(8), fg=MUTED, bg=PANEL).pack(side="left")
            tk.Label(card.body, text=it["title"], font=F(11, True), fg=FG, bg=PANEL, anchor="w").pack(fill="x", pady=(2, 2))
            WrapLabel(card.body, text=it["why"], font=F(9), fg=MUTED).pack(fill="x")
