"""Página «Inicio»: panel de bienvenida con accesos rápidos y el estado de HellOP de un vistazo."""
import time
import tkinter as tk

import actions
import games
import logo_data
import updater
import version
from util import DEMO, is_admin
from widgets import themed_logo
from widgets import (BG, CYAN, F, FG, GREEN, MUTED, PANEL, PINK, RED, VIOLET, YELLOW, Card, NeonButton, ScrollFrame,
                     SparkField, WrapLabel, mix)

TILES = [
    ("hidden", "⌕", "Rendimiento oculto", "Encuentra lo que más FPS te cuesta: monitor a menos Hz, RAM, HDD, VBS…", PINK),
    ("analysis", "◎", "Analizar mi PC", "Procesador, placa, RAM, gráfica y discos, con consejos para tu equipo.", CYAN),
    ("optimize", "⚡", "Optimizar", "Gaming, Trabajo, Extremo o Limpieza profunda. Tú decides cada ajuste.", PINK),
    ("games", "▣", "Mis juegos", "Biblioteca y modo automático: se optimiza solo al abrir tu juego.", GREEN),
    ("fps", "▤", "FPS reales", "Mide FPS, 1 % low y tirones de tu juego y comprueba con números si un cambio ayudó.", CYAN),
    ("diag", "◈", "Diagnóstico", "Mide mientras juegas y te dice qué te frena y qué causa los tirones.", VIOLET),
    ("gameprof", "✧", "Ajustes de juego", "Baja sombras y efectos en Fortnite, VALORANT, LoL, Minecraft y CS2 con copia y deshacer.", PINK),
    ("tweaks", "☄", "Tweaks", "Ajustes de latencia y rendimiento en tres niveles de riesgo: tú eliges cuáles.", YELLOW),
    ("health", "♥", "Salud del PC", "Temperaturas, drivers y ping: lo que frena tus FPS sin que lo sepas.", GREEN),
    ("score", "★", "Puntuación HellOP", "La nota de tu PC con medalla y logros: te dice cuánto te falta para el oro.", YELLOW),
    ("cuello", "⬆", "Qué pieza mejorar", "Detecta qué te frena de verdad y te dice si te compensa gastar dinero.", PINK),
    ("bios", "◉", "BIOS y overclock", "Lo que no se puede cambiar desde Windows, explicado paso a paso.", YELLOW),
]


