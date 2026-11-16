"""Inicio: saludo, nota de tu PC, datos en vivo, accesos rápidos y estado de HellOP."""
import time

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QHBoxLayout, QLabel, QVBoxLayout, QWidget

import actions
import games
import version
from util import DEMO, is_admin

from ..graficos import Anillo, Medidor
from ..widgets import Boton, Etiqueta, Insignia, Pagina, Rejilla, Tarjeta, fila
from .. import theme

MAS = [
    ("analysis", "◎", "Analizar mi PC", "Procesador, placa, RAM, gráfica y discos, con consejos para tu equipo.", "accent"),
    ("diag", "◈", "Diagnóstico", "Mide mientras juegas y te dice qué te frena y qué causa los tirones.", "accent"),
    ("gameprof", "✧", "Ajustes de juego", "Baja sombras y efectos en Fortnite, VALORANT, LoL, Minecraft y CS2 con copia y deshacer.", "teal"),
    ("health", "♥", "Salud del PC", "Temperaturas, drivers y ping: lo que frena tus FPS sin que lo sepas.", "green"),
    ("score", "★", "Puntuación HellOP", "La nota de tu PC con medalla y logros: te dice cuánto te falta para el oro.", "yellow"),
    ("cuello", "⬆", "Qué pieza mejorar", "Detecta qué te frena de verdad y te dice si te compensa gastar dinero.", "teal"),
    ("bios", "◉", "BIOS y overclock", "Lo que no se puede cambiar desde Windows, explicado paso a paso.", "yellow"),
]
GRANDES = [
    ("optimize", "⚡", "Optimizar", "Elige cada optimización en su cuadrado y aplícalas juntas.", "accent"),
    ("games", "▣", "Mis juegos", "Se optimiza solo al abrir tu juego.", "teal"),
    ("fps", "▤", "FPS reales", "Mide FPS y tirones y comprueba si un cambio ayudó.", "yellow"),
    ("tweaks", "☄", "Tweaks", "Ajustes de latencia en tres niveles de riesgo.", "green"),
]


def _glifo(g, tone, tam=40):
    lb = QLabel(g)
    lb.setAlignment(Qt.AlignmentFlag.AlignCenter)
    lb.setFixedSize(tam, tam)
    lb.setStyleSheet(f"background: {theme.hexa(tone, 0.14)}; color: {theme.C[tone]}; border-radius: {tam // 3}px; font-size: {int(tam * 0.45)}px; font-weight: 700;")
    return lb


class TarjetaClic(Tarjeta):
    def __init__(self, cmd, **kw):
        super().__init__(**kw)
        self.cmd = cmd
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def mouseReleaseEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton and self.rect().contains(e.position().toPoint()):
            self.cmd()
        super().mouseReleaseEvent(e)


