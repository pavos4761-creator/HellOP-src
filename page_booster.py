"""Página «Modo Extremo»: optimización EN VIVO mientras juegas."""
import tkinter as tk

import booster
from util import DEMO, fmt_bytes, is_admin
from widgets import (BG, CYAN, F, FG, GREEN, MUTED, PANEL, PANEL2, PINK, RED, VIOLET, YELLOW, Card, NeonButton,
                     ScrollFrame, WrapLabel, checkbox, page_title)

OPTIONS = [
    ("timer", "Temporizador de Windows a 0,5 ms (la latencia del planificador baja de 15,6 ms a 0,5 ms)", True),
    ("game_prio", "Prioridad ALTA para tu juego", True),
    ("bg_prio", "Prioridad baja para todo lo de fondo (navegador, launchers, etc.)", True),
    ("bg_ram", "Liberar la RAM que usan los programas de fondo", True),
    ("services", "Pausar servicios que despiertan al disco y la CPU (SysMain, búsqueda, Windows Update…) · necesita administrador", True),
    ("dns", "Vaciar la caché DNS", False),
]


class BoosterPage(tk.Frame):
    def __init__(self, parent, app):
        super().__init__(parent, bg=BG)
        self.app = app
        self.b = booster.Booster()
        self.vars = {k: tk.BooleanVar(value=d) for k, _t, d in OPTIONS}
        self.no_game = tk.BooleanVar(value=False)
        self.games = []
        self.busy = False

        top = tk.Frame(self, bg=BG)
        top.pack(fill="x", padx=26, pady=(22, 6))
        page_title(top, "Modo Extremo",
                   "Optimiza TU PC mientras juegas y lo deja todo como estaba al terminar. Mantén esta app abierta.",
                   accent=PINK).pack(anchor="w")
        self.scroll = ScrollFrame(self)
        self.scroll.pack(fill="both", expand=True, padx=(26, 10), pady=(8, 10))
        self.build(self.scroll.inner)
        self.refresh_games()
        self._loop()

    # ------------------------------------------------------------------
    def build(self, root):
        c1 = Card(root, accent=CYAN, title="1 · Elige tu juego")
        c1.pack(fill="x", pady=(0, 12))
        WrapLabel(c1.body, fg=MUTED, font=F(9),
                  text="Abre tu juego primero y pulsa «Actualizar». Si no aparece, escríbeme su nombre de proceso en el Administrador de tareas.").pack(fill="x", pady=(0, 6))
        self.lb = tk.Listbox(c1.body, height=7, bg=PANEL2, fg=FG, selectbackground="#1d3b66", selectforeground="#ffffff",
                             highlightthickness=1, highlightbackground="#25254a", highlightcolor=CYAN, bd=0,
                             font=("Consolas", 10), activestyle="none", exportselection=False)
        self.lb.pack(fill="x")
        row = tk.Frame(c1.body, bg=PANEL)
        row.pack(fill="x", pady=(8, 0))
        NeonButton(row, "↻  Actualizar lista", self.refresh_games, color=CYAN, padx=12, pady=6, font=F(9, True)).pack(side="left")
        checkbox(row, "Sin juego concreto (solo limpiar el fondo)", self.no_game, font=F(9)).pack(side="left", padx=14, fill="x", expand=True)

        c2 = Card(root, accent=VIOLET, title="2 · Qué quieres que haga")
        c2.pack(fill="x", pady=(0, 12))
        for k, text, _d in OPTIONS:
            checkbox(c2.body, text, self.vars[k], font=F(10)).pack(fill="x", pady=3)

        c3 = Card(root, accent=PINK, title="3 · Activar", pad=16)
        c3.pack(fill="x", pady=(0, 12))
        self.btn = NeonButton(c3.body, "☢   ACTIVAR MODO EXTREMO", self.toggle, color=PINK, filled=True, font=F(15, True),
                              padx=40, pady=14)
        self.btn.pack(anchor="w")
        if not is_admin() and not DEMO:
            WrapLabel(c3.body, fg=YELLOW, font=F(9),
                      text="Sin administrador no se pueden pausar servicios ni cambiar la prioridad de algunos procesos.").pack(fill="x", pady=(8, 0))

        grid = tk.Frame(c3.body, bg=PANEL)
        grid.pack(fill="x", pady=(14, 0))
        self.tiles = {}
        specs = [("timer", "TEMPORIZADOR", CYAN), ("game", "PRIORIDAD DEL JUEGO", PINK), ("low", "FONDO FRENADO", VIOLET),
                 ("ram", "RAM LIBERADA", GREEN), ("svc", "SERVICIOS EN PAUSA", YELLOW), ("time", "TIEMPO ACTIVO", MUTED)]
        for i, (key, label, col) in enumerate(specs):
            grid.columnconfigure(i % 3, weight=1, uniform="t")
            f = tk.Frame(grid, bg=PANEL2)
            f.grid(row=i // 3, column=i % 3, sticky="nsew", padx=4, pady=4)
            tk.Label(f, text=label, font=F(8, True), fg=MUTED, bg=PANEL2).pack(anchor="w", padx=10, pady=(8, 0))
            v = tk.Label(f, text="—", font=F(16, True), fg=col, bg=PANEL2)
            v.pack(anchor="w", padx=10, pady=(0, 8))
            self.tiles[key] = v

        self.log = tk.Text(c3.body, height=8, bg="#0b0b17", fg=FG, font=("Consolas", 9), bd=0, highlightthickness=1,
                           highlightbackground="#25254a", wrap="word", state="disabled")
        self.log.pack(fill="x", pady=(12, 0))
        self._log("Listo. Elige tu juego y pulsa ACTIVAR.")

        WrapLabel(root, bg=BG, fg=MUTED, font=F(9),
                  text="Honestidad: esto no crea FPS de la nada. Reduce latencia y tirones quitando lo que compite con tu juego. "
                       "En un PC ya ligero la mejora es pequeña; en uno con muchas cosas abiertas se nota más. "
                       "Al desactivar (o cerrar la app) todo vuelve a su estado normal.").pack(fill="x", pady=(0, 14))

    # ------------------------------------------------------------------
    def _log(self, msg):
        self.log.config(state="normal")
        self.log.insert("end", msg + "\n")
        self.log.see("end")
        self.log.config(state="disabled")

    def refresh_games(self):
        self.games = booster.candidate_games()
        self.lb.delete(0, "end")
        for name, rss, pid in self.games:
            self.lb.insert("end", f"{name:<44} {fmt_bytes(rss):>9}   pid {pid}")
        if self.games:
            self.lb.selection_set(0)

    def toggle(self):
        if self.busy:
            return
        if self.b.active:
            self.deactivate()
        else:
            self.activate()

    def activate(self):
        game = None
        if not self.no_game.get():
            sel = self.lb.curselection()
            if not sel:
                self._log("⚠ Elige un juego de la lista (o marca «Sin juego concreto»).")
                return
            game = self.games[sel[0]][0]
        opts = {k: v.get() for k, v in self.vars.items()}
        self.busy = True
        self.btn.set_enabled(False)
        self._log("Activando… (mido el fondo, puede tardar un segundo)")
        self.app.bg(lambda: self.b.start(game, opts, lambda m: self.app.ui(self._log, m)), self._activated,
                    lambda e: self._failed(e))

    def _activated(self, _r):
        self.busy = False
        self.btn.set_enabled(True)
        self.btn.set_text("■   DESACTIVAR Y DEJARLO TODO COMO ESTABA")
        self.btn.set_color(GREEN)
        self.app.status("Modo Extremo ACTIVO")

    def _failed(self, e):
        self.busy = False
        self.btn.set_enabled(True)
        self._log(f"✗ Error: {type(e).__name__}: {e}")

    def deactivate(self):
        self.busy = True
        self.btn.set_enabled(False)
        self.app.bg(lambda: self.b.stop(lambda m: self.app.ui(self._log, m)), self._deactivated, lambda e: self._failed(e))

    def _deactivated(self, _r):
        self.busy = False
        self.btn.set_enabled(True)
        self.btn.set_text("☢   ACTIVAR MODO EXTREMO")
        self.btn.set_color(PINK)
        for t in self.tiles.values():
            t.config(text="—")
        self.app.status("Modo Extremo desactivado")

    # ------------------------------------------------------------------
    def _loop(self):
        if self.b.active:
            s = self.b.stats()
            self.tiles["timer"].config(text=f"{s['timer']:.2f} ms" if s["timer"] else "—")
            self.tiles["game"].config(text=s["game_prio"])
            self.tiles["low"].config(text=f"{s['lowered']} procesos")
            self.tiles["ram"].config(text=fmt_bytes(s["freed"]))
            self.tiles["svc"].config(text=str(s["services"]))
            m, sec = divmod(s["elapsed"], 60)
            self.tiles["time"].config(text=f"{m:02d}:{sec:02d}")
        self.after(1000, self._loop)

    def shutdown(self):
        """Se llama al cerrar la app: deja todo como estaba."""
        if self.b.active:
            self.b.stop()
