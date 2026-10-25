"""Página «Gestor de arranque»: qué abre Windows al encender, con su impacto, para desactivarlo o reactivarlo."""
import tkinter as tk

import arranque
from util import DEMO
from widgets import (BG, CYAN, F, FG, GREEN, MUTED, PANEL, PINK, RED, YELLOW, Card, NeonButton, ScrollFrame, WrapLabel, badge,
                     page_title)

IMPACT_COL = {"alto": RED, "medio": YELLOW, "bajo": GREEN}


class ArranquePage(tk.Frame):
    def __init__(self, parent, app):
        super().__init__(parent, bg=BG)
        self.app = app
        self.busy = False
        self.items, self.boot = [], None
        top = tk.Frame(self, bg=BG)
        top.pack(fill="x", padx=26, pady=(22, 6))
        page_title(top, "Gestor de arranque", "Qué se abre solo al encender Windows y cuánto lo retrasa. Desactivas y reactivas cuando quieras.",
                   accent=CYAN).pack(anchor="w")
        self.scroll = ScrollFrame(self)
        self.scroll.pack(fill="both", expand=True, padx=(26, 10), pady=(8, 10))
        root = self.scroll.inner
        c = Card(root, accent=YELLOW, title="Antes de empezar")
        c.pack(fill="x", pady=(0, 12))
        for t in ("Desactivar NO desinstala nada: el programa sigue en tu PC y se abrirá cuando tú lo lances.",
                  "Todo queda en el Historial y se puede deshacer. Los componentes de seguridad salen marcados como protegidos.",
                  "Honestidad: en un SSD moderno el arranque ya es rápido y ganarás pocos segundos. Se nota más con disco duro, "
                  "con muchos programas activos o con RAM justa. No sube los FPS en el juego."):
            WrapLabel(c.body, text="•  " + t, font=F(9), fg=MUTED).pack(fill="x", pady=1)
        bar = tk.Frame(root, bg=BG)
        bar.pack(fill="x", pady=(0, 8))
        self.b_scan = NeonButton(bar, "↻  REVISAR MI ARRANQUE", self.scan, color=CYAN, filled=True, font=F(11, True), padx=20, pady=8)
        self.b_scan.pack(side="left")
        self.msg = tk.Label(bar, text="", font=F(10), fg=MUTED, bg=BG)
        self.msg.pack(side="left", padx=14)
        self.body = tk.Frame(root, bg=BG)
        self.body.pack(fill="x")
        self._loaded = False

    def on_show(self):
        if not self._loaded:
            self._loaded = True
            self.scan()

    # ------------------------------------------------------------------
    def scan(self):
        if self.busy:
            return
        self.busy = True
        self.b_scan.set_enabled(False)
        self.msg.config(text="Leyendo el arranque de Windows (unos segundos)…", fg=CYAN)
        self.app.bg(arranque.entries, self._scanned, self._fail)

    def _fail(self, e):
        self.busy = False
        self.b_scan.set_enabled(True)
        self.msg.config(text=f"Error: {e}", fg=RED)

    def _scanned(self, res):
        self.busy = False
        self.b_scan.set_enabled(True)
        self.items, self.boot = res
        self.render()

    def render(self):
        for w in self.body.winfo_children():
            w.destroy()
        on = [i for i in self.items if i["enabled"]]
        off = [i for i in self.items if not i["enabled"]]
        alto = sum(1 for i in on if i["impact"] == "alto" and not i["protected"])
        resumen = f"{len(on)} activos · {len(off)} desactivados"
        if self.boot:
            resumen = f"Último arranque: {self.boot:.0f} s  ·  " + resumen
        self.msg.config(text=resumen, fg=GREEN)
        if alto:
            WrapLabel(self.body, text=f"Hay {alto} programa(s) de impacto ALTO que puedes desactivar para arrancar antes.",
                      font=F(10, True), fg=YELLOW).pack(fill="x", pady=(0, 8))
        for title, group, accent in (("Se abren al iniciar", on, PINK), ("Desactivados", off, MUTED)):
            c = Card(self.body, accent=accent, title=title)
            c.pack(fill="x", pady=(0, 12))
            if not group:
                WrapLabel(c.body, text="Nada por aquí.", font=F(10), fg=MUTED).pack(fill="x")
            for it in group:
                self._row(c.body, it)

    def _row(self, parent, it):
        r = tk.Frame(parent, bg=PANEL)
        r.pack(fill="x", pady=5)
        tx = tk.Frame(r, bg=PANEL)
        tx.pack(side="left", fill="x", expand=True)
        head = tk.Frame(tx, bg=PANEL)
        head.pack(fill="x")
        tk.Label(head, text=it["name"], font=F(10, True), fg=FG, bg=PANEL).pack(side="left")
        if it["enabled"]:
            col = IMPACT_COL[it["impact"]]
            tk.Label(head, text=f"  impacto {it['impact'].upper()} ({it['how']})", font=F(8, True), fg=col, bg=PANEL).pack(side="left")
        if it["protected"]:
            tk.Label(head, text="  protegido", font=F(8, True), fg=MUTED, bg=PANEL).pack(side="left")
        WrapLabel(tx, text=it["desc"], font=F(9), fg=MUTED).pack(fill="x")
        cmd = it["command"].strip()
        tk.Label(tx, text=cmd if len(cmd) <= 95 else cmd[:92] + "…", font=("Consolas", 8), fg=MUTED, bg=PANEL, anchor="w").pack(fill="x")
        if it["protected"]:
            return
        if it["enabled"]:
            NeonButton(r, "Desactivar", lambda i=it: self.toggle(i, False), color=RED if it["impact"] == "alto" else MUTED,
                       padx=14, pady=5, font=F(9, True)).pack(side="right")
        else:
            NeonButton(r, "Activar", lambda i=it: self.toggle(i, True), color=GREEN, padx=14, pady=5, font=F(9, True)).pack(side="right")

    def toggle(self, it, on):
        if self.busy:
            return
        self.busy = True
        self.msg.config(text="Aplicando…", fg=CYAN)
        fn = arranque.enable if on else arranque.disable

        def done(res):
            self.busy = False
            if res.ok:
                it["enabled"] = on
                self.render()
                self.msg.config(text="✓ " + res.msg + f" · «{it['name']}» " + ("activado" if on else "desactivado"), fg=GREEN)
            else:
                self.msg.config(text="✗ " + res.msg, fg=RED)
        self.app.bg(lambda: fn(it), done, self._fail)