class Inicio(Pagina):
    def __init__(self, app):
        super().__init__(app)
        self._nota, self._cargando, self._temp_ok, self._nota_t = None, set(), False, 0
        hr = time.localtime().tm_hour
        saludo = "Buenos días" if 6 <= hr < 13 else "Buenas tardes" if 13 <= hr < 21 else "Buenas noches"
        ok = is_admin() or DEMO
        top = QHBoxLayout()
        top.addWidget(Etiqueta(saludo, "title", wrap=False))
        top.addWidget(Insignia("● Administrador" if ok else "● Sin administrador", "green" if ok else "red"), 0, Qt.AlignmentFlag.AlignBottom)
        top.addStretch(1)
        self.b_asist = Boton("✨  Asistente de optimización", app.abrir_asistente, kind="soft")
        top.addWidget(self.b_asist)
        w = QWidget()
        w.setLayout(top)
        self.add(w)
        self.lic_lbl = Etiqueta("", "small", wrap=False)
        top.insertWidget(2, self.lic_lbl)
        # ---- tarjeta principal ----
        hero = Tarjeta(margen=22, espacio=10)
        h = QHBoxLayout()
        h.setSpacing(26)
        self.anillo = Anillo(0, "accent", texto="—", sub="", tam=170, grosor=14)
        h.addWidget(self.anillo, 0, Qt.AlignmentFlag.AlignVCenter)
        centro = QVBoxLayout()
        centro.addWidget(Etiqueta("PUNTUACIÓN HELLOP", "small", "accent"))
        self.lbl_nota = Etiqueta("Midiendo tu PC…", "h2")
        self.lbl_nota.setStyleSheet("font-size: 22px; font-weight: 700;")
        self.lbl_desc = Etiqueta("Esto tarda unos segundos: miro tu monitor, la RAM, el arranque y el espacio.", "muted")
        centro.addWidget(self.lbl_nota)
        centro.addWidget(self.lbl_desc)
        centro.addSpacing(6)
        centro.addWidget(fila(Boton("Mejorar ahora", lambda: app.ir("optimize")), Boton("Ver qué me falta", lambda: app.ir("score"), kind="ghost"), None))
        centro.addStretch(1)
        h.addLayout(centro, 1)
        datos = QVBoxLayout()
        datos.setSpacing(10)
        self.stat = {}
        for k, n in (("cpu", "Procesador"), ("ram", "Memoria RAM"), ("disk", "Disco libre"), ("temp", "Temperatura")):
            m = Medidor(n)
            m.setFixedWidth(220)
            self.stat[k] = m
            datos.addWidget(m)
        h.addLayout(datos)
        hero.lay.addLayout(h)
        self.add(hero)
        # ---- 4 accesos grandes ----
        rej = Rejilla(4)
        for key, sim, tit, txt, tn in GRANDES:
            c = TarjetaClic(lambda k=key: app.ir(k), margen=16, espacio=6)
            c.lay.addWidget(_glifo(sim, tn), 0, Qt.AlignmentFlag.AlignLeft)
            c.lay.addSpacing(6)
            c.lay.addWidget(Etiqueta(tit, "h3"))
            c.lay.addWidget(Etiqueta(txt, "muted"))
            c.lay.addStretch(1)
            c.setMinimumHeight(150)
            rej.add(c)
        self.add(rej)
        self.add(Etiqueta("Más herramientas", "h2"))
        rej2 = Rejilla(3)
        for key, icon, name, desc, tn in MAS:
            c = Tarjeta(margen=16, espacio=6)
            c.lay.addWidget(_glifo(icon, tn), 0, Qt.AlignmentFlag.AlignLeft)
            c.lay.addWidget(Etiqueta(name, "h3"))
            c.lay.addWidget(Etiqueta(desc, "muted"))
            c.lay.addStretch(1)
            c.lay.addWidget(Boton("Abrir  →", lambda k=key: app.ir(k), kind="soft", tone=tn if tn != "yellow" else None), 0, Qt.AlignmentFlag.AlignLeft)
            rej2.add(c)
        self.add(rej2)
        est = Tarjeta(titulo="Estado de HellOP")
        self.rows = {}
        for key, label in (("auto", "Modo juego automático"), ("last", "Última optimización"), ("upd", "Actualizaciones"), ("adm", "Permisos de administrador")):
            f = QHBoxLayout()
            dot = Etiqueta("●", tone="muted", wrap=False)
            f.addWidget(dot)
            lb = Etiqueta(label, "muted", wrap=False)
            lb.setFixedWidth(210)
            f.addWidget(lb)
            val = Etiqueta("—", "h3", wrap=True)
            f.addWidget(val, 1)
            est.lay.addLayout(f)
            self.rows[key] = (dot, val)
        self.add(est)

    # ---- licencia (la ventana llama a esto al cambiar) ----
    def caja_lic(self, st):
        txt = {"owner": "Modo creador", "pro": "HellOP PRO activo", "free": "Plan gratis", "expired": "Clave caducada", "invalid": "Clave no válida"}.get(st["level"], "")
        self.lic_lbl.setText("   " + txt)

    # ---- datos ----
    def _live(self):
        import psutil
        import sysinfo
        vols = [(f / t * 100) for _m, f, t in sysinfo.volumes() if t]
        return psutil.cpu_percent(interval=0.3), psutil.virtual_memory().percent, (min(vols) if vols else None)

    def _live_done(self, r):
        cpu, ram, low = r
        self.stat["cpu"].pon(cpu, f"{cpu:.0f} %", "red" if cpu >= 90 else "yellow" if cpu >= 75 else None)
        self.stat["ram"].pon(ram, f"{ram:.0f} %", "red" if ram >= 90 else "yellow" if ram >= 75 else None)
        if low is not None:
            self.stat["disk"].pon(low, f"{low:.0f} %", "red" if low < 15 else "yellow" if low < 25 else None)

    def _temp_done(self, rows):
        cpu = [x["value"] for x in rows if x.get("kind") == "cpu"]
        m = self.stat["temp"]
        if cpu:
            t = max(cpu)
            m.pon(t, f"{t:.0f} °C", "red" if t >= 85 else "yellow" if t >= 75 else "green")
        else:
            m.pon(0, "No disponible")

    def _nota_done(self, res):
        import puntuacion
        self._nota = res
        sc = res["score"]
        nombre, _col = res["medal"]
        sig = next(((lim, n) for lim, n, _c in reversed(puntuacion.MEDALLAS) if lim > sc), None)
        self.anillo.pon(sc, "accent", texto=str(sc), sub=nombre.upper())
        self.lbl_nota.setText(f"Tu PC está al {sc} %." + (f"\nA {sig[0] - sc} puntos de {sig[1]}." if sig else "\n¡Máximo rango!"))
        top = [t for t, _p, _f in res["perdidos"][:2]]
        self.lbl_desc.setText(("Lo que más te frena: " + "; ".join(top) + ". Se arregla en un par de minutos.") if top
                              else "Todo está en orden. No hay nada que te frene ahora mismo.")

    def _set(self, key, texto, tone):
        dot, val = self.rows[key]
        dot.tono(tone)
        val.setText(texto)

    def al_mostrar(self):
        import licencia
        self.caja_lic(licencia.status())
        self.app.bg(self._live, self._live_done, lambda e: None)
        if not self._temp_ok and "temp" not in self._cargando:
            self._cargando.add("temp")
            self._temp_ok = True
            import sysinfo
            self.app.after(6000, lambda: self.app.bg(sysinfo.read_temps, lambda r: (self._cargando.discard("temp"), self._temp_done(r)),
                                                     lambda e: (self._cargando.discard("temp"), self._temp_done([]))))
        import puntuacion
        if self._nota is None:
            ult = puntuacion.ultima()
            if ult:
                self._nota_done(ult)
        if "nota" not in self._cargando and (self._nota is None or (self._nota_t == 0 and puntuacion.antigua())):
            self._cargando.add("nota")
            self._nota_t = time.time()
            self.app.after(10000 if self._nota else 400, lambda: self.app.bg(
                lambda: puntuacion.calcular(), lambda r: (self._cargando.discard("nota"), self._nota_done(r)), lambda e: self._cargando.discard("nota")))
        w = self.app.pages["games"].watcher if hasattr(self.app.pages["games"], "watcher") else None
        if w and getattr(w, "running", False):
            self._set("auto", w.status()[0], "green")
        else:
            n = len(games.load()["games"])
            self._set("auto", "Desactivado" + (f" · {n} juegos en tu biblioteca" if n else " · añade tus juegos en «Mis juegos»"), "muted")
        last = None
        if not DEMO:
            done = [e for e in actions.load_log() if not e.get("undone")]
            last = done[-1]["ts"] if done else None
        self._set("last", last or ("Ejemplo: hoy" if DEMO else "Aún no has optimizado nada"), "green" if last or DEMO else "yellow")
        info = self.app.pages["update"].info if self.app.pages.creada("update") and hasattr(self.app.pages["update"], "info") else None
        if info and info.get("newer"):
            self._set("upd", f"Hay una versión nueva: v{info['latest']}", "yellow")
        elif info:
            self._set("upd", f"Estás al día (v{version.__version__})", "green")
        else:
            self._set("upd", f"v{version.__version__} · pulsa «Actualizaciones» para buscar", "muted")
        ok = is_admin() or DEMO
        self._set("adm", "Sí" if ok else "No: pulsa «Reabrir como administrador» arriba", "green" if ok else "red")