class HomePage(tk.Frame):
    def __init__(self, parent, app):
        super().__init__(parent, bg=BG)
        self.app = app
        self.scroll = ScrollFrame(self)
        self.scroll.pack(fill="both", expand=True, padx=(26, 10), pady=(18, 10))
        root = self.scroll.inner

        hero = Card(root, accent=CYAN, pad=18)
        hero.pack(fill="x", pady=(0, 14))
        row = tk.Frame(hero.body, bg=PANEL)
        row.pack(fill="x")
        self._logo = themed_logo(tk.PhotoImage(data=logo_data.LOGO_128))
        glow = SparkField(row, logo=self._logo, bg=PANEL, n=22)
        glow.configure(width=200, height=150)
        glow.pack(side="left")
        txt = tk.Frame(row, bg=PANEL)
        txt.pack(side="left", fill="x", expand=True, padx=(10, 0))
        title = tk.Frame(txt, bg=PANEL)
        title.pack(anchor="w")
        tk.Label(title, text="Hell", font=F(34, True), fg=FG, bg=PANEL).pack(side="left")
        tk.Label(title, text="OP", font=F(34, True), fg=CYAN, bg=PANEL).pack(side="left")
        tk.Label(title, text=f"  v{version.__version__}", font=F(11, True), fg=MUTED, bg=PANEL).pack(side="left", pady=(14, 0))
        WrapLabel(txt, text="Optimización extrema para gaming: analiza tu PC, quita lo que sobra, optimiza solo cuando juegas y "
                            "te dice qué te frena. Todo se puede deshacer.", fg=MUTED, font=F(11)).pack(fill="x", pady=(2, 12))
        btns = tk.Frame(txt, bg=PANEL)
        btns.pack(anchor="w")
        NeonButton(btns, "◎   ANALIZAR MI PC", lambda: app.show("analysis"), color=CYAN, filled=True, font=F(12, True), padx=24, pady=10).pack(side="left")
        NeonButton(btns, "▣   MIS JUEGOS", lambda: app.show("games"), color=GREEN, font=F(12, True), padx=22, pady=10).pack(side="left", padx=10)

        tk.Label(root, text="Qué quieres hacer", font=F(14, True), fg=FG, bg=BG, anchor="w").pack(fill="x", pady=(2, 8))
        grid = tk.Frame(root, bg=BG)
        grid.pack(fill="x")
        for c in range(3):
            grid.columnconfigure(c, weight=1, uniform="t")
        for i, (key, icon, name, desc, color) in enumerate(TILES):
            c = Card(grid, accent=color)
            c.grid(row=i // 3, column=i % 3, sticky="nsew", padx=(0, 12) if i % 3 < 2 else 0, pady=(0, 12))
            tk.Label(c.body, text=icon, font=F(24, True), fg=color, bg=PANEL).pack(anchor="w")
            tk.Label(c.body, text=name, font=F(12, True), fg=FG, bg=PANEL).pack(anchor="w", pady=(2, 2))
            WrapLabel(c.body, text=desc, fg=MUTED, font=F(9)).pack(fill="x")
            NeonButton(c.body, "Abrir  →", lambda k=key: app.show(k), color=color, padx=14, pady=6, font=F(10, True)).pack(anchor="w", pady=(10, 0))

        self.status = Card(root, accent=PINK, title="Estado de HellOP")
        self.status.pack(fill="x", pady=(2, 14))
        self.rows = {}
        for key, label in (("auto", "Modo juego automático"), ("last", "Última optimización"), ("upd", "Actualizaciones"),
                           ("adm", "Permisos de administrador")):
            r = tk.Frame(self.status.body, bg=PANEL)
            r.pack(fill="x", pady=3)
            dot = tk.Label(r, text="●", font=F(11), fg=MUTED, bg=PANEL)
            dot.pack(side="left")
            tk.Label(r, text=label, font=F(10), fg=MUTED, bg=PANEL, width=26, anchor="w").pack(side="left", padx=(8, 0))
            val = tk.Label(r, text="—", font=F(10, True), fg=FG, bg=PANEL, anchor="w")
            val.pack(side="left", fill="x", expand=True)
            self.rows[key] = (dot, val)

    # ------------------------------------------------------------------
    def _set(self, key, text, color):
        dot, val = self.rows[key]
        dot.config(fg=color)
        val.config(text=text, fg=FG if color != RED else RED)

    def on_show(self):
        w = self.app.pages["games"].watcher
        if w and w.running:
            self._set("auto", w.status()[0], GREEN)
        else:
            n = len(games.load()["games"])
            self._set("auto", "Desactivado" + (f" · {n} juegos en tu biblioteca" if n else " · añade tus juegos en «Mis juegos»"), MUTED)
        last = None
        if not DEMO:
            done = [e for e in actions.load_log() if not e.get("undone")]
            last = done[-1]["ts"] if done else None
        self._set("last", last or ("Ejemplo: hoy" if DEMO else "Aún no has optimizado nada"), GREEN if last or DEMO else YELLOW)
        info = self.app.pages["update"].info
        if info and info.get("newer"):
            self._set("upd", f"Hay una versión nueva: v{info['latest']}", YELLOW)
        elif info:
            self._set("upd", f"Estás al día (v{version.__version__})", GREEN)
        else:
            self._set("upd", f"v{version.__version__} · pulsa «Actualizaciones» para buscar", MUTED)
        self._set("adm", "Sí" if is_admin() or DEMO else "No: pulsa «Reabrir como administrador» arriba", GREEN if is_admin() or DEMO else RED)
