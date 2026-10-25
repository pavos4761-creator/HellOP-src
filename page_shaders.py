"""Página «Limpiar shaders»: borra las cachés de shaders (DirectX, NVIDIA, AMD, Intel, Steam) para arreglar tirones raros."""
import tkinter as tk
from tkinter import messagebox

import shaders
from util import DEMO, fmt_bytes
from widgets import (BG, CYAN, F, FG, GREEN, MUTED, PANEL, PINK, RED, YELLOW, Card, NeonButton, ScrollFrame, WrapLabel, checkbox,
                     page_title)


class ShadersPage(tk.Frame):
    def __init__(self, parent, app):
        super().__init__(parent, bg=BG)
        self.app = app
        self.busy = False
        self.items, self.vars = [], {}
        top = tk.Frame(self, bg=BG)
        top.pack(fill="x", padx=26, pady=(22, 6))
        page_title(top, "Limpiar shaders", "Arregla tirones, parpadeos o artefactos tras actualizar el driver o un juego.", accent=PINK).pack(anchor="w")
        self.scroll = ScrollFrame(self)
        self.scroll.pack(fill="both", expand=True, padx=(26, 10), pady=(8, 10))
        root = self.scroll.inner
        c = Card(root, accent=YELLOW, title="Cuándo sirve (y cuándo no)")
        c.pack(fill="x", pady=(0, 12))
        for t in ("Los shaders son «trozos» de gráficos que tu PC guarda ya preparados. A veces se corrompen o quedan viejos y dan "
                  "tirones raros, parpadeos o texturas rotas, sobre todo tras actualizar el driver de la gráfica o el juego.",
                  "Honestidad: limpiar esto NO sube los FPS. Solo arregla fallos. Si tu juego va bien, déjalo como está.",
                  "La primera partida después irá algo peor (tirones mientras se vuelven a crear) y luego vuelve a la normalidad.",
                  "Se borra solo el contenido de esas carpetas de caché. Cierra los juegos antes. No se puede deshacer, "
                  "pero tampoco hace falta: se regeneran solas."):
            WrapLabel(c.body, text="•  " + t, font=F(9), fg=MUTED).pack(fill="x", pady=1)
        bar = tk.Frame(root, bg=BG)
        bar.pack(fill="x", pady=(0, 8))
        self.b_scan = NeonButton(bar, "↻  BUSCAR CACHÉS", self.scan, color=PINK, filled=True, font=F(11, True), padx=20, pady=8)
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

    def scan(self):
        if self.busy:
            return
        self.busy = True
        self.b_scan.set_enabled(False)
        self.msg.config(text="Midiendo las cachés…", fg=CYAN)
        self.app.bg(shaders.scan, self._scanned, self._fail)

    def _fail(self, e):
        self.busy = False
        self.b_scan.set_enabled(True)
        self.msg.config(text=f"Error: {e}", fg=RED)

    def _scanned(self, items):
        self.busy = False
        self.b_scan.set_enabled(True)
        self.items = items
        total = sum(i["size"] for i in items)
        self.msg.config(text=(f"{len(items)} cachés · {fmt_bytes(total)} en total" if items else "No he encontrado cachés de shaders."), fg=GREEN)
        self.render()

    def render(self):
        for w in self.body.winfo_children():
            w.destroy()
        self.vars = {}
        if not self.items:
            return
        c = Card(self.body, accent=PINK, title="Cachés encontradas")
        c.pack(fill="x", pady=(0, 12))
        for it in self.items:
            v = tk.BooleanVar(value=False)
            self.vars[it["id"]] = v
            r = tk.Frame(c.body, bg=PANEL)
            r.pack(fill="x", pady=4)
            checkbox(r, f"{it['label']}   ({fmt_bytes(it['size'])})", v, bg=PANEL, font=F(10, True)).pack(anchor="w")
            WrapLabel(r, text=it["desc"], font=F(9), fg=MUTED).pack(fill="x", padx=(26, 0))
        row = tk.Frame(self.body, bg=BG)
        row.pack(fill="x", pady=(0, 14))
        NeonButton(row, "✖  LIMPIAR LAS MARCADAS", self.clean, color=RED, filled=True, font=F(11, True), padx=20, pady=8).pack(side="left")

    def clean(self):
        chosen = [i for i in self.items if self.vars.get(i["id"]) and self.vars[i["id"]].get()]
        if self.busy:
            return
        if not chosen:
            self.msg.config(text="Marca primero alguna caché.", fg=YELLOW)
            return
        if not DEMO and not messagebox.askyesno("Limpiar shaders", "Se borrará el contenido de:\n\n" + "\n".join("· " + i["label"] for i in chosen)
                                                + "\n\nCierra antes tus juegos. La primera partida irá algo peor mientras se regeneran.\n¿Continuar?"):
            return
        self.busy = True
        self.msg.config(text="Limpiando…", fg=CYAN)

        def done(res):
            self.busy = False
            freed, errs = res
            self.msg.config(text=(f"✓ Liberados {fmt_bytes(freed)}" if not errs else "✗ " + " · ".join(errs)), fg=GREEN if not errs else RED)
            if not DEMO:
                self.scan()
        self.app.bg(lambda: shaders.clean(chosen), done, self._fail)
