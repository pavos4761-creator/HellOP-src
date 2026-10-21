"""Página «Rendimiento»: test antes/después con comparación."""
import tkinter as tk
from tkinter import ttk

import bench
from util import DEMO
from widgets import (BG, CYAN, F, FG, GREEN, MUTED, PANEL, PINK, RED, YELLOW, Card, NeonButton,
                     ScrollFrame, WrapLabel, page_title)

STATE_COLOR = {"better": GREEN, "worse": RED, "same": MUTED, "na": MUTED}


class BenchPage(tk.Frame):
    def __init__(self, parent, app):
        super().__init__(parent, bg=BG)
        self.app = app
        self.busy = False
        top = tk.Frame(self, bg=BG)
        top.pack(fill="x", padx=26, pady=(22, 6))
        page_title(top, "Rendimiento", "Mide tu PC antes y después de optimizar y compara con números reales.",
                   accent=PINK).pack(anchor="w")
        row = tk.Frame(top, bg=BG)
        row.pack(fill="x", pady=(14, 4))
        self.b_before = NeonButton(row, "Test «ANTES»", lambda: self.run("before"), color=CYAN, padx=22, pady=10)
        self.b_before.pack(side="left")
        self.b_after = NeonButton(row, "Test «DESPUÉS»", lambda: self.run("after"), color=GREEN, filled=True, padx=22, pady=10)
        self.b_after.pack(side="left", padx=10)
        self.msg = tk.Label(row, text="", font=F(10), fg=MUTED, bg=BG)
        self.msg.pack(side="left", padx=12)
        self.pb = ttk.Progressbar(top, style="Neon.Horizontal.TProgressbar", mode="determinate", maximum=100, length=420)
        self.scroll = ScrollFrame(self)
        self.scroll.pack(fill="both", expand=True, padx=(26, 10), pady=(8, 10))

    def on_show(self):
        if not self.busy:
            self.render()

    def run(self, kind):
        if self.busy:
            return
        self.busy = True
        self.b_before.set_enabled(False)
        self.b_after.set_enabled(False)
        self.pb.pack(anchor="w", pady=(4, 0))
        self.pb["value"] = 0
        self.msg.config(text="Midiendo… no uses el PC durante unos segundos.", fg=CYAN)
        improved = kind == "after"

        def work():
            m = bench.run_benchmark(lambda p, t: self.app.ui(self._prog, p, t), improved=improved)
            bench.save_snap(kind, m)
            return kind

        self.app.bg(work, self.done, self.fail)

    def _prog(self, pct, text):
        self.pb["value"] = pct
        self.msg.config(text=text, fg=CYAN)

    def fail(self, e):
        self.busy = False
        self.pb.pack_forget()
        self.b_before.set_enabled(True)
        self.b_after.set_enabled(True)
        self.msg.config(text=f"Error: {e}", fg=RED)

    def done(self, kind):
        self.busy = False
        self.pb.pack_forget()
        self.b_before.set_enabled(True)
        self.b_after.set_enabled(True)
        self.msg.config(text="✓ Test guardado", fg=GREEN)
        self.render()

    def render(self):
        sf = self.scroll
        sf.clear()
        snaps = bench.load_snaps()
        before, after = snaps.get("before"), snaps.get("after")
        root = sf.inner
        if not before and not after:
            c = Card(root, accent=CYAN)
            c.pack(fill="x")
            WrapLabel(c.body, text="Aún no hay tests. Haz primero el «ANTES», optimiza, y luego el «DESPUÉS» para ver la mejora real. "
                                   "Cada test dura unos 20 segundos.").pack(fill="x")
            return
        rows = bench.compare(before["metrics"] if before else None, after["metrics"] if after else None)
        good = [r for r in rows if r["state"] == "better"]
        bad = [r for r in rows if r["state"] == "worse"]
        head = Card(root, accent=GREEN if good else CYAN)
        head.pack(fill="x", pady=(0, 12))
        if before and after:
            tk.Label(head.body, text=f"{len(good)} métricas mejoran · {len(bad)} empeoran", font=F(16, True),
                     fg=GREEN if len(good) >= len(bad) else YELLOW, bg=PANEL, anchor="w").pack(fill="x")
            tk.Label(head.body, text=f"Antes: {before['ts']}     Después: {after['ts']}", font=F(9), fg=MUTED, bg=PANEL, anchor="w").pack(fill="x")
            WrapLabel(head.body, fg=MUTED, font=F(9),
                      text="Pequeñas diferencias (±3 %) son ruido normal y se marcan como «igual». El arranque de Windows solo cambia tras reiniciar.").pack(fill="x", pady=(4, 0))
        else:
            tk.Label(head.body, text="Falta el test «ANTES»" if not before else "Falta el test «DESPUÉS»", font=F(14, True),
                     fg=YELLOW, bg=PANEL).pack(anchor="w")
        c = Card(root, accent=PINK, title="Comparación")
        c.pack(fill="x")
        grid = tk.Frame(c.body, bg=PANEL)
        grid.pack(fill="x")
        grid.columnconfigure(0, weight=1)
        for j, h in enumerate(("Métrica", "Antes", "Después", "Cambio")):
            tk.Label(grid, text=h, font=F(9, True), fg=CYAN, bg=PANEL, anchor="w" if j == 0 else "e", width=0 if j == 0 else 14).grid(
                row=0, column=j, sticky="ew", padx=6, pady=(0, 6))
        for i, r in enumerate(rows, 1):
            col = STATE_COLOR[r["state"]]
            tk.Label(grid, text=r["name"], font=F(10), fg=FG, bg=PANEL, anchor="w").grid(row=i, column=0, sticky="ew", padx=6, pady=3)
            tk.Label(grid, text=r["before"], font=("Consolas", 10), fg=MUTED, bg=PANEL, anchor="e", width=14).grid(row=i, column=1, padx=6)
            tk.Label(grid, text=r["after"], font=("Consolas", 10), fg=FG, bg=PANEL, anchor="e", width=14).grid(row=i, column=2, padx=6)
            if r["pct"] is None:
                txt = "—"
            else:
                arrow = "▲" if r["pct"] >= 3 else "▼" if r["pct"] <= -3 else "="
                txt = f"{arrow} {abs(r['pct']):.0f} %" + (" mejor" if r["state"] == "better" else " peor" if r["state"] == "worse" else "")
            tk.Label(grid, text=txt, font=F(10, True), fg=col, bg=PANEL, anchor="e", width=14).grid(row=i, column=3, padx=6)
