"""Página «Análisis de PC»."""
import os
import tkinter as tk
import webbrowser
from tkinter import ttk

import psutil

import sysinfo
from util import age_text
from widgets import (BG, CYAN, F, FG, GREEN, MUTED, PANEL, PINK, RED, VIOLET, YELLOW, Card, Gauge,
                     NeonButton, ScrollFrame, WrapLabel, badge, kv_rows, page_title)

LEVEL_STYLE = {"ok": ("✓", GREEN), "info": ("ℹ", CYAN), "warn": ("⚠", YELLOW)}
TEMP_COLOR = {"ok": GREEN, "warn": YELLOW, "crit": RED}
ICONS = {"cpu": "▣", "board": "▤", "ram": "▥", "gpu": "◈", "disks": "▦", "os": "❖"}
ACCENTS = {"cpu": CYAN, "board": VIOLET, "ram": PINK, "gpu": GREEN, "disks": YELLOW, "os": CYAN}


class AnalysisPage(tk.Frame):
    def __init__(self, parent, app):
        super().__init__(parent, bg=BG)
        self.app = app
        self.temp_box = None
        self.temp_busy = False
        top = tk.Frame(self, bg=BG)
        top.pack(fill="x", padx=26, pady=(22, 6))
        page_title(top, "Análisis de PC",
                   "Lee tu procesador, placa, RAM, gráfica y discos, y te dice qué puedes mejorar.").pack(anchor="w")
        hero = Card(top, accent=CYAN, pad=16)
        hero.pack(fill="x", pady=(16, 4))
        gauges = tk.Frame(hero.body, bg=PANEL)
        gauges.pack(side="left")
        self.g_cpu = Gauge(gauges, "CPU", 120, CYAN)
        self.g_ram = Gauge(gauges, "RAM", 120, PINK)
        self.g_disk = Gauge(gauges, "DISCO", 120, YELLOW)
        for g in (self.g_cpu, self.g_ram, self.g_disk):
            g.pack(side="left", padx=6)
        row = tk.Frame(hero.body, bg=PANEL)
        row.pack(side="left", fill="x", expand=True, padx=(24, 0))
        self.btn = NeonButton(row, "⚡   ANÁLISIS DE PC", self.run, color=CYAN, filled=True, font=F(15, True),
                              padx=44, pady=14)
        self.btn.pack(anchor="w")
        info = tk.Frame(row, bg=PANEL)
        info.pack(anchor="w", pady=(10, 0))
        self._live()
        self.msg = tk.Label(info, text="Pulsa el botón para empezar.", font=F(10), fg=MUTED, bg=PANEL, anchor="w")
        self.msg.pack(anchor="w")
        self.pb = ttk.Progressbar(info, style="Neon.Horizontal.TProgressbar", mode="indeterminate", length=320)
        self.scroll = ScrollFrame(self)
        self.scroll.pack(fill="both", expand=True, padx=(26, 10), pady=(10, 12))
        self.report = None

    def _live(self):
        try:
            self.g_cpu.set(psutil.cpu_percent(interval=None))
            self.g_ram.set(psutil.virtual_memory().percent)
            self.g_disk.set(psutil.disk_usage(os.path.abspath(os.sep)).percent)
        except Exception:  # noqa: BLE001
            pass
        self.after(1500, self._live)

    # ------------------------------------------------------------------
    def run(self):
        self.btn.set_enabled(False)
        self.msg.config(text="Analizando tu equipo… (puede tardar unos segundos)", fg=CYAN)
        self.pb.pack(anchor="w", pady=(6, 0))
        self.pb.start(12)
        self.app.status("Analizando hardware…")
        self.app.bg(sysinfo.analyze, self.done, self.fail)

    def fail(self, e):
        self.pb.stop()
        self.pb.pack_forget()
        self.btn.set_enabled(True)
        self.msg.config(text=f"No pude completar el análisis: {e}", fg=RED)
        self.app.status("Análisis fallido")

    def done(self, rep):
        self.pb.stop()
        self.pb.pack_forget()
        self.btn.set_enabled(True)
        self.btn.set_text("⚡   ANALIZAR DE NUEVO")
        self.msg.config(text="Análisis completado ✓", fg=GREEN)
        self.app.status("Análisis completado")
        self.report = rep
        self.render(rep)

    # ------------------------------------------------------------------
    def render(self, rep):
        sf = self.scroll
        sf.clear()
        root = sf.inner

        grid = tk.Frame(root, bg=BG)
        grid.pack(fill="x", pady=(2, 10))
        grid.columnconfigure(0, weight=1, uniform="c")
        grid.columnconfigure(1, weight=1, uniform="c")
        for i, key in enumerate(("cpu", "board", "ram", "gpu", "disks", "os")):
            title, rows = rep["sections"][key]
            c = Card(grid, accent=ACCENTS[key], title=f"{ICONS[key]}  {title}")
            c.grid(row=i // 2, column=i % 2, sticky="nsew", padx=(0, 10) if i % 2 == 0 else 0, pady=(0, 10))
            kv_rows(c.body, rows)

        if rep["ram"]:
            self._ram_card(root, rep["ram"])
        self._temps_card(root)
        self._recs_card(root, rep["recs"])
        self._drivers_card(root, rep["drivers"])

        nxt = Card(root, accent=GREEN, title="➜  Siguiente paso")
        nxt.pack(fill="x", pady=(0, 14))
        WrapLabel(nxt.body, text="Con estos datos ya puedo proponerte optimizaciones a medida. Te las iré preguntando una por una.").pack(fill="x")
        NeonButton(nxt.body, "Ir a Optimizar  →", lambda: self.app.show("optimize"), color=GREEN, filled=True).pack(anchor="w", pady=(10, 0))

    def _ram_card(self, root, ram):
        c = Card(root, accent=PINK, title="▥  Memoria RAM · mejores tiempos para tu equipo")
        c.pack(fill="x", pady=(0, 10))
        color = {"ok": GREEN, "warn": YELLOW, "info": CYAN}[ram["level"]]
        tk.Label(c.body, text=ram["headline"], font=F(12, True), fg=color, bg=PANEL, anchor="w",
                 justify="left", wraplength=800).pack(fill="x", pady=(0, 6))
        for g in ram["goal"]:
            WrapLabel(c.body, text="•  " + g).pack(fill="x", pady=1)
        if ram["steps"]:
            tk.Label(c.body, text=f"Cómo activar {ram['xmp']} en la BIOS", font=F(10, True), fg=PINK,
                     bg=PANEL, anchor="w").pack(fill="x", pady=(10, 3))
            for i, s in enumerate(ram["steps"], 1):
                WrapLabel(c.body, text=f"{i}.  {s}").pack(fill="x", pady=1)

    def _temps_card(self, root):
        c = Card(root, accent=YELLOW, title="♨  Temperaturas")
        c.pack(fill="x", pady=(0, 10))
        self.temp_box = tk.Frame(c.body, bg=PANEL)
        self.temp_box.pack(fill="x")
        tk.Label(self.temp_box, text="Leyendo sensores…", fg=MUTED, bg=PANEL, font=F(10)).pack(anchor="w")
        WrapLabel(c.body, fg=MUTED, font=F(8),
                  text="Se actualiza cada pocos segundos. Windows no expone todos los sensores: para lecturas precisas de CPU "
                       "deja abierto LibreHardwareMonitor y la app las usará automáticamente.").pack(fill="x", pady=(8, 0))
        self._read_temps()

    def _read_temps(self):
        if self.temp_busy:
            return
        self.temp_busy = True
        self.app.bg(sysinfo.read_temps, self._temps_done, lambda e: self._temps_done([]))

    def _temps_done(self, temps):
        self.temp_busy = False
        box = self.temp_box
        if box is None or not box.winfo_exists():
            return
        for w in box.winfo_children():
            w.destroy()
        if not temps:
            tk.Label(box, text="Windows no ha dado lecturas de temperatura en este equipo.", fg=MUTED,
                     bg=PANEL, font=F(10)).pack(anchor="w")
        for t in temps:
            r = tk.Frame(box, bg=PANEL)
            r.pack(fill="x", pady=2)
            color = TEMP_COLOR[t["level"]]
            tk.Label(r, text=f"{t['value']:.0f} °C", font=F(14, True), fg=color, bg=PANEL, width=7, anchor="w").pack(side="left")
            tk.Label(r, text=t["label"], font=F(10), fg=FG, bg=PANEL, anchor="w").pack(side="left")
            if t["level"] != "ok":
                badge(r, "CALIENTE" if t["level"] == "warn" else "CRÍTICA", color).pack(side="left", padx=8)
            if t["note"]:
                tk.Label(r, text=t["note"], font=F(9), fg=YELLOW if "aprox" in t["note"] else RED, bg=PANEL).pack(side="left", padx=8)
        self.after(5000, self._tick)

    def _tick(self):
        if self.app.current == "analysis" and self.temp_box is not None and self.temp_box.winfo_exists():
            self._read_temps()
        elif self.temp_box is not None and self.temp_box.winfo_exists():
            self.after(5000, self._tick)

    def on_show(self):
        if self.report and self.temp_box is not None and self.temp_box.winfo_exists():
            self._read_temps()

    def _recs_card(self, root, recs):
        c = Card(root, accent=VIOLET, title="✚  Salud y recomendaciones")
        c.pack(fill="x", pady=(0, 10))
        for level, title, detail in recs:
            icon, color = LEVEL_STYLE.get(level, LEVEL_STYLE["info"])
            r = tk.Frame(c.body, bg=PANEL)
            r.pack(fill="x", pady=4)
            tk.Label(r, text=icon, font=F(14, True), fg=color, bg=PANEL, width=3).pack(side="left", anchor="n")
            t = tk.Frame(r, bg=PANEL)
            t.pack(side="left", fill="x", expand=True)
            tk.Label(t, text=title, font=F(10, True), fg=FG, bg=PANEL, anchor="w").pack(fill="x")
            WrapLabel(t, text=detail, fg=MUTED).pack(fill="x")

    def _drivers_card(self, root, drivers):
        c = Card(root, accent=CYAN, title="⚙  Drivers")
        c.pack(fill="x", pady=(0, 10))
        if not drivers:
            tk.Label(c.body, text="No se pudieron leer los drivers.", fg=MUTED, bg=PANEL, font=F(10)).pack(anchor="w")
            return
        WrapLabel(c.body, fg=MUTED, font=F(9),
                  text="Una fecha antigua no siempre significa que falte una versión nueva: compruébalo en la web del fabricante. "
                       "Actualiza siempre desde la página oficial.").pack(fill="x", pady=(0, 6))
        for d in drivers[:14]:
            r = tk.Frame(c.body, bg=PANEL)
            r.pack(fill="x", pady=3)
            (badge(r, "ANTIGUO", YELLOW) if d["old"] else badge(r, "AL DÍA", GREEN)).pack(side="left", padx=(0, 10))
            t = tk.Frame(r, bg=PANEL)
            t.pack(side="left", fill="x", expand=True)
            tk.Label(t, text=d["name"], font=F(10, True), fg=FG, bg=PANEL, anchor="w").pack(fill="x")
            tk.Label(t, text=f"versión {d['version']} · {d['date']} ({age_text(d['age_days'])})", font=F(9),
                     fg=MUTED, bg=PANEL, anchor="w").pack(fill="x")
            if d["old"] and d["url"]:
                NeonButton(r, "Buscar actualización", lambda u=d["url"]: webbrowser.open(u), color=CYAN, padx=10,
                           pady=4, font=F(9, True)).pack(side="right")
