"""Página «Inicio» (diseño «neón cristal»): saludo, anillo con la nota de tu PC, datos en vivo y accesos rápidos."""
import math
import time
import tkinter as tk

import actions
import games
import updater
import version
from util import DEMO, is_admin
from widgets import (BG, BORDER, CYAN, F, FG, GREEN, MUTED, PANEL, PINK, RED, VIOLET, YELLOW, Card, NeonButton, PillBar,
                     ScrollFrame, WrapLabel, badge, mix, round_rect)

MAS = [
    ("analysis", "◎", "Analizar mi PC", "Procesador, placa, RAM, gráfica y discos, con consejos para tu equipo.", CYAN),
    ("diag", "◈", "Diagnóstico", "Mide mientras juegas y te dice qué te frena y qué causa los tirones.", VIOLET),
    ("gameprof", "✧", "Ajustes de juego", "Baja sombras y efectos en Fortnite, VALORANT, LoL, Minecraft y CS2 con copia y deshacer.", PINK),
    ("health", "♥", "Salud del PC", "Temperaturas, drivers y ping: lo que frena tus FPS sin que lo sepas.", GREEN),
    ("score", "★", "Puntuación HellOP", "La nota de tu PC con medalla y logros: te dice cuánto te falta para el oro.", YELLOW),
    ("cuello", "⬆", "Qué pieza mejorar", "Detecta qué te frena de verdad y te dice si te compensa gastar dinero.", PINK),
    ("bios", "◉", "BIOS y overclock", "Lo que no se puede cambiar desde Windows, explicado paso a paso.", YELLOW),
]



GRANDES = [   # (página, símbolo, título, texto, color 1, color 2)
    ("optimize", "⚡", "Optimizar", "Gaming, Trabajo o Extremo. Tú decides cada ajuste.", CYAN, PINK),
    ("games", "▣", "Mis juegos", "Se optimiza solo al abrir tu juego.", "#3b9eff", "#38e1ff"),
    ("fps", "▤", "FPS reales", "Mide FPS y tirones y comprueba si un cambio ayudó.", "#ff8a3d", "#ff3b5c"),
    ("tweaks", "☄", "Tweaks", "Ajustes de latencia en tres niveles de riesgo.", "#ffc233", "#ff9f1c"),
]


class Anillo(tk.Canvas):
    """Anillo con degradado que se llena hasta la nota (0-100); en el centro, la nota y la medalla."""
    D = 170

    def __init__(self, parent, bg):
        super().__init__(parent, width=self.D, height=self.D, bg=bg, highlightthickness=0, bd=0)
        self.bg0, self.valor, self.mostrado, self.medalla, self._job = bg, 0, 0.0, "", None
        self._draw()

    def poner(self, valor, medalla):
        self.valor, self.medalla = valor, medalla
        if self._job is None:
            self._job = self.after(16, self._anima)

    def _anima(self):
        self._job = None
        try:
            self.mostrado += (self.valor - self.mostrado) * 0.12
            if abs(self.valor - self.mostrado) < 0.4:
                self.mostrado = float(self.valor)
            else:
                self._job = self.after(16, self._anima)
            self._draw()
        except tk.TclError:
            pass

    def _draw(self):
        self.delete("all")
        d, g, r = self.D, 13, self.D / 2 - 14
        c = d / 2
        self.create_oval(c - r, c - r, c + r, c + r, outline=mix(self.bg0, "#ffffff", 0.09), width=g)
        n = int(self.mostrado / 100 * 72)
        for i in range(n):
            col = mix(CYAN, PINK, i / 72)
            self.create_arc(c - r, c - r, c + r, c + r, start=90 - i * 5 - 5.6, extent=5.6, style="arc", outline=col, width=g)
        if n:
            for ang, col in ((90, CYAN), (90 - n * 5, mix(CYAN, PINK, n / 72))):
                x, y = c + r * math.cos(math.radians(ang)), c - r * math.sin(math.radians(ang))
                self.create_oval(x - g / 2, y - g / 2, x + g / 2, y + g / 2, fill=col, outline="")
        shown = round(self.mostrado) if self.medalla else "—"
        self.create_text(c, c - 6, text=str(shown), fill=FG, font=F(32, True))
        self.create_text(c, c + 26, text=self.medalla.upper(), fill=CYAN, font=F(9, True))


