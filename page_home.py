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
                     ScrollFrame, WrapLabel, badge, esquinas, glow_image, mix, round_rect)

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


class _Txt:
    """Texto de la tarjeta principal: se cambia con .config(text=...) como una etiqueta."""

    def __init__(self, hero, texto=""):
        self.hero, self.texto = hero, texto

    def config(self, text=None, **kw):
        if text is not None and text != self.texto:
            self.texto = text
            self.hero.pinta_texto()


class _Dato:
    """Barra de datos en vivo (valor + barra) de la tarjeta principal."""

    def __init__(self, hero, nombre):
        self.hero, self.nombre, self.valor, self.pct, self.color = hero, nombre, "—", 0.0, CYAN

    def __iter__(self):                    # el resto del código lo usa como (etiqueta, barra)
        return iter((self, self))

    def config(self, text=None, **kw):
        if text is not None:
            self.valor = text
            self.hero.pinta_datos()

    def set(self, pct, color=None):
        self.pct = max(0.0, min(100.0, float(pct)))
        if color:
            self.color = color
        self.hero.pinta_datos()


class Hero(tk.Canvas):
    """Tarjeta principal de Inicio: luces de color difuminadas de fondo y, encima, anillo, mensaje, botones y datos en vivo."""
    H = 268
    D = 170

    def __init__(self, parent, app):
        self.fill = mix(PANEL, CYAN, 0.07)
        super().__init__(parent, bg=BG, height=self.H, highlightthickness=0, bd=0)
        self.app, self._key, self._img, self._job = app, None, None, None
        self.lbl_nota = _Txt(self, "Midiendo tu PC…")
        self.lbl_desc = _Txt(self, "Esto tarda unos segundos: miro tu monitor, la RAM, el arranque y el espacio.")
        self.stat = {k: _Dato(self, n) for k, n in (("cpu", "Procesador"), ("ram", "Memoria RAM"), ("disk", "Disco libre"), ("temp", "Temperatura"))}
        self.anillo = self                     # misma interfaz que el anillo suelto de antes: .poner(nota, medalla)
        self.valor, self.mostrado, self.medalla, self._anim = 0, 0.0, "", None
        self.b1 = NeonButton(self, "Mejorar ahora", lambda: app.show("optimize"), color=CYAN, filled=True, font=F(11, True), padx=22, pady=9)
        self.b2 = NeonButton(self, "Ver qué me falta", lambda: app.show("score"), color=MUTED, font=F(11, True), padx=18, pady=9)
        self._w1 = self.create_window(0, 0, window=self.b1, anchor="nw")
        self._w2 = self.create_window(0, 0, window=self.b2, anchor="nw")
        self.bind("<Configure>", self._conf)

    # ---- fondo ----
    def _conf(self, e):
        if self._job:
            self.after_cancel(self._job)
        self._job = self.after(50, self._todo)

    def _todo(self):
        self._job = None
        try:
            w = self.winfo_width()
            if w < 300:
                return
            if self._key != (w, self.H):
                self._key = (w, self.H)
                self._img = glow_image(self, w, self.H, 30, self.fill,
                                       [(0.07, 0.18, 430, CYAN, 0.46), (0.97, 0.92, 400, PINK, 0.38), (0.55, 0.45, 320, VIOLET, 0.12)], cell=6)
            self.delete("bg")
            self.create_image(0, 0, image=self._img, anchor="nw", tags="bg")
            esquinas(self, w, self.H, 30, BG, "bg")
            round_rect(self, 1, 1, w - 1, self.H - 1, 30, fill="", outline=mix(BORDER, CYAN, 0.7), tags="bg")
            self.tag_lower("bg")
            self.pinta_texto()
            self.pinta_datos()
            self._ring()
        except tk.TclError:
            pass

    # ---- texto y botones ----
    def pinta_texto(self):
        w = self.winfo_width()
        if w < 300:
            return
        self.delete("txt")
        x0, ancho = self.D + 56, max(160, w - (self.D + 56) - 270)
        self.create_text(x0, 34, text="PUNTUACIÓN HELLOP", anchor="w", fill=CYAN, font=F(9, True), tags="txt")
        t1 = self.create_text(x0, 52, text=self.lbl_nota.texto, anchor="nw", fill=FG, font=F(20, True), width=ancho, tags="txt")
        y2 = self.bbox(t1)[3] + 10                          # la descripción va justo debajo del título, sea cual sea su alto
        t2 = self.create_text(x0, y2, text=self.lbl_desc.texto, anchor="nw", fill=mix(FG, MUTED, 0.35), font=F(10), width=ancho, tags="txt")
        y = self.bbox(t2)[3] + 16
        x2 = x0 + self.b1.winfo_reqwidth() + 10
        apilado = x2 + self.b2.winfo_reqwidth() > w - 262            # en ventana estrecha el 2.º botón va debajo del 1.º
        necesario = max(250, int(y + self.b1.winfo_reqheight() + (self.b2.winfo_reqheight() + 8 if apilado else 0) + 26))
        if necesario != self.H:                             # la tarjeta crece si el texto lo pide (otro idioma, fuente más grande…)
            self.H = necesario
            self.configure(height=necesario)
            self._key = None
            self._conf(None)
            return
        self.coords(self._w1, x0, y)
        if apilado:
            x2, y2b = x0, y + self.b1.winfo_reqheight() + 8
        else:
            y2b = y
        self.coords(self._w2, x2, y2b)
        try:                                    # que el fondo de cada botón sea del color de la luz que tiene detrás
            for b, bx in ((self.b1, x0), (self.b2, x2)):
                p = self._img.get(int(bx + 4), int((y if b is self.b1 else y2b) + 18))
                b.configure(bg="#%02x%02x%02x" % tuple(p))
        except (tk.TclError, AttributeError, ValueError, TypeError):
            pass

    def pinta_datos(self):
        w = self.winfo_width()
        if w < 300:
            return
        self.delete("dat")
        x1, x2 = w - 250, w - 30
        for i, d in enumerate(self.stat.values()):
            y = 48 + i * 42
            self.create_text(x1, y, text=d.nombre, anchor="w", fill=mix(FG, MUTED, 0.45), font=F(9, True), tags="dat")
            self.create_text(x2, y, text=d.valor, anchor="e", fill=FG, font=F(9, True), tags="dat")
            round_rect(self, x1, y + 12, x2, y + 18, 3, fill=mix(self.fill, "#ffffff", 0.14), outline="", tags="dat")
            if d.pct > 0:
                round_rect(self, x1, y + 12, x1 + max(6, (x2 - x1) * d.pct / 100), y + 18, 3, fill=d.color, outline="", tags="dat")

    # ---- anillo ----
    def poner(self, valor, medalla):
        self.valor, self.medalla = valor, medalla
        if self._anim is None:
            self._anim = self.after(16, self._paso)

    def _paso(self):
        self._anim = None
        try:
            self.mostrado += (self.valor - self.mostrado) * 0.12
            if abs(self.valor - self.mostrado) < 0.4:
                self.mostrado = float(self.valor)
            else:
                self._anim = self.after(16, self._paso)
            self._ring()
        except tk.TclError:
            pass

    def _ring(self):
        self.delete("ring")
        d, g = self.D, 13
        r = d / 2 - 14
        cx, cy = 28 + d / 2, self.H / 2
        self.create_oval(cx - r, cy - r, cx + r, cy + r, outline=mix(self.fill, "#ffffff", 0.14), width=g, tags="ring")
        n = int(self.mostrado / 100 * 72)
        for i in range(n):
            self.create_arc(cx - r, cy - r, cx + r, cy + r, start=90 - i * 5 - 5.6, extent=5.6, style="arc",
                            outline=mix(CYAN, PINK, i / 72), width=g, tags="ring")
        if n:
            for ang, col in ((90, CYAN), (90 - n * 5, mix(CYAN, PINK, n / 72))):
                x, y = cx + r * math.cos(math.radians(ang)), cy - r * math.sin(math.radians(ang))
                self.create_oval(x - g / 2, y - g / 2, x + g / 2, y + g / 2, fill=col, outline="", tags="ring")
        self.create_text(cx, cy - 6, text=str(round(self.mostrado) if self.medalla else "—"), fill="#ffffff", font=F(32, True), tags="ring")
        self.create_text(cx, cy + 26, text=self.medalla.upper(), fill=CYAN, font=F(9, True), tags="ring")


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
            round_rect(self, 1, 1, w - 1, self.H - 1, 24, fill=mix(PANEL, col, 0.14 if self.hov else 0.05),
                       outline=mix(BORDER, col, 0.7 if self.hov else 0.25))
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

        # ---- tarjeta principal: todo se pinta sobre las luces difuminadas, así el texto queda nítido sobre el fondo borroso ----
        hero = Hero(root, app)
        hero.pack(fill="x", pady=(0, 14))
        self.hero = hero
        self.anillo, self.lbl_nota, self.lbl_desc, self.stat = hero.anillo, hero.lbl_nota, hero.lbl_desc, hero.stat
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
