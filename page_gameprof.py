"""Página «Ajustes de juego»: perfiles de gráficos para tus juegos, con copia y deshacer."""
import tkinter as tk
from tkinter import messagebox

import actions
import gameprofiles as gp
from util import DEMO
from widgets import (BG, CYAN, F, FG, GREEN, MUTED, PANEL, PINK, RED, YELLOW, Card, NeonButton, ScrollFrame, WrapLabel,
                     page_title)


class GameProfilePage(tk.Frame):
    def __init__(self, parent, app):
        super().__init__(parent, bg=BG)
        self.app = app
        self.busy = False
        top = tk.Frame(self, bg=BG)
        top.pack(fill="x", padx=26, pady=(22, 6))
        page_title(top, "Ajustes de juego",
                   "Baja lo que más cuesta FPS dentro del propio juego (sombras, efectos, límite de FPS) con un clic.",
                   accent=PINK).pack(anchor="w")
        self.scroll = ScrollFrame(self)
        self.scroll.pack(fill="both", expand=True, padx=(26, 10), pady=(8, 10))
        root = self.scroll.inner
        c = Card(root, accent=YELLOW, title="Qué hace y qué no")
        c.pack(fill="x", pady=(0, 12))
        for t in ("Cambia el archivo de configuración del juego. Solo toca valores que ya existen y antes guarda una copia.",
                  "Es lo que más FPS da si tu gráfica va al 100 %: los ajustes de Windows no pueden darle más potencia, "
                  "pero bajar sombras y efectos sí.",
                  "Cierra el juego antes de aplicar. Si está abierto, lo reescribe al salir y se pierde el cambio.",
                  "«Restaurar» devuelve el archivo tal como estaba. También aparece en Historial."):
            WrapLabel(c.body, text="•  " + t, font=F(9), fg=MUTED).pack(fill="x", pady=1)
        bar = tk.Frame(root, bg=BG)
        bar.pack(fill="x", pady=(0, 8))
        NeonButton(bar, "↻  BUSCAR MIS JUEGOS", self.refresh, color=PINK, filled=True, font=F(11, True), padx=20, pady=8).pack(side="left")
        self.msg = tk.Label(bar, text="", font=F(10), fg=MUTED, bg=BG)
        self.msg.pack(side="left", padx=14)
        self.list = tk.Frame(root, bg=BG)
        self.list.pack(fill="x")
        self._loaded = False

    def on_show(self):
        if not self._loaded:
            self.refresh()

    def refresh(self):
        self._loaded = True
        self.msg.config(text="Buscando…", fg=CYAN)
        self.app.bg(self._collect, self._render, lambda e: self.msg.config(text=f"Error: {e}", fg=RED))

    def _collect(self):
        found = gp.find_files()
        out = []
        for gid in gp.GAMES:
            if gid in found:
                out.append((gid, str(found[gid]), {p: gp.plan(gid, p) for p in gp.PRESETS}))
        return out, [g for g in gp.find_guides() if g in gp.GUIDES]

    def _last_entry(self, gid):
        for e in reversed(actions.load_log()):
            if e.get("cls") == "GameConfigAction" and not e.get("undone") and e.get("data", {}).get("gid") == gid:
                return e
        return None

    def _render(self, res):
        data, guides = res
        for w in self.list.winfo_children():
            w.destroy()
        for gid in guides:
            g = gp.GUIDES[gid]
            c = Card(self.list, accent=CYAN, title=f"{g['name']}  ·  guía de ajustes")
            c.pack(fill="x", pady=(0, 12))
            WrapLabel(c.body, text=g["note"], font=F(9), fg=MUTED).pack(fill="x", pady=(0, 6))
            for i, t in enumerate(g["steps"], 1):
                WrapLabel(c.body, text=f"{i}.  {t}", font=F(10), fg=FG).pack(fill="x", pady=2)
        if not data and not guides:
            self.msg.config(text="No he encontrado ninguno de los juegos compatibles (Fortnite, VALORANT, Minecraft Java, League of Legends, CS2, eFootball).", fg=YELLOW)
            return
        self.msg.config(text=f"{len(data) + len(guides)} juego(s) encontrado(s)", fg=GREEN)
        for gid, path, plans in data:
            g = gp.GAMES[gid]
            c = Card(self.list, accent=PINK, title=g["name"])
            c.pack(fill="x", pady=(0, 12))
            tk.Label(c.body, text=path, font=F(8), fg=MUTED, bg=PANEL, anchor="w").pack(fill="x")
            WrapLabel(c.body, text=g["note"], font=F(9), fg=MUTED).pack(fill="x", pady=(2, 8))
            row = tk.Frame(c.body, bg=PANEL)
            row.pack(fill="x")
            for key, (label, _d) in gp.PRESETS.items():
                n = len(plans[key])
                col = PINK if key == "max" else CYAN
                b = NeonButton(row, f"{label}  ({n} cambios)" if n else f"{label}  (ya está así)",
                               lambda g_=gid, k=key: self.apply(g_, k), color=col, filled=(key == "max"),
                               font=F(10, True), padx=16, pady=7)
                b.pack(side="left", padx=(0, 10))
                if not n:
                    b.set_enabled(False)
            last = self._last_entry(gid)
            rb = NeonButton(row, "↺  Restaurar", lambda g_=gid: self.restore(g_), color=YELLOW, font=F(10, True), padx=14, pady=7)
            rb.pack(side="left")
            if not last:
                rb.set_enabled(False)
            best = plans["max"] or plans["balanced"]
            if best:
                tk.Label(c.body, text="Cambios de «Máximo FPS»:" if plans["max"] else "Cambios:", font=F(9, True), fg=FG,
                         bg=PANEL, anchor="w").pack(fill="x", pady=(10, 2))
                for k, old, new in best[:10]:
                    tk.Label(c.body, text=f"{k}:   {old}  →  {new}", font=("Consolas", 9), fg=MUTED, bg=PANEL, anchor="w").pack(fill="x")

    def apply(self, gid, preset):
        if self.busy:
            return
        name = gp.GAMES[gid]["name"]
        if not DEMO and not messagebox.askyesno("Aplicar perfil", f"Se cambiará la configuración de {name} (se guarda una copia).\n\n"
                                                 "¿Has cerrado el juego?"):
            return
        self.busy = True
        self.msg.config(text="Aplicando…", fg=CYAN)
        self.app.bg(lambda: actions.execute(gp.GameConfigAction(gid, preset)), self._done, lambda e: self._done(None, str(e)))

    def _done(self, res, err=None):
        self.busy = False
        if res is None or not res.ok:
            self.msg.config(text="✗ " + (err or res.msg), fg=RED)
        else:
            self.msg.config(text="✓ " + res.msg, fg=GREEN)
        self.refresh_keep()

    def refresh_keep(self):
        self.app.bg(self._collect, self._render_keep, lambda e: None)

    def _render_keep(self, data):
        txt, col = self.msg.cget("text"), self.msg.cget("fg")
        self._render(data)
        self.msg.config(text=txt, fg=col)

    def restore(self, gid):
        e = self._last_entry(gid)
        if not e:
            return
        r = actions.undo_entry(e["id"])
        self.msg.config(text=("✓ Restaurado como estaba." if r.ok else "✗ " + r.msg), fg=GREEN if r.ok else RED)
        self.refresh_keep()
