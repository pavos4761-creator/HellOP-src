"""Página «Juegos»: biblioteca, perfil por juego y modo juego automático."""
import os
import subprocess
import tkinter as tk
from tkinter import filedialog, messagebox

import games
from util import DEMO
from widgets import (BG, CYAN, F, FG, GREEN, MUTED, PANEL, PANEL2, PINK, RED, VIOLET, YELLOW, Card, NeonButton,
                     ScrollFrame, WrapLabel, badge, checkbox, page_title)

SRC_COLOR = {"Steam": CYAN, "Epic": VIOLET, "Riot": RED, "Manual": YELLOW}


class GamesPage(tk.Frame):
    def __init__(self, parent, app):
        super().__init__(parent, bg=BG)
        self.app = app
        self.watcher = None
        top = tk.Frame(self, bg=BG)
        top.pack(fill="x", padx=26, pady=(22, 6))
        page_title(top, "Mis juegos",
                   "Tu biblioteca y el modo automático: abres un juego y HellOP lo optimiza solo; lo cierras y deja todo como estaba.",
                   accent=GREEN).pack(anchor="w")
        self.scroll = ScrollFrame(self)
        self.scroll.pack(fill="both", expand=True, padx=(26, 10), pady=(8, 10))
        root = self.scroll.inner

        a = Card(root, accent=GREEN, title="◉  Modo juego automático", pad=16)
        a.pack(fill="x", pady=(0, 12))
        WrapLabel(a.body, fg=MUTED, font=F(10),
                  text="Con esto activado, HellOP vigila tus juegos. Cuando abres uno de tu biblioteca activa el Modo Extremo con el perfil "
                       "de ESE juego (prioridad, procesos de fondo, plan de energía, temporizador…). Al cerrarlo lo devuelve todo a su sitio. "
                       "HellOP debe estar abierto (puede estar minimizado).").pack(fill="x", pady=(0, 10))
        row = tk.Frame(a.body, bg=PANEL)
        row.pack(fill="x")
        self.auto_btn = NeonButton(row, "▶   ACTIVAR MODO AUTOMÁTICO", self.toggle_auto, color=GREEN, filled=True, font=F(13, True), padx=30, pady=11)
        self.auto_btn.pack(side="left")
        self.state = tk.Label(row, text="Desactivado", font=F(11, True), fg=MUTED, bg=PANEL)
        self.state.pack(side="left", padx=16)

        lib = Card(root, accent=CYAN, title="▣  Mi biblioteca")
        lib.pack(fill="x", pady=(0, 12))
        bar = tk.Frame(lib.body, bg=PANEL)
        bar.pack(fill="x")
        NeonButton(bar, "↻  Buscar juegos (Steam, Epic)", self.scan, color=CYAN, filled=True, padx=14, pady=7, font=F(10, True)).pack(side="left")
        NeonButton(bar, "＋  Añadir un .exe", self.add_exe, color=VIOLET, padx=14, pady=7, font=F(10, True)).pack(side="left", padx=8)
        self.info = tk.Label(bar, text="", font=F(9), fg=MUTED, bg=PANEL)
        self.info.pack(side="left", padx=10)
        self.list = tk.Frame(lib.body, bg=PANEL)
        self.list.pack(fill="x", pady=(10, 0))

        WrapLabel(root, bg=BG, fg=MUTED, font=F(9),
                  text="Cada juego usa su propio perfil: pulsa «Perfil» para elegir qué se optimiza. Todo lo que cambia se restaura solo al cerrar el juego "
                       "(o al cerrar HellOP). No se toca nada del juego en sí: solo el sistema alrededor.").pack(fill="x", pady=(0, 14))
        self.render()
        self.after(1000, self._tick)

    # ------------------------------------------------------------------
    def boot(self):
        """Al abrir la app: si el modo automático estaba activado, lo reanuda."""
        if games.load()["auto"]:
            self._ensure_watcher().start()
            self._refresh_state()

    def _ensure_watcher(self):
        if self.watcher is None:
            bp = self.app.pages["booster"]
            self.watcher = games.Watcher(bp.b, log=lambda m: self.app.ui(bp._log, m), on_change=lambda: self.app.ui(self._changed))
        return self.watcher

    def _changed(self):
        self._refresh_state()
        bp = self.app.pages["booster"]
        bp.sync()

    def shutdown(self):
        if self.watcher:
            self.watcher.running = False
            if self.watcher.current:
                self.watcher.current = None

    # ------------------------------------------------------------------
    def toggle_auto(self):
        w = self._ensure_watcher()
        if w.running:
            games.set_auto(False)
            w.stop()
        else:
            if not games.load()["games"]:
                self.info.config(text="Primero busca o añade algún juego.", fg=YELLOW)
                return
            games.set_auto(True)
            w.start()
        self._refresh_state()

    def _refresh_state(self):
        w = self.watcher
        on = bool(w and w.running)
        self.auto_btn.set_text("■   DESACTIVAR MODO AUTOMÁTICO" if on else "▶   ACTIVAR MODO AUTOMÁTICO")
        self.auto_btn.set_color(PINK if on else GREEN)
        txt, secs = w.status() if w else ("Desactivado", None)
        if secs is not None:
            m, s = divmod(secs, 60)
            txt += f" · {m:02d}:{s:02d}"
        self.state.config(text=txt, fg=GREEN if on else MUTED)
        if on:
            self.app.status(txt)

    def _tick(self):
        if self.watcher and self.watcher.running:
            self._refresh_state()
        self.after(1000, self._tick)

    # ------------------------------------------------------------------
    def scan(self):
        self.info.config(text="Buscando…", fg=CYAN)
        self.app.bg(games.scan_all, self._scanned, lambda e: self.info.config(text=f"Error: {e}", fg=RED))

    def _scanned(self, new):
        n = len(games.load()["games"])
        self.info.config(text=(f"{new} juego(s) nuevo(s) · {n} en total" if n else
                               "No encontré juegos de Steam ni Epic. Puedes añadir un .exe a mano."), fg=GREEN if n else YELLOW)
        self.render()

    def add_exe(self):
        p = filedialog.askopenfilename(title="Elige el .exe del juego", filetypes=[("Programa", "*.exe")])
        if p:
            self.info.config(text="Añadido." if games.add_manual(p) else "Ese juego ya estaba en la lista.", fg=GREEN)
            self.render()

    def render(self):
        for w in self.list.winfo_children():
            w.destroy()
        gl = games.load()["games"]
        if not gl:
            WrapLabel(self.list, text="Aún no hay juegos. Pulsa «Buscar juegos» para detectar los de Steam y Epic, o añade un .exe.",
                      fg=MUTED, font=F(10)).pack(fill="x")
            return
        for g in gl:
            row = tk.Frame(self.list, bg=PANEL2)
            row.pack(fill="x", pady=3)
            inner = tk.Frame(row, bg=PANEL2)
            inner.pack(fill="x", padx=12, pady=9)
            left = tk.Frame(inner, bg=PANEL2)
            left.pack(side="left", fill="x", expand=True)
            head = tk.Frame(left, bg=PANEL2)
            head.pack(fill="x")
            tk.Label(head, text=g["name"], font=F(11, True), fg=FG, bg=PANEL2).pack(side="left")
            badge(head, g["source"].upper(), SRC_COLOR.get(g["source"], MUTED)).pack(side="left", padx=8)
            tk.Label(left, text="Perfil: " + games.summary(g["profile"]), font=F(9), fg=MUTED, bg=PANEL2, anchor="w").pack(fill="x")
            NeonButton(inner, "Quitar", lambda gid=g["id"]: self.remove(gid), color=MUTED, padx=10, pady=5, font=F(9, True)).pack(side="right", padx=(6, 0))
            NeonButton(inner, "Perfil", lambda gg=g: self.edit_profile(gg), color=VIOLET, padx=12, pady=5, font=F(9, True)).pack(side="right", padx=3)
            NeonButton(inner, "▶ Jugar", lambda gg=g: self.play(gg), color=GREEN, filled=True, padx=12, pady=5, font=F(9, True)).pack(side="right", padx=3)

    def remove(self, gid):
        games.remove(gid)
        self.render()

    def play(self, g):
        if not (self.watcher and self.watcher.running):
            games.set_auto(True)
            self._ensure_watcher().start()
            self._refresh_state()
        if DEMO or not g.get("launch"):
            self.info.config(text=f"(Demo) Abriría «{g['name']}» y se optimizaría solo.", fg=GREEN)
            return
        try:
            if g["launch"].startswith(("steam:", "com.epicgames")):
                os.startfile(g["launch"])                       # noqa: S606 (abre Steam/Epic con el juego)
            else:
                subprocess.Popen([g["launch"]], cwd=os.path.dirname(g["launch"]) or None)
            self.info.config(text=f"Abriendo «{g['name']}»… se optimizará solo en cuanto arranque.", fg=GREEN)
        except OSError as e:
            self.info.config(text=f"No pude abrirlo: {e}", fg=RED)

    # ------------------------------------------------------------------
    def edit_profile(self, g):
        win = tk.Toplevel(self)
        win.title(f"Perfil · {g['name']}")
        win.configure(bg=BG)
        win.geometry("640x520")
        win.transient(self.winfo_toplevel())
        tk.Label(win, text=g["name"], font=F(16, True), fg=FG, bg=BG).pack(anchor="w", padx=20, pady=(16, 0))
        tk.Label(win, text="Qué se optimiza cuando abres este juego:", font=F(10), fg=MUTED, bg=BG).pack(anchor="w", padx=20, pady=(2, 10))
        box = tk.Frame(win, bg=PANEL)
        box.pack(fill="x", padx=20)
        vars_ = {}
        for k, text, _d in games.OPTIONS:
            v = tk.BooleanVar(value=bool(g["profile"].get(k)))
            vars_[k] = v
            checkbox(box, text, v, font=F(10)).pack(fill="x", padx=14, pady=4)

        def current():
            return {k: v.get() for k, v in vars_.items()}

        def ok(everyone=False):
            games.set_profile(g["id"], current(), everyone)
            win.destroy()
            self.render()
        btns = tk.Frame(win, bg=BG)
        btns.pack(fill="x", padx=20, pady=16)
        NeonButton(btns, "Guardar", ok, color=GREEN, filled=True, padx=22, pady=8, font=F(11, True)).pack(side="left")
        NeonButton(btns, "Guardar y copiar a todos los juegos", lambda: ok(True), color=VIOLET, padx=16, pady=8, font=F(10, True)).pack(side="left", padx=10)
        NeonButton(btns, "Cancelar", win.destroy, color=MUTED, padx=16, pady=8, font=F(10, True)).pack(side="left")
