"""Pantalla «Salud del PC»: temperaturas, drivers y red/ping (versión Qt)."""
import webbrowser

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QHBoxLayout, QVBoxLayout, QWidget

import actions
import health

from ..widgets import Barra, Boton, Etiqueta, Pagina, Tarjeta, fila, vacia

TABS = [("temp", "Temperaturas", "red"), ("drv", "Drivers", "teal"), ("net", "Red y ping", "green")]
TONO = {"green": "green", "yellow": "yellow", "red": "red", "muted": "muted"}


def _bullets(textos, titulo, tone="yellow", role="small"):
    c = Tarjeta(tone=tone, titulo=titulo)
    for t in textos:
        c.add(Etiqueta("•  " + t, role))
    return c


def _contenedor():
    w = QWidget()
    v = QVBoxLayout(w)
    v.setContentsMargins(0, 0, 0, 0)
    v.setSpacing(12)
    return w, v


class Salud(Pagina):
    titulo_texto = "Salud del PC"
    sub_texto = "Calor, drivers y conexión: lo que más suele frenar tus FPS sin que lo sepas."

    def __init__(self, app):
        super().__init__(app)
        self.tab = None
        self._loaded = set()
        self.busy = set()
        self._dns_card = None

        self.tab_btns = {}
        botones = []
        for key, label, _tone in TABS:
            b = Boton(label, lambda k=key: self.set_tab(k), kind="soft")
            self.tab_btns[key] = b
            botones.append(b)
        self.add(fila(*botones, None))

        self.frames = {}
        for key, _l, _t in TABS:
            w, v = _contenedor()
            self.frames[key] = (w, v)
            self.add(w)
        self._build_temp(self.frames["temp"][1])
        self._build_drv(self.frames["drv"][1])
        self._build_net(self.frames["net"][1])
        self.set_tab("temp")

    # ------------------------------------------------------------------
    def set_tab(self, key):
        self.tab = key
        for k, (w, _v) in self.frames.items():
            w.setVisible(k == key)
        tonos = {k: t for k, _l, t in TABS}
        for k, b in self.tab_btns.items():
            if k == key:
                b.estilo(kind="primary", tone=tonos[k])
            else:
                b.estilo(kind="soft", tone="")
        if key not in self._loaded and key != "net":
            self._loaded.add(key)
            {"temp": self.read_temp, "drv": self.read_drv}[key]()

    def al_mostrar(self):
        self.set_tab(self.tab or "temp")

    def _row_line(self, left, right, tone):
        w = QWidget()
        h = QHBoxLayout(w)
        h.setContentsMargins(0, 3, 0, 3)
        h.setSpacing(8)
        dot = Etiqueta("●", "h3", tone, wrap=False)
        dot.setFixedWidth(20)
        lb = Etiqueta(left, "muted")
        lb.setMinimumWidth(220)
        lb.setMaximumWidth(260)
        h.addWidget(dot, 0, Qt.AlignmentFlag.AlignTop)
        h.addWidget(lb, 0, Qt.AlignmentFlag.AlignTop)
        h.addWidget(Etiqueta(str(right), "h3"), 1, Qt.AlignmentFlag.AlignTop)
        return w

    def _fail(self, key, btn, lbl, e):
        self.busy.discard(key)
        btn.set_enabled(True)
        lbl.setText(f"Error: {e}")
        lbl.tono("red")

    # ---------------------------------------------------------------- temperaturas
    def _build_temp(self, lay):
        self.b_temp = Boton("↻  LEER TEMPERATURAS", self.read_temp, kind="primary", tone="red")
        self.m_temp = Etiqueta("", "muted")
        lay.addWidget(fila(self.b_temp, self.m_temp, None, espacio=14))
        self.temp_body, self.temp_lay = _contenedor()
        lay.addWidget(self.temp_body)
        lay.addWidget(_bullets((
            "Si la gráfica o el procesador pasan de cierta temperatura, bajan su velocidad solos para no quemarse. "
            "Pierdes FPS y notas tirones aunque todo lo demás esté bien.",
            "Mide mientras juegas (con Alt+Tab, o con el Monitor): en reposo la temperatura siempre sale más baja.",
            "Lo que más ayuda: limpiar el polvo (con el PC apagado), que la caja tenga entrada y salida de aire, y cambiar "
            "la pasta térmica si tu equipo tiene más de 3 o 4 años.",
            "Referencia: gráfica por debajo de 80 °C y procesador por debajo de 85 °C jugando es bueno."),
            "Por qué importa el calor"))

    def read_temp(self):
        if "temp" in self.busy:
            return
        self.busy.add("temp")
        self.b_temp.set_enabled(False)
        self.m_temp.setText("Leyendo…")
        self.m_temp.tono("teal")
        self.app.bg(health.temp_report, self._temp_done, lambda e: self._fail("temp", self.b_temp, self.m_temp, e))

    def _temp_done(self, res):
        rows, tips = res
        self.busy.discard("temp")
        self.b_temp.set_enabled(True)
        self.m_temp.setText("Listo")
        self.m_temp.tono("green")
        vacia(self.temp_lay)
        c = Tarjeta(tone="red", titulo="Temperaturas ahora mismo")
        for title, value, st in rows:
            c.add(self._row_line(title, value, TONO.get(st, "muted")))
        self.temp_lay.addWidget(c)
        t = Tarjeta(tone="teal", titulo="Qué hacer")
        for s in tips:
            t.add(Etiqueta("•  " + s))
        self.temp_lay.addWidget(t)

    # ---------------------------------------------------------------- drivers
    def _build_drv(self, lay):
        self.b_drv = Boton("↻  REVISAR MIS DRIVERS", self.read_drv, kind="primary", tone="teal")
        self.m_drv = Etiqueta("", "muted")
        lay.addWidget(fila(self.b_drv, self.m_drv, None, espacio=14))
        self.drv_body, self.drv_lay = _contenedor()
        lay.addWidget(self.drv_body)
        lay.addWidget(_bullets((
            "Solo el driver de la GRÁFICA influye de verdad en los FPS: los juegos nuevos suelen traer mejoras en cada versión.",
            "Un driver de red o de sonido «antiguo» no es un problema si todo funciona: no los toques sin motivo.",
            "HellOP no puede saber cuál es la última versión: te lleva a la página oficial del fabricante para que la compares.",
            "Para la gráfica, descarga siempre desde la web del fabricante, nunca desde páginas de «actualizadores de drivers»."),
            "Cómo leerlo"))

    def read_drv(self):
        if "drv" in self.busy:
            return
        self.busy.add("drv")
        self.b_drv.set_enabled(False)
        self.m_drv.setText("Leyendo tus drivers…")
        self.m_drv.tono("teal")
        self.app.bg(health.driver_report, self._drv_done, lambda e: self._fail("drv", self.b_drv, self.m_drv, e))

    def _drv_done(self, items):
        self.busy.discard("drv")
        self.b_drv.set_enabled(True)
        vacia(self.drv_lay)
        if not items:
            self.m_drv.setText("No he podido leer los drivers.")
            self.m_drv.tono("yellow")
            return
        self.m_drv.setText(f"{len(items)} drivers revisados")
        self.m_drv.tono("green")
        for it in items:
            st, text = health.driver_state(it)
            tone = TONO.get(st, "muted")
            c = Tarjeta(tone=tone, margen=14, espacio=4)
            head = QHBoxLayout()
            head.setSpacing(10)
            head.addWidget(Etiqueta(str(it["kind"]).upper(), "small", tone, wrap=False), 0, Qt.AlignmentFlag.AlignVCenter)
            head.addWidget(Etiqueta(str(it["name"]), "h3"), 1)
            c.lay.addLayout(head)
            c.add(Etiqueta(f"Versión {it['version']}  ·  fecha {it['date'] or '—'}", "small"))
            c.add(Etiqueta(text, "h3", tone))
            url = health.LINKS.get(it.get("vendor"))
            if url and st in ("yellow", "red", "green") and it["kind"] == "Gráfica":
                b = Boton(f"Abrir página de {it['vendor']}", lambda u=url: webbrowser.open(u), kind="soft", tone="teal")
                c.add(fila(b, None, margenes=(0, 6, 0, 0)))
            elif st in ("yellow", "red") and it["kind"] != "Gráfica":
                c.add(Etiqueta("Busca el driver en la web de tu placa base o de tu portátil (modelo exacto).", "small"))
            self.drv_lay.addWidget(c)

    # ---------------------------------------------------------------- red
    def _build_net(self, lay):
        self.b_ping = Boton("◉  MEDIR MI CONEXIÓN", self.run_ping, kind="primary", tone="green")
        self.b_dns = Boton("⚡  BUSCAR UN DNS MÁS RÁPIDO", self.run_dns, kind="soft", tone="teal")
        self.m_net = Etiqueta("", "muted")
        lay.addWidget(fila(self.b_ping, self.b_dns, self.m_net, None, espacio=10))
        self.pb = Barra(0, "green")
        self.pb.hide()
        lay.addWidget(self.pb)
        self.net_body, self.net_lay = _contenedor()
        lay.addWidget(self.net_body)
        lay.addWidget(_bullets((
            "Cable de red en vez de Wi-Fi: es lo que más reduce el ping y los saltos (jitter).",
            "Cerrar descargas en segundo plano (Steam, Epic, Windows Update, OneDrive) mientras juegas online.",
            "Elegir el servidor del juego más cercano a ti. HellOP no puede acortar la distancia física.",
            "Cambiar de DNS solo acelera que las webs empiecen a cargar; casi no cambia el ping dentro de una partida.",
            "Si tu ping es malo en todo, reinicia el router y revisa con tu operador: ningún programa puede arreglar una línea mala."),
            "Lo que de verdad baja el ping"))

    def run_ping(self):
        if "ping" in self.busy:
            return
        self.busy.add("ping")
        self.b_ping.set_enabled(False)
        self.m_net.setText("Midiendo (unos segundos)…")
        self.m_net.tono("teal")
        self.pb.pon(0)
        self.pb.show()

        def fail(e):
            self.pb.hide()
            self._fail("ping", self.b_ping, self.m_net, e)

        self.app.bg(lambda: health.ping_report(10, lambda p: self.app.ui(self._prog, p)), self._ping_done, fail)

    def _prog(self, p):
        self.pb.pon(int(p * 100))

    def _ping_done(self, res):
        rows, (st, verdict) = res
        self.busy.discard("ping")
        self.b_ping.set_enabled(True)
        self.pb.hide()
        self.m_net.setText("Listo")
        self.m_net.tono("green")
        if getattr(self, "_ping_card", None) is not None:
            self._ping_card.setParent(None)
            self._ping_card.deleteLater()
        c = Tarjeta(tone=TONO.get(st, "muted"), titulo="Resultado de la conexión")
        for r in rows:
            if r["avg"] is None:
                c.add(self._row_line(r["name"], "Sin respuesta", "red"))
                continue
            tone = ("green" if r["avg"] < 40 and r["jitter"] < 6 and r["loss"] < 5
                    else "yellow" if r["avg"] < 80 and r["jitter"] < 15 else "red")
            c.add(self._row_line(r["name"], f"{r['avg']:.0f} ms  ·  variación {r['jitter']:.1f} ms  ·  pérdida {r['loss']} %", tone))
        c.add(Etiqueta(verdict, "h3", TONO.get(st, "muted")))
        self._ping_card = c
        self.net_lay.insertWidget(0, c)

    def run_dns(self):
        if "dns" in self.busy:
            return
        self.busy.add("dns")
        self.b_dns.set_enabled(False)
        self.m_net.setText("Probando servidores DNS…")
        self.m_net.tono("teal")
        self.app.bg(actions.network_actions, self._dns_done, lambda e: self._fail("dns", self.b_dns, self.m_net, e))

    def _dns_done(self, acts):
        self.busy.discard("dns")
        self.b_dns.set_enabled(True)
        self.m_net.setText("Listo")
        self.m_net.tono("green")
        if self._dns_card is not None:
            self._dns_card.setParent(None)
            self._dns_card.deleteLater()
        c = Tarjeta(tone="teal", titulo="DNS")
        fast = [a for a in acts if isinstance(a, actions.DnsAction)]
        if not fast:
            c.add(Etiqueta("Tu DNS actual ya es rápido: no hace falta cambiarlo.", None, "green"))
        for a in acts:
            h = QHBoxLayout()
            h.setSpacing(12)
            tx = QVBoxLayout()
            tx.setSpacing(2)
            tx.addWidget(Etiqueta(a.title, "h3"))
            st = a.check()
            if st:
                tx.addWidget(Etiqueta(str(st), "small"))
            h.addLayout(tx, 1)
            h.addWidget(Boton("Aplicar", lambda a_=a: self.apply_action(a_), kind="primary", tone="teal"), 0, Qt.AlignmentFlag.AlignVCenter)
            c.lay.addLayout(h)
        self._dns_card = c
        self.net_lay.addWidget(c)

    def apply_action(self, a):
        self.m_net.setText("Aplicando…")
        self.m_net.tono("teal")

        def done(res):
            self.m_net.setText(("✓ " if res.ok else "✗ ") + res.msg)
            self.m_net.tono("green" if res.ok else "red")

        def fail(e):
            self.m_net.setText(f"✗ {e}")
            self.m_net.tono("red")

        self.app.bg(lambda: actions.execute(a), done, fail)