class Tarjeta(tk.Canvas):
    """Tarjeta grande clicable: icono con color, título y texto. Se ilumina al pasar el ratón."""
    H = 150

    def __init__(self, parent, simbolo, titulo, texto, c1, c2, command):
        super().__init__(parent, bg=BG, height=self.H, highlightthickness=0, bd=0, cursor="hand2")
        self.d = (simbolo, titulo, texto, c1, c2)
        self.hov = False
        self.bind("<Configure>", lambda e: self._draw())
        self.bind("<Enter>", lambda e: self._h(True))
        self.bind("<Leave>", lambda e: self._h(False))
        self.bind("<Button-1>", lambda e: command())

    def _h(self, on):
        self.hov = on
        self._draw()

    def _draw(self):
        try:
            self.delete("all")
            w = max(80, self.winfo_width())
            simbolo, titulo, texto, c1, c2 = self.d
            col = mix(c1, c2, 0.5)
            round_rect(self, 1, 1, w - 1, self.H - 1, 24, fill=mix(PANEL, col, 0.12 if self.hov else 0.0),
                       outline=mix(BORDER, col, 0.7 if self.hov else 0.0))
            round_rect(self, 14, 14, 62, 62, 17, fill=mix(PANEL, col, 0.28), outline="")           # brillo
            round_rect(self, 18, 18, 58, 58, 14, fill=col, outline="")
            round_rect(self, 18, 18, 58, 38, 12, fill=mix(c1, "#ffffff", 0.18), outline="")         # reflejo
            self.create_text(38, 38, text=simbolo, fill="#ffffff", font=F(16, True))
            self.create_text(18, 82, text=titulo, anchor="w", fill=FG, font=F(12, True))
            fnt = F(9)
            import tkinter.font as tkfont
            f = tkfont.Font(font=fnt)
            lineas, linea = [], ""
            for p in texto.split():
                if f.measure((linea + " " + p).strip()) > w - 36:
                    lineas.append(linea)
                    linea = p
                else:
                    linea = (linea + " " + p).strip()
            lineas.append(linea)
            for i, l in enumerate(lineas[:3]):
                self.create_text(18, 104 + i * 15, text=l, anchor="w", fill=MUTED, font=fnt)
        except tk.TclError:
            pass


