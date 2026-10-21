"""Página «Historial / Deshacer»."""
import tkinter as tk
from tkinter import messagebox

import actions
from widgets import (BG, CYAN, F, FG, GREEN, MUTED, PANEL, RED, YELLOW, Card, NeonButton, ScrollFrame,
                     WrapLabel, badge, page_title)


class HistoryPage(tk.Frame):
    def __init__(self, parent, app):
        super().__init__(parent, bg=BG)
        self.app = app
        top = tk.Frame(self, bg=BG)
        top.pack(fill="x", padx=26, pady=(22, 6))
        page_title(top, "Historial / Deshacer", "Todo lo que la app ha cambiado. Puedes volver atrás cambio por cambio.",
                   accent=YELLOW).pack(anchor="w")
        self.b_all = NeonButton(top, "↺  Deshacer todo lo reversible", self.undo_all, color=YELLOW, padx=16, pady=8)
        self.b_all.pack(anchor="w", pady=(12, 0))
        self.scroll = ScrollFrame(self)
        self.scroll.pack(fill="both", expand=True, padx=(26, 10), pady=(8, 10))

    def on_show(self):
        self.render()

    def render(self):
        sf = self.scroll
        sf.clear()
        entries = list(reversed(actions.load_log()))
        pending = [e for e in entries if e["reversible"] and not e["undone"]]
        self.b_all.set_enabled(bool(pending))
        if not entries:
            c = Card(sf.inner, accent=CYAN)
            c.pack(fill="x")
            WrapLabel(c.body, text="Todavía no has cambiado nada. Cuando apliques optimizaciones aparecerán aquí.").pack(fill="x")
            return
        for e in entries:
            c = Card(sf.inner, accent=MUTED if e["undone"] else GREEN, pad=10)
            c.pack(fill="x", pady=(0, 8))
            r = tk.Frame(c.body, bg=PANEL)
            r.pack(fill="x")
            t = tk.Frame(r, bg=PANEL)
            t.pack(side="left", fill="x", expand=True)
            tk.Label(t, text=e["title"], font=F(10, True), fg=MUTED if e["undone"] else FG, bg=PANEL, anchor="w",
                     justify="left", wraplength=620).pack(fill="x")
            tk.Label(t, text=e["ts"], font=F(9), fg=MUTED, bg=PANEL, anchor="w").pack(fill="x")
            if e["undone"]:
                badge(r, "DESHECHO", MUTED).pack(side="right")
            elif e["reversible"]:
                NeonButton(r, "Deshacer", lambda i=e["id"]: self.undo(i), color=YELLOW, padx=12, pady=5,
                           font=F(9, True)).pack(side="right")
            else:
                badge(r, "NO REVERSIBLE", RED).pack(side="right")

    def undo(self, entry_id):
        res = actions.undo_entry(entry_id)
        self.app.status(res.msg)
        if not res.ok:
            messagebox.showwarning("Deshacer", res.msg)
        self.render()

    def undo_all(self):
        if not messagebox.askyesno("Deshacer todo", "Se revertirán todos los cambios reversibles pendientes.\n¿Continuar?"):
            return
        done, fail = actions.undo_all()
        self.app.status(f"Deshechos {done} cambios" + (f" · {fail} con error" if fail else ""))
        self.render()
