"""Página «Salud del PC»: temperaturas, drivers y red/ping."""
import tkinter as tk
import webbrowser
from tkinter import ttk

import actions
import health
from util import DEMO
from widgets import (BG, CYAN, F, FG, GREEN, MUTED, PANEL, PINK, RED, VIOLET, YELLOW, Card, NeonButton, ScrollFrame,
                     WrapLabel, page_title)

COL = {"green": GREEN, "yellow": YELLOW, "red": RED, "muted": MUTED}
TABS = [("temp", "Temperaturas", PINK), ("drv", "Drivers", CYAN), ("net", "Red y ping", GREEN)]


class HealthPage(tk.Frame):
    def __init__(self, parent, app):
        super().__init__(parent, bg=BG)
        self.app = app
        self.tab = None
        self._loaded = set()
        self.busy = set()
        top = tk.Frame(self, bg=BG)
        top.pack(fill="x", padx=26, pady=(22, 6))
        page_title(top, "Salud del PC",
                   "Calor, drivers y conexión: lo que más suele frenar tus FPS sin que lo sepas.", accent=PINK).pack(anchor="w")
        bar = tk.Frame(top, bg=BG)
        bar.pack(fill="x", pady=(12, 0))
        self.tab_btns = {}
        for key, label, color in TABS:
            b = NeonButton(bar, label, lambda k=key: self.set_tab(k), color=color, font=F(11, True), padx=18, pady=7)
            b.pack(side="left", padx=(0, 10))
            self.tab_btns[key] = b
        self.scroll = ScrollFrame(self)
        self.scroll.pack(fill="both", expand=True, padx=(26, 10), pady=(8, 10))
        self.frames = {k: tk.Frame(self.scroll.inner, bg=BG) for k, _l, _c in TABS}
        self._build_temp(self.frames["temp"])
        self._build_drv(self.frames["drv"])
        self._build_net(self.frames["net"])
        self.set_tab("temp")

    # ------------------------------------------------------------------
    def set_tab(self, key):
        self.tab = key
        for k, f in self.frames.items():
            f.pack_forget()
        self.frames[key].pack(fill="x")
        for k, b in self.tab_btns.items():
            b.set_color(dict((a, c) for a, _l, c in TABS)[k] if k == key else MUTED)
        if key not in self._loaded and key != "net":
            self._loaded.add(key)
            {"temp": self.read_temp, "drv": self.read_drv}[key]()

    def on_show(self):
        self.set_tab(self.tab or "temp")

    def _row_line(self, parent, left, right, color, bold=False):
        r = tk.Frame(parent, bg=PANEL)
        r.pack(fill="x", pady=3)
        tk.Label(r, text="●", font=F(11), fg=color, bg=PANEL).pack(side="left")
        tk.Label(r, text=left, font=F(10), fg=MUTED, bg=PANEL, width=30, anchor="w").pack(side="left", padx=(8, 0))
        tk.Label(r, text=right, font=F(10, True), fg=FG, bg=PANEL, anchor="w").pack(side="left", fill="x", expand=True)
        return r

    def _clear(self, f):
        for w in f.winfo_children():
            w.destroy()

    # ---------------------------------------------------------------- temperaturas
    def _build_temp(self, root):
        row = tk.Frame(root, bg=BG)
        row.pack(fill="x", pady=(0, 8))
        self.b_temp = NeonButton(row, "↻  LEER TEMPERATURAS", self.read_temp, color=PINK, filled=True, font=F(11, True), padx=20, pady=8)
        self.b_temp.pack(side="left")
        self.m_temp = tk.Label(row, text="", font=F(10), fg=MUTED, bg=BG)
        self.m_temp.pack(side="left", padx=14)
        self.temp_body = tk.Frame(root, bg=BG)
        self.temp_body.pack(fill="x")
        c = Card(root, accent=YELLOW, title="Por qué importa el calor")
        c.pack(fill="x", pady=(12, 0))
        for t in ("Si la gráfica o el procesador pasan de cierta temperatura, bajan su velocidad solos para no quemarse. "
                  "Pierdes FPS y notas tirones aunque todo lo demás esté bien.",
                  "Mide mientras juegas (con Alt+Tab, o con el Monitor): en reposo la temperatura siempre sale más baja.",
                  "Lo que más ayuda: limpiar el polvo (con el PC apagado), que la caja tenga entrada y salida de aire, y cambiar "
                  "la pasta térmica si tu equipo tiene más de 3 o 4 años.",
                  "Referencia: gráfica por debajo de 80 °C y procesador por debajo de 85 °C jugando es bueno."):
            WrapLabel(c.body, text="•  " + t, font=F(9), fg=MUTED).pack(fill="x", pady=1)

    def read_temp(self):
        if "temp" in self.busy:
            return
        self.busy.add("temp")
        self.b_temp.set_enabled(False)
        self.m_temp.config(text="Leyendo…", fg=CYAN)
        self.app.bg(health.temp_report, self._temp_done, lambda e: self._fail("temp", self.b_temp, self.m_temp, e))

    def _fail(self, key, btn, lbl, e):
        self.busy.discard(key)
        btn.set_enabled(True)
        lbl.config(text=f"Error: {e}", fg=RED)

    def _temp_done(self, res):
        rows, tips = res
        self.busy.discard("temp")
        self.b_temp.set_enabled(True)
        self.m_temp.config(text="Listo", fg=GREEN)
        self._clear(self.temp_body)
        c = Card(self.temp_body, accent=PINK, title="Temperaturas ahora mismo")
        c.pack(fill="x", pady=(0, 10))
        for title, value, st in rows:
            self._row_line(c.body, title, value, COL.get(st, MUTED))
        t = Card(self.temp_body, accent=CYAN, title="Qué hacer")
        t.pack(fill="x")
        for s in tips:
            WrapLabel(t.body, text="•  " + s, font=F(10), fg=FG).pack(fill="x", pady=2)

    # ---------------------------------------------------------------- drivers
    def _build_drv(self, root):
        row = tk.Frame(root, bg=BG)
        row.pack(fill="x", pady=(0, 8))
        self.b_drv = NeonButton(row, "↻  REVISAR MIS DRIVERS", self.read_drv, color=CYAN, filled=True, font=F(11, True), padx=20, pady=8)
        self.b_drv.pack(side="left")
        self.m_drv = tk.Label(row, text="", font=F(10), fg=MUTED, bg=BG)
        self.m_drv.pack(side="left", padx=14)
        self.drv_body = tk.Frame(root, bg=BG)
        self.drv_body.pack(fill="x")
        c = Card(root, accent=YELLOW, title="Cómo leerlo")
        c.pack(fill="x", pady=(12, 0))
        for t in ("Solo el driver de la GRÁFICA influye de verdad en los FPS: los juegos nuevos suelen traer mejoras en cada versión.",
                  "Un driver de red o de sonido «antiguo» no es un problema si todo funciona: no los toques sin motivo.",
                  "HellOP no puede saber cuál es la última versión: te lleva a la página oficial del fabricante para que la compares.",
                  "Para la gráfica, descarga siempre desde la web del fabricante, nunca desde páginas de «actualizadores de drivers»."):
            WrapLabel(c.body, text="•  " + t, font=F(9), fg=MUTED).pack(fill="x", pady=1)

    def read_drv(self):
        if "drv" in self.busy:
            return
        self.busy.add("drv")
        self.b_drv.set_enabled(False)
        self.m_drv.config(text="Leyendo tus drivers…", fg=CYAN)
        self.app.bg(health.driver_report, self._drv_done, lambda e: self._fail("drv", self.b_drv, self.m_drv, e))

    def _drv_done(self, items):
        self.busy.discard("drv")
        self.b_drv.set_enabled(True)
        self._clear(self.drv_body)
        if not items:
            self.m_drv.config(text="No he podido leer los drivers.", fg=YELLOW)
            return
        self.m_drv.config(text=f"{len(items)} drivers revisados", fg=GREEN)
        for it in items:
            st, text = health.driver_state(it)
            color = COL.get(st, MUTED)
            c = Card(self.drv_body, accent=color)
            c.pack(fill="x", pady=(0, 8))
            top = tk.Frame(c.body, bg=PANEL)
            top.pack(fill="x")
            tk.Label(top, text=it["kind"].upper(), font=F(8, True), fg=color, bg=PANEL).pack(side="left")
            tk.Label(top, text="   " + it["name"], font=F(11, True), fg=FG, bg=PANEL).pack(side="left")
            tk.Label(c.body, text=f"Versión {it['version']}  ·  fecha {it['date'] or '—'}", font=F(9), fg=MUTED, bg=PANEL,
                     anchor="w").pack(fill="x", pady=(2, 0))
            tk.Label(c.body, text=text, font=F(10, True), fg=color, bg=PANEL, anchor="w").pack(fill="x", pady=(2, 0))
            url = health.LINKS.get(it.get("vendor"))
            if url and st in ("yellow", "red", "green") and it["kind"] == "Gráfica":
                NeonButton(c.body, f"Abrir página de {it['vendor']}", lambda u=url: webbrowser.open(u), color=CYAN,
                           padx=14, pady=6, font=F(10, True)).pack(anchor="w", pady=(8, 0))
            elif st in ("yellow", "red") and it["kind"] != "Gráfica":
                WrapLabel(c.body, text="Busca el driver en la web de tu placa base o de tu portátil (modelo exacto).",
                          font=F(9), fg=MUTED).pack(fill="x", pady=(4, 0))

    # ---------------------------------------------------------------- red
    def _build_net(self, root):
        row = tk.Frame(root, bg=BG)
        row.pack(fill="x", pady=(0, 8))
        self.b_ping = NeonButton(row, "◉  MEDIR MI CONEXIÓN", self.run_ping, color=GREEN, filled=True, font=F(11, True), padx=20, pady=8)
        self.b_ping.pack(side="left")
        self.b_dns = NeonButton(row, "⚡  BUSCAR UN DNS MÁS RÁPIDO", self.run_dns, color=CYAN, font=F(11, True), padx=20, pady=8)
        self.b_dns.pack(side="left", padx=10)
        self.m_net = tk.Label(row, text="", font=F(10), fg=MUTED, bg=BG)
        self.m_net.pack(side="left", padx=8)
        self.pb = ttk.Progressbar(root, style="Green.Horizontal.TProgressbar", mode="determinate", maximum=100, length=360)
        self.net_body = tk.Frame(root, bg=BG)
        self.net_body.pack(fill="x", pady=(6, 0))
        c = Card(root, accent=YELLOW, title="Lo que de verdad baja el ping")
        c.pack(fill="x", pady=(12, 0))
        for t in ("Cable de red en vez de Wi-Fi: es lo que más reduce el ping y los saltos (jitter).",
                  "Cerrar descargas en segundo plano (Steam, Epic, Windows Update, OneDrive) mientras juegas online.",
                  "Elegir el servidor del juego más cercano a ti. HellOP no puede acortar la distancia física.",
                  "Cambiar de DNS solo acelera que las webs empiecen a cargar; casi no cambia el ping dentro de una partida.",
                  "Si tu ping es malo en todo, reinicia el router y revisa con tu operador: ningún programa puede arreglar una línea mala."):
            WrapLabel(c.body, text="•  " + t, font=F(9), fg=MUTED).pack(fill="x", pady=1)

    def run_ping(self):
        if "ping" in self.busy:
            return
        self.busy.add("ping")
        self.b_ping.set_enabled(False)
        self.m_net.config(text="Midiendo (unos segundos)…", fg=CYAN)
        self.pb["value"] = 0
        self.pb.pack(anchor="w", pady=(4, 0))
        self.app.bg(lambda: health.ping_report(10, lambda p: self.app.ui(self._prog, p)), self._ping_done,
                    lambda e: (self.pb.pack_forget(), self._fail("ping", self.b_ping, self.m_net, e)))

    def _prog(self, p):
        self.pb["value"] = int(p * 100)

    def _ping_done(self, res):
        rows, (st, verdict) = res
        self.busy.discard("ping")
        self.b_ping.set_enabled(True)
        self.pb.pack_forget()
        self.m_net.config(text="Listo", fg=GREEN)
        self._clear(self.net_body)
        c = Card(self.net_body, accent=COL[st], title="Resultado de la conexión")
        c.pack(fill="x", pady=(0, 10))
        for r in rows:
            if r["avg"] is None:
                self._row_line(c.body, r["name"], "Sin respuesta", RED)
                continue
            col = GREEN if r["avg"] < 40 and r["jitter"] < 6 and r["loss"] < 5 else YELLOW if r["avg"] < 80 and r["jitter"] < 15 else RED
            self._row_line(c.body, r["name"], f"{r['avg']:.0f} ms  ·  variación {r['jitter']:.1f} ms  ·  pérdida {r['loss']} %", col)
        WrapLabel(c.body, text=verdict, font=F(10, True), fg=COL[st]).pack(fill="x", pady=(8, 0))

    def run_dns(self):
        if "dns" in self.busy:
            return
        self.busy.add("dns")
        self.b_dns.set_enabled(False)
        self.m_net.config(text="Probando servidores DNS…", fg=CYAN)
        self.app.bg(actions.network_actions, self._dns_done, lambda e: self._fail("dns", self.b_dns, self.m_net, e))

    def _dns_done(self, acts):
        self.busy.discard("dns")
        self.b_dns.set_enabled(True)
        self.m_net.config(text="Listo", fg=GREEN)
        for w in self.net_body.winfo_children():
            if getattr(w, "_dns", False):
                w.destroy()
        c = Card(self.net_body, accent=CYAN, title="DNS")
        c._dns = True
        c.pack(fill="x", pady=(0, 10))
        fast = [a for a in acts if isinstance(a, actions.DnsAction)]
        if not fast:
            WrapLabel(c.body, text="Tu DNS actual ya es rápido: no hace falta cambiarlo.", font=F(10), fg=GREEN).pack(fill="x")
        for a in acts:
            r = tk.Frame(c.body, bg=PANEL)
            r.pack(fill="x", pady=4)
            tx = tk.Frame(r, bg=PANEL)
            tx.pack(side="left", fill="x", expand=True)
            tk.Label(tx, text=a.title, font=F(10, True), fg=FG, bg=PANEL, anchor="w").pack(fill="x")
            st = a.check()
            if st:
                tk.Label(tx, text=st, font=F(9), fg=MUTED, bg=PANEL, anchor="w").pack(fill="x")
            NeonButton(r, "Aplicar", lambda a_=a: self.apply_action(a_), color=CYAN, filled=True, padx=16, pady=6,
                       font=F(10, True)).pack(side="right")

    def apply_action(self, a):
        self.m_net.config(text="Aplicando…", fg=CYAN)

        def done(res):
            self.m_net.config(text=("✓ " if res.ok else "✗ ") + res.msg, fg=GREEN if res.ok else RED)
        self.app.bg(lambda: actions.execute(a), done, lambda e: self.m_net.config(text=f"✗ {e}", fg=RED))
