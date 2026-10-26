"""Página «Inicio»: panel de bienvenida con accesos rápidos y el estado de HellOP de un vistazo."""
import time
import tkinter as tk

import actions
import games
import logo_data
import updater
import version
from util import DEMO, is_admin
from widgets import badge, themed_logo
from widgets import (BG, BORDER, CYAN, F, FG, GREEN, MUTED, PANEL, PINK, RED, VIOLET, YELLOW, Card, NeonButton, PillBar,
                     ScrollFrame, SparkField, WrapLabel, mix)

TILES = [
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

        # ---- cabecera estilo «centro de mando»: saludo, nota de tu PC y dos botones ----
        top = tk.Frame(root, bg=BG)
        top.pack(fill="x", pady=(0, 14))
        izq = tk.Frame(top, bg=BG)
        izq.pack(side="left")
        tk.Label(izq, text=self._saludo(), font=F(10), fg=MUTED, bg=BG, anchor="w").pack(anchor="w")
        self.lbl_nota = tk.Label(izq, text="Tu PC: midiendo…", font=F(24, True), fg=FG, bg=BG, anchor="w")
        self.lbl_nota.pack(anchor="w")
        der = tk.Frame(top, bg=BG)
        der.pack(side="right")
        NeonButton(der, "Ver informe", lambda: app.show("score"), color=MUTED, font=F(10, True), padx=18, pady=8).pack(side="left", padx=(0, 8))
        NeonButton(der, "Optimizar ahora", lambda: app.show("optimize"), color=CYAN, filled=True, font=F(10, True), padx=20, pady=8).pack(side="left")

        # ---- 4 datos en vivo ----
        kp = tk.Frame(root, bg=BG)
        kp.pack(fill="x", pady=(0, 14))
        for c in range(4):
            kp.columnconfigure(c, weight=1, uniform="k")
        self.kpi = {}
        for i, (key, label, color) in enumerate((("proc", "Procesos en segundo plano", CYAN), ("ram", "RAM libre", PINK),
                                                 ("temp", "Temperatura CPU", YELLOW), ("disk", "Espacio libre (peor disco)", VIOLET))):
            c = Card(kp, strip=False, radius=20, pad=14, fill=PANEL)
            c.grid(row=0, column=i, sticky="nsew", padx=(0, 10) if i < 3 else 0)
            tk.Label(c.body, text=label, font=F(9), fg=MUTED, bg=PANEL, anchor="w").pack(fill="x")
            v = tk.Label(c.body, text="—", font=F(18, True), fg=FG, bg=PANEL, anchor="w")
            v.pack(fill="x", pady=(2, 6))
            bar = PillBar(c.body, color=color, bg=PANEL)
            bar.pack(fill="x")
            self.kpi[key] = (v, bar)

        # ---- recomendado + rango y avisos ----
        mid = tk.Frame(root, bg=BG)
        mid.pack(fill="x", pady=(0, 14))
        mid.columnconfigure(0, weight=3, uniform="m")
        mid.columnconfigure(1, weight=2, uniform="m")
        self.rec = Card(mid, strip=False, radius=24, pad=16)
        self.rec.grid(row=0, column=0, sticky="nsew", padx=(0, 12))
        cab = tk.Frame(self.rec.body, bg=PANEL)
        cab.pack(fill="x")
        tk.Label(cab, text="Recomendado para ti", font=F(12, True), fg=FG, bg=PANEL).pack(side="left")
        ver = tk.Label(cab, text="Ver todo", font=F(9, True), fg=CYAN, bg=PANEL, cursor="hand2")
        ver.pack(side="right")
        ver.bind("<Button-1>", lambda e: app.show("tweaks"))
        self.rec_list = tk.Frame(self.rec.body, bg=PANEL)
        self.rec_list.pack(fill="x", pady=(8, 0))
        self.rec_msg = tk.Label(self.rec_list, text="Buscando ajustes seguros para tu equipo…", font=F(10), fg=MUTED, bg=PANEL, anchor="w")
        self.rec_msg.pack(fill="x", pady=6)
        der2 = tk.Frame(mid, bg=BG)
        der2.grid(row=0, column=1, sticky="nsew")
        self.rango = Card(der2, strip=False, radius=24, pad=16, fill=mix(PANEL, CYAN, 0.16), line=mix(BORDER, CYAN, 0.5))
        self.rango.pack(fill="x", pady=(0, 12))
        rf = mix(PANEL, CYAN, 0.16)
        tk.Label(self.rango.body, text="RANGO", font=F(9, True), fg=CYAN, bg=rf, anchor="w").pack(fill="x")
        self.lbl_rango = tk.Label(self.rango.body, text="—", font=F(26, True), fg=FG, bg=rf, anchor="w")
        self.lbl_rango.pack(fill="x")
        self.lbl_rango2 = WrapLabel(self.rango.body, text="Calculando tu puntuación…", font=F(9), fg=MUTED, bg=rf)
        self.lbl_rango2.pack(fill="x", pady=(2, 8))
        self.bar_rango = PillBar(self.rango.body, color=CYAN, bg=rf, height=8)
        self.bar_rango.pack(fill="x")
        self.avisos = Card(der2, strip=False, radius=24, pad=16)
        self.avisos.pack(fill="x")
        tk.Label(self.avisos.body, text="Avisos", font=F(12, True), fg=FG, bg=PANEL, anchor="w").pack(fill="x", pady=(0, 6))
        self.av_list = tk.Frame(self.avisos.body, bg=PANEL)
        self.av_list.pack(fill="x")
        self._nota = None
        self._recs_t = 0
        self._cargando = set()

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
    @staticmethod
    def _saludo():
        hr = time.localtime().tm_hour
        return "Buenos días" if 6 <= hr < 13 else "Buenas tardes" if 13 <= hr < 21 else "Buenas noches"

    def _live(self):
        """Procesos, RAM y disco (rápidos). La temperatura y la nota van aparte, en segundo plano."""
        import psutil
        import sysinfo
        vm = psutil.virtual_memory()
        vols = [(f / t * 100, f) for _m, f, t in sysinfo.volumes() if t]
        low = min(vols) if vols else None
        return len(psutil.pids()), vm.available / 1024 ** 3, vm.percent, low

    def _live_done(self, r):
        n, libre, usado, low = r
        v, b = self.kpi["proc"]
        v.config(text=str(n))
        b.set(min(100, n / 3))
        v, b = self.kpi["ram"]
        v.config(text=f"{libre:.1f} GB".replace(".", ","))
        b.set(100 - usado)
        v, b = self.kpi["disk"]
        if low:
            v.config(text=f"{low[0]:.0f} %")
            b.set(low[0], RED if low[0] < 15 else YELLOW if low[0] < 25 else VIOLET)

    def _temp_done(self, rows):
        cpu = [x["value"] for x in rows if x.get("kind") == "cpu"]
        v, b = self.kpi["temp"]
        if cpu:
            t = max(cpu)
            v.config(text=f"{t:.0f} °C")
            b.set(t, RED if t >= 85 else YELLOW if t >= 75 else GREEN)
        else:
            v.config(text="No disponible")
            b.set(0)

    def _nota_done(self, res):
        import puntuacion
        self._nota = res
        sc = res["score"]
        nombre, col = res["medal"]
        self.lbl_nota.config(text=f"Tu PC está al {sc} %")
        self.lbl_rango.config(text=nombre)
        sig = next(((lim, n) for lim, n, _c in reversed(puntuacion.MEDALLAS) if lim > sc), None)
        p = len(res["perdidos"])
        if sig:
            self.lbl_rango2.config(text=f"Te faltan {sig[0] - sc} puntos para {sig[1]}." + (f" Hay {p} cosas que mejorar." if p else ""))
        else:
            self.lbl_rango2.config(text="¡Máximo rango! Tu PC está al tope.")
        self.bar_rango.set(sc)
        for w in self.av_list.winfo_children():
            w.destroy()
        for titulo, pts, fix in res["perdidos"][:3]:
            fila = tk.Frame(self.av_list, bg=PANEL, cursor="hand2" if fix else "")
            fila.pack(fill="x", pady=2)
            tk.Label(fila, text="▲", font=F(9), fg=YELLOW, bg=PANEL).pack(side="left", anchor="n")
            WrapLabel(fila, text=f"{titulo} (−{pts})", font=F(9), fg=MUTED).pack(side="left", fill="x", expand=True, padx=(6, 0))
            if fix and fix[0] == "goto":
                fila.bind("<Button-1>", lambda e, d=fix[1]: self.app.show(d))
        if not res["perdidos"]:
            tk.Label(self.av_list, text="●  Todo en orden, no hay avisos.", font=F(9), fg=GREEN, bg=PANEL, anchor="w").pack(fill="x")

    def _recs_done(self, acts):
        self._cargando.discard("recs")
        self._recs_t = time.time()
        for w in self.rec_list.winfo_children():
            w.destroy()
        seguros = [a for a in acts if a.risk == "bajo" and a.reversible][:4]
        if not seguros:
            tk.Label(self.rec_list, text="●  No te queda ningún ajuste seguro por aplicar.", font=F(10), fg=GREEN, bg=PANEL,
                     anchor="w").pack(fill="x", pady=6)
            return
        for a in seguros:
            fila = tk.Frame(self.rec_list, bg=PANEL)
            fila.pack(fill="x", pady=4)
            tk.Label(fila, text="⚡", font=F(13, True), fg=CYAN, bg=PANEL, width=2).pack(side="left")
            col = tk.Frame(fila, bg=PANEL)
            col.pack(side="left", fill="x", expand=True, padx=(4, 8))
            tk.Label(col, text=a.title, font=F(10, True), fg=FG, bg=PANEL, anchor="w").pack(fill="x")
            WrapLabel(col, text=a.desc, font=F(8), fg=MUTED).pack(fill="x")
            badge(fila, "SEGURO", GREEN, bg=PANEL).pack(side="left", padx=6)
            NeonButton(fila, "Aplicar", lambda x=a, f=fila: self._aplicar(x, f), color=CYAN, padx=12, pady=4, font=F(9, True)).pack(side="left")

    def _aplicar(self, a, fila):
        if a.needs_admin and not (is_admin() or DEMO):
            self.app.status("Ese ajuste necesita administrador: pulsa «Reabrir como administrador» arriba.")
            return
        for w in fila.winfo_children():
            if isinstance(w, tk.Canvas):
                w.destroy()
        tk.Label(fila, text="Aplicando…", font=F(9), fg=CYAN, bg=PANEL).pack(side="left", padx=8)

        def listo(r):
            self.app.status(("✓ Aplicado: " if r.ok else "No se pudo: ") + a.title + ("" if r.ok else f" ({r.msg[:60]})") +
                            ("  ·  se puede deshacer en el Historial" if r.ok else ""))
            self._recs_t = 0
            self._pedir_recs()
        self.app.bg(lambda: actions.execute(a), listo, lambda e: self.app.status(f"Error: {e}"))

    def _pedir_recs(self):
        if "recs" in self._cargando:
            return
        self._cargando.add("recs")
        import tweaks
        self.app.bg(lambda: tweaks.collect(), self._recs_done, lambda e: (self._cargando.discard("recs"), self._recs_done([])))

    def _set(self, key, text, color):
        dot, val = self.rows[key]
        dot.config(fg=color)
        val.config(text=text, fg=FG if color != RED else RED)

    def on_show(self):
        self.app.bg(self._live, self._live_done, lambda e: None)
        if "temp" not in self._cargando and not getattr(self, "_temp_ok", False):
            self._cargando.add("temp")
            import sysinfo
            self._temp_ok = True
            self.app.bg(sysinfo.read_temps, lambda r: (self._cargando.discard("temp"), self._temp_done(r)),
                        lambda e: (self._cargando.discard("temp"), self._temp_done([])))
        if "nota" not in self._cargando and (self._nota is None or time.time() - getattr(self, "_nota_t", 0) > 600):
            self._cargando.add("nota")
            import puntuacion
            self._nota_t = time.time()
            self.app.bg(lambda: puntuacion.calcular(), lambda r: (self._cargando.discard("nota"), self._nota_done(r)),
                        lambda e: self._cargando.discard("nota"))
        if time.time() - self._recs_t > 600:
            self._pedir_recs()
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
