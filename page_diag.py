"""Página «Diagnóstico»: mide mientras juegas y te dice qué te frena y qué causa los tirones."""
import threading
import tkinter as tk
from tkinter import ttk

import bios
import diag
from util import DEMO
from widgets import (BG, CYAN, F, FG, GREEN, MUTED, PANEL, PANEL2, PINK, RED, VIOLET, YELLOW, Card, NeonButton,
                     ScrollFrame, WrapLabel, badge, kv_rows, page_title)

LEVEL = {"mal": ("PROBLEMA", RED), "ojo": ("OJO", YELLOW), "bien": ("BIEN", GREEN), "info": ("INFO", CYAN)}
COUNTDOWN = 10


class DiagPage(tk.Frame):
    def __init__(self, parent, app):
        super().__init__(parent, bg=BG)
        self.app = app
        self.secs = 30
        self.busy = False
        top = tk.Frame(self, bg=BG)
        top.pack(fill="x", padx=26, pady=(22, 6))
        page_title(top, "Diagnóstico de juego",
                   "Mide tu PC mientras juegas y te dice si te frena la CPU, la gráfica, la RAM, el disco o el calor, y qué causa los tirones.",
                   accent=PINK).pack(anchor="w")
        self.scroll = ScrollFrame(self)
        self.scroll.pack(fill="both", expand=True, padx=(26, 10), pady=(8, 10))
        root = self.scroll.inner

        how = Card(root, accent=PINK, title="Cómo se usa (3 pasos)")
        how.pack(fill="x", pady=(0, 12))
        for t in ("1.  Pulsa «Empezar medición». Tienes 10 segundos de cuenta atrás.",
                  "2.  Vuelve a tu juego (Alt+Tab) y juega con normalidad, mejor en una zona exigente.",
                  "3.  Cuando termine, vuelve a HellOP y lee el resultado. No cambia ningún ajuste: solo mide y te aconseja."):
            WrapLabel(how.body, text=t, font=F(10), fg=FG).pack(fill="x", pady=1)

        ctl = Card(root, accent=CYAN, title="Medición")
        ctl.pack(fill="x", pady=(0, 12))
        row = tk.Frame(ctl.body, bg=PANEL)
        row.pack(fill="x")
        tk.Label(row, text="Duración:", font=F(10, True), fg=MUTED, bg=PANEL).pack(side="left", padx=(0, 10))
        self.dur = {}
        for s in (20, 30, 60):
            b = NeonButton(row, f"{s} s", lambda v=s: self.set_secs(v), color=CYAN if s == self.secs else MUTED, padx=14, pady=6,
                           font=F(10, True))
            b.pack(side="left", padx=3)
            self.dur[s] = b
        self.btn = NeonButton(ctl.body, "▶   EMPEZAR MEDICIÓN", self.start, color=PINK, filled=True, font=F(14, True), padx=34, pady=12)
        self.btn.pack(anchor="w", pady=(14, 0))
        self.msg = tk.Label(ctl.body, text="", font=F(11, True), fg=MUTED, bg=PANEL, anchor="w", justify="left", wraplength=760)
        self.msg.pack(fill="x", pady=(10, 0))
        self.pb = ttk.Progressbar(ctl.body, style="Pink.Horizontal.TProgressbar", mode="determinate", maximum=100)

        self.results = tk.Frame(root, bg=BG)
        self.results.pack(fill="x")

    # ------------------------------------------------------------------
    def set_secs(self, v):
        if self.busy:
            return
        self.secs = v
        for s, b in self.dur.items():
            b.set_color(CYAN if s == v else MUTED)

    def say(self, text, color=MUTED):
        self.msg.config(text=text, fg=color)

    def start(self):
        if self.busy:
            return
        self.busy = True
        self.btn.set_enabled(False)
        for w in self.results.winfo_children():
            w.destroy()
        self.pb["value"] = 0
        self._count(0 if DEMO else COUNTDOWN)

    def _count(self, n):
        if n > 0:
            self.say(f"Vuelve a tu juego ahora (Alt+Tab). Empiezo a medir en {n} s…", YELLOW)
            self.after(1000, lambda: self._count(n - 1))
            return
        self.pb.pack(fill="x", pady=(8, 0))
        self.say("Midiendo… juega con normalidad.", CYAN)
        secs = self.secs
        self.app.bg(lambda: diag.measure(secs, lambda p, t: self.app.ui(self._prog, p, t)), self.measured, self.failed)

    def _prog(self, p, t):
        self.pb["value"] = p
        self.say(t, CYAN)

    def failed(self, e):
        self.busy = False
        self.pb.pack_forget()
        self.btn.set_enabled(True)
        self.say(f"No pude completar la medición: {e}", RED)

    def measured(self, m):
        self.pb.pack_forget()
        self.say("Analizando resultados y revisando causas de tirones…", CYAN)
        self.app.bg(lambda: self._analyze(m), self.show_result, self.failed)

    def _analyze(self, m):
        res = diag.analyze(m)
        guide = self.app.pages["bios"].guide
        ram = None
        try:
            if guide is None and not DEMO:
                guide = bios.build_guide()
                self.app.pages["bios"].guide = guide
            if guide and guide.get("ram"):
                ram = {"running": guide["ram"].get("running"), "kit": guide["ram"].get("target")}
        except Exception:  # noqa: BLE001
            ram = None
        res["checks"] = diag.static_checks(ram)
        res["prev"] = diag.load_history()
        diag.save_run(res["kpi"])
        return res

    # ------------------------------------------------------------------
    def show_result(self, r):
        self.busy = False
        self.btn.set_enabled(True)
        self.btn.set_text("↻   MEDIR OTRA VEZ")
        self.say("Listo. Aquí tienes el resultado.", GREEN)
        root = self.results
        col = {"bien": GREEN, "mal": RED, "ojo": YELLOW}.get(r["color"], CYAN)

        v = Card(root, accent=col)
        v.pack(fill="x", pady=(0, 12))
        tk.Label(v.body, text="CUELLO DE BOTELLA", font=F(9, True), fg=MUTED, bg=PANEL, anchor="w").pack(fill="x")
        tk.Label(v.body, text=r["bottleneck"], font=F(26, True), fg=col, bg=PANEL, anchor="w").pack(fill="x")
        WrapLabel(v.body, text=r["headline"], font=F(11, True), fg=FG).pack(fill="x", pady=(2, 8))
        kv_rows(v.body, r["stats"], key_width=24)
        prev = r["prev"][-1] if r["prev"] else None
        if prev:
            k = r["kpi"]
            bits = [f"latencia p99: {prev['j99']} → {k['j99']} ms", f"DPC: {prev['dpc']} → {k['dpc']} %",
                    f"núcleo más cargado: {prev['hot']} → {k['hot']} %"]
            WrapLabel(v.body, text=f"Comparado con la medición anterior ({prev['ts']}):  " + "  ·  ".join(bits),
                      font=F(9), fg=MUTED).pack(fill="x", pady=(8, 0))

        tk.Label(root, text="Qué he encontrado", font=F(14, True), fg=FG, bg=BG, anchor="w").pack(fill="x", pady=(6, 6))
        for level, title, detail, fix in r["findings"] + r["checks"]:
            self._finding(root, level, title, detail, fix)

        if r["top"]:
            c = Card(root, accent=VIOLET, title="Programas que más CPU gastaron mientras jugabas")
            c.pack(fill="x", pady=(6, 12))
            kv_rows(c.body, [(n, f"{p:.1f} % de la CPU") for n, p in r["top"]], key_width=24)
            WrapLabel(c.body, text="Si ves aquí navegadores, launchers o programas que no necesitas, ciérralos antes de jugar "
                                   "(el Modo Extremo lo hace por ti).", font=F(9), fg=MUTED).pack(fill="x", pady=(6, 0))

    def _finding(self, root, level, title, detail, fix):
        name, col = LEVEL[level]
        c = Card(root, accent=col)
        c.pack(fill="x", pady=4)
        head = tk.Frame(c.body, bg=PANEL)
        head.pack(fill="x")
        badge(head, name, col).pack(side="left", padx=(0, 10))
        WrapLabel(head, text=title, font=F(11, True), fg=FG).pack(side="left", fill="x", expand=True)
        if detail:
            WrapLabel(c.body, text=detail, font=F(10), fg=MUTED).pack(fill="x", pady=(6, 0))
        if fix:
            WrapLabel(c.body, text="Qué hacer:  " + fix, font=F(10, True), fg=col if level != "bien" else FG).pack(fill="x", pady=(6, 0))