class HomePage(tk.Frame):
    def __init__(self, parent, app):
        super().__init__(parent, bg=BG)
        self.app = app
        self.scroll = ScrollFrame(self)
        self.scroll.pack(fill="both", expand=True, padx=(26, 10), pady=(18, 10))
        root = self.scroll.inner

        # ---- saludo, estado de administrador y asistente ----
        top = tk.Frame(root, bg=BG)
        top.pack(fill="x", pady=(0, 14))
        tk.Label(top, text=self._saludo(), font=F(22, True), fg=FG, bg=BG).pack(side="left")
        ok = is_admin() or DEMO
        badge(top, "● Administrador" if ok else "● Sin administrador", GREEN if ok else RED, bg=BG).pack(side="left", padx=14, pady=(8, 0))
        import licencia
        from cajas import CajaAsistente, CajaLicencia
        self.caja_asist = CajaAsistente(top, app.abrir_asistente, fondo=BG, ancho=190)
        self.caja_asist.pack(side="right")
        self.caja_lic = CajaLicencia(top, lambda: app.show("license"), fondo=BG, ancho=230)
        self.caja_lic.pack(side="right", padx=(0, 10))
        self.caja_lic.set(licencia.status())

        # ---- tarjeta principal: anillo + mensaje + datos en vivo ----
        fill = mix(PANEL, CYAN, 0.07)
        hero = Card(root, strip=False, radius=30, pad=22, fill=fill, line=mix(BORDER, CYAN, 0.65),
                    orbs=[(0.08, 0.1, 260, CYAN, 0.30), (0.96, 0.95, 240, PINK, 0.26)])
        hero.pack(fill="x", pady=(0, 14))
        fila = tk.Frame(hero.body, bg=fill)
        fila.pack(fill="x")
        self.anillo = Anillo(fila, fill)
        self.anillo.pack(side="left", padx=(4, 24))
        datos = tk.Frame(fila, bg=fill)
        datos.pack(side="right", padx=(20, 4), anchor="center")
        self.stat = {}
        for key, label in (("cpu", "Procesador"), ("ram", "Memoria RAM"), ("disk", "Disco libre"), ("temp", "Temperatura")):
            f = tk.Frame(datos, bg=fill)
            f.pack(fill="x", pady=5)
            r = tk.Frame(f, bg=fill)
            r.pack(fill="x")
            tk.Label(r, text=label, font=F(9, True), fg=MUTED, bg=fill).pack(side="left")
            v = tk.Label(r, text="—", font=F(9, True), fg=FG, bg=fill)
            v.pack(side="right")
            bar = PillBar(f, color=CYAN, bg=fill, height=6)
            bar.pack(fill="x", pady=(4, 0))
            self.stat[key] = (v, bar)
        tk.Frame(datos, bg=fill, width=210, height=1).pack()

        centro = tk.Frame(fila, bg=fill)
        centro.pack(side="left", fill="x", expand=True)
        tk.Label(centro, text="PUNTUACIÓN HELLOP", font=F(9, True), fg=CYAN, bg=fill, anchor="w").pack(fill="x")
        self.lbl_nota = tk.Label(centro, text="Midiendo tu PC…", font=F(20, True), fg=FG, bg=fill, anchor="w", justify="left")
        self.lbl_nota.pack(fill="x", pady=(4, 0))
        self.lbl_desc = WrapLabel(centro, text="Esto tarda unos segundos: miro tu monitor, la RAM, el arranque y el espacio.", bg=fill, font=F(10), fg=MUTED)
        self.lbl_desc.pack(fill="x", pady=(6, 12))
        bt = tk.Frame(centro, bg=fill)
        bt.pack(anchor="w")
        NeonButton(bt, "Mejorar ahora", lambda: app.show("optimize"), color=CYAN, filled=True, font=F(11, True), padx=22, pady=9).pack(side="left")
        NeonButton(bt, "Ver qué me falta", lambda: app.show("score"), color=MUTED, font=F(11, True), padx=18, pady=9).pack(side="left", padx=10)
        # ---- 4 accesos grandes ----
        gr = tk.Frame(root, bg=BG)
        gr.pack(fill="x", pady=(0, 18))
        for c in range(4):
            gr.columnconfigure(c, weight=1, uniform="g")
        for i, (key, sim, tit, txt, c1, c2) in enumerate(GRANDES):
            Tarjeta(gr, sim, tit, txt, c1, c2, lambda k=key: app.show(k)).grid(row=0, column=i, sticky="nsew", padx=(0, 12) if i < 3 else 0)

        tk.Label(root, text="Más herramientas", font=F(13, True), fg=FG, bg=BG, anchor="w").pack(fill="x", pady=(0, 8))
        grid = tk.Frame(root, bg=BG)
        grid.pack(fill="x")
        for c in range(3):
            grid.columnconfigure(c, weight=1, uniform="t")
        for i, (key, icon, name, desc, color) in enumerate(MAS):
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
        self._nota = None
        self._cargando = set()
        self._temp_ok = False
        self._nota_t = 0

    # ------------------------------------------------------------------
    @staticmethod
    def _saludo():
        hr = time.localtime().tm_hour
        return "Buenos días" if 6 <= hr < 13 else "Buenas tardes" if 13 <= hr < 21 else "Buenas noches"

    def _live(self):
        import psutil
        import sysinfo
        vols = [(f / t * 100) for _m, f, t in sysinfo.volumes() if t]
        return psutil.cpu_percent(interval=0.3), psutil.virtual_memory().percent, (min(vols) if vols else None)

    def _live_done(self, r):
        cpu, ram, low = r
        for key, val in (("cpu", cpu), ("ram", ram)):
            v, b = self.stat[key]
            v.config(text=f"{val:.0f} %")
            b.set(val, RED if val >= 90 else YELLOW if val >= 75 else CYAN)
        if low is not None:
            v, b = self.stat["disk"]
            v.config(text=f"{low:.0f} %")
            b.set(low, RED if low < 15 else YELLOW if low < 25 else CYAN)

    def _temp_done(self, rows):
        cpu = [x["value"] for x in rows if x.get("kind") == "cpu"]
        v, b = self.stat["temp"]
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
        nombre, _col = res["medal"]
        sig = next(((lim, n) for lim, n, _c in reversed(puntuacion.MEDALLAS) if lim > sc), None)
        self.anillo.poner(sc, nombre)
        self.lbl_nota.config(text=f"Tu PC está al {sc} %." + (f"\nA {sig[0] - sc} puntos de {sig[1]}." if sig else "\n¡Máximo rango!"))
        top = [t for t, _p, _f in res["perdidos"][:2]]
        self.lbl_desc.config(text=("Lo que más te frena: " + "; ".join(top) + ". Se arregla en un par de minutos.") if top
                             else "Todo está en orden. No hay nada que te frene ahora mismo.")

    def _set(self, key, text, color):
        dot, val = self.rows[key]
        dot.config(fg=color)
        val.config(text=text, fg=FG if color != RED else RED)

    def on_show(self):
        self.app.bg(self._live, self._live_done, lambda e: None)
        if not self._temp_ok and "temp" not in self._cargando:
            self._cargando.add("temp")
            self._temp_ok = True
            import sysinfo
            self.app.bg(sysinfo.read_temps, lambda r: (self._cargando.discard("temp"), self._temp_done(r)),
                        lambda e: (self._cargando.discard("temp"), self._temp_done([])))
        if "nota" not in self._cargando and (self._nota is None or time.time() - self._nota_t > 600):
            self._cargando.add("nota")
            self._nota_t = time.time()
            import puntuacion
            self.app.bg(lambda: puntuacion.calcular(), lambda r: (self._cargando.discard("nota"), self._nota_done(r)),
                        lambda e: self._cargando.discard("nota"))
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
