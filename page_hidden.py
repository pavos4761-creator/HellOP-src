"""Página «Rendimiento oculto»: los problemas que más FPS y fluidez cuestan de verdad, detectados en TU equipo."""
import tkinter as tk

import actions
import hidden
from util import DEMO
from widgets import (BG, CYAN, F, FG, GREEN, MUTED, PANEL, PINK, RED, YELLOW, Card, NeonButton, ScrollFrame, WrapLabel,
                     page_title)

SEV_COL = {"bad": RED, "warn": YELLOW, "info": CYAN, "ok": GREEN}
SEV_TXT = {"bad": "PROBLEMA", "warn": "MEJORABLE", "info": "A REVISAR", "ok": "BIEN"}


class HiddenPage(tk.Frame):
    def __init__(self, parent, app):
        super().__init__(parent, bg=BG)
        self.app = app
        self.busy = False
        top = tk.Frame(self, bg=BG)
        top.pack(fill="x", padx=26, pady=(22, 6))
        page_title(top, "Rendimiento oculto",
                   "Lo que más FPS te está costando sin que lo sepas, ordenado de más a menos importante.", accent=PINK).pack(anchor="w")
        row = tk.Frame(top, bg=BG)
        row.pack(fill="x", pady=(14, 4))
        self.btn = NeonButton(row, "⌕   BUSCAR RENDIMIENTO PERDIDO", self.run, color=PINK, filled=True, font=F(14, True), padx=34, pady=12)
        self.btn.pack(side="left")
        self.msg = tk.Label(row, text="", font=F(10), fg=MUTED, bg=BG)
        self.msg.pack(side="left", padx=16)
        self.scroll = ScrollFrame(self)
        self.scroll.pack(fill="both", expand=True, padx=(26, 10), pady=(8, 10))
        intro = Card(self.scroll.inner, accent=YELLOW, title="Qué es esto")
        intro.pack(fill="x")
        for t in ("En Windows no hay un «tweak mágico» que dé +30 %: los saltos grandes vienen de cosas más básicas que se pasan por alto.",
                  "Aquí miro las que de verdad cuestan rendimiento: monitor a menos Hz de los que soporta, RAM sin su perfil o en canal único, "
                  "juegos en un HDD, gráfica con menos líneas PCIe, VBS, plan de energía y programas de fondo.",
                  "Los porcentajes son rangos de pruebas públicas, no promesas: dependen de tu juego y de tu equipo."):
            WrapLabel(intro.body, text="•  " + t, font=F(9), fg=MUTED).pack(fill="x", pady=1)
        self.body = tk.Frame(self.scroll.inner, bg=BG)
        self.body.pack(fill="x", pady=(10, 0))
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
        self.msg.config(text="Buscando…", fg=CYAN)
        self.app.bg(lambda: hidden.scan(lambda m: self.app.ui(self._say, m)), self.done, self.fail)

    def _say(self, m):
        self.msg.config(text=m, fg=CYAN)

    def fail(self, e):
        self.busy = False
        self.btn.set_enabled(True)
        self.msg.config(text=f"Error: {e}", fg=RED)

    def done(self, items):
        self.busy = False
        self.btn.set_enabled(True)
        self.btn.set_text("↻   BUSCAR DE NUEVO")
        bad = sum(1 for f in items if f["sev"] in ("bad", "warn"))
        self.msg.config(text=(f"{bad} cosa(s) que te cuestan rendimiento" if bad else "No he encontrado nada importante: tu PC está bien configurado"),
                        fg=YELLOW if bad else GREEN)
        for w in self.body.winfo_children():
            w.destroy()
        for f in items:
            self._card(f)

    def _card(self, f):
        col = SEV_COL[f["sev"]]
        c = Card(self.body, accent=col)
        c.pack(fill="x", pady=(0, 10))
        head = tk.Frame(c.body, bg=PANEL)
        head.pack(fill="x")
        tk.Label(head, text=SEV_TXT[f["sev"]], font=F(8, True), fg=col, bg=PANEL).pack(side="left")
        tk.Label(head, text="   " + f["title"], font=F(11, True), fg=FG, bg=PANEL, anchor="w").pack(side="left")
        if f["sev"] == "ok":
            return
        if f["impact"]:
            WrapLabel(c.body, text="Impacto: " + f["impact"], font=F(9, True), fg=col).pack(fill="x", pady=(4, 0))
        if f["detail"]:
            WrapLabel(c.body, text=f["detail"], font=F(9), fg=MUTED).pack(fill="x", pady=(3, 0))
        fix = f.get("fix")
        if fix:
            kind, target, label = fix
            cmd = (lambda a=target, b=None: self.apply(a)) if kind == "action" else (lambda p=target: self.app.show(p))
            NeonButton(c.body, label, cmd, color=col if kind == "action" else CYAN, filled=(kind == "action"), padx=16, pady=6,
                       font=F(10, True)).pack(anchor="w", pady=(8, 0))

    def apply(self, action):
        self.msg.config(text="Aplicando…", fg=CYAN)

        def done(res):
            self.msg.config(text=("✓ " if res.ok else "✗ ") + res.msg, fg=GREEN if res.ok else RED)
            if res.ok:
                self.app.after(2500, self.run)
        self.app.bg(lambda: actions.execute(action), done, lambda e: self.msg.config(text=f"✗ {e}", fg=RED))
