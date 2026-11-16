"""Pantalla «Análisis de PC»."""
import os
import webbrowser

import psutil
from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import QGridLayout, QHBoxLayout, QVBoxLayout, QWidget

import sysinfo
from util import age_text

from ..graficos import Anillo
from ..widgets import Barra, Boton, Etiqueta, Insignia, Pagina, Rejilla, Tarjeta, fila, vacia

LEVEL_STYLE = {"ok": ("✓", "green"), "info": ("ℹ", "accent"), "warn": ("⚠", "yellow")}
TEMP_TONE = {"ok": "green", "warn": "yellow", "crit": "red"}
ICONS = {"cpu": "▣", "board": "▤", "ram": "▥", "gpu": "◈", "disks": "▦", "os": "❖"}
ACCENTS = {"cpu": "accent", "board": "teal", "ram": "red", "gpu": "green", "disks": "yellow", "os": "accent"}


def kv_rows(rows, key_width=130):
    """Filas «etiqueta  valor» en dos columnas. Devuelve un QWidget."""
    w = QWidget()
    g = QGridLayout(w)
    g.setContentsMargins(0, 0, 0, 0)
    g.setHorizontalSpacing(14)
    g.setVerticalSpacing(6)
    g.setColumnStretch(1, 1)
    for i, (k, v) in enumerate(rows):
        kl = Etiqueta(str(k), "small", "muted")
        kl.setFixedWidth(key_width)
        kl.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        vl = Etiqueta(str(v))
        vl.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        g.addWidget(kl, i, 0, Qt.AlignmentFlag.AlignTop)
        g.addWidget(vl, i, 1, Qt.AlignmentFlag.AlignTop)
    return w


class Analisis(Pagina):
    titulo_texto = "Análisis de PC"
    sub_texto = "Lee tu procesador, placa, RAM, gráfica y discos, y te dice qué puedes mejorar."

    def __init__(self, app):
        super().__init__(app)
        self.report = None
        self.temp_box = None
        self.temp_lay = None
        self.temp_busy = False
        self.rgen = 0

        hero = Tarjeta(tone="accent")
        h = QHBoxLayout()
        h.setSpacing(12)
        self.g_cpu = Anillo(0, "accent", "0 %", "CPU", 120, 10)
        self.g_ram = Anillo(0, "red", "0 %", "RAM", 120, 10)
        self.g_disk = Anillo(0, "yellow", "0 %", "DISCO", 120, 10)
        for g in (self.g_cpu, self.g_ram, self.g_disk):
            h.addWidget(g)
        h.addSpacing(16)
        v = QVBoxLayout()
        v.setSpacing(8)
        self.btn = Boton("⚡   ANÁLISIS DE PC", self.run, kind="primary")
        self.btn.setMinimumHeight(46)
        self.msg = Etiqueta("Pulsa el botón para empezar.", "muted")
        self.pb = Barra(0, "accent")
        self.pb.setRange(0, 0)
        self.pb.setVisible(False)
        self.pb.setMaximumWidth(340)
        v.addStretch(1)
        v.addWidget(self.btn, 0, Qt.AlignmentFlag.AlignLeft)
        v.addWidget(self.msg)
        v.addWidget(self.pb)
        v.addStretch(1)
        h.addLayout(v, 1)
        hero.lay.addLayout(h)
        self.add(hero)

        self.res = QWidget()
        self.res.setObjectName("pagina")
        self.res_lay = QVBoxLayout(self.res)
        self.res_lay.setContentsMargins(0, 0, 0, 0)
        self.res_lay.setSpacing(12)
        self.add(self.res)

        self.timer = QTimer(self)
        self.timer.setInterval(1500)
        self.timer.timeout.connect(self._live)
        self.t_temps = QTimer(self)
        self.t_temps.setInterval(5000)
        self.t_temps.timeout.connect(self._read_temps)
        self._live()

    # ------------------------------------------------------------------
    def _live(self):
        try:
            c = psutil.cpu_percent(interval=None)
            r = psutil.virtual_memory().percent
            d = psutil.disk_usage(os.path.abspath(os.sep)).percent
            self.g_cpu.pon(c, "accent", f"{c:.0f} %", "CPU", animar=False)
            self.g_ram.pon(r, "red", f"{r:.0f} %", "RAM", animar=False)
            self.g_disk.pon(d, "yellow", f"{d:.0f} %", "DISCO", animar=False)
        except Exception:  # noqa: BLE001
            pass

    def al_mostrar(self):
        self._live()
        self.timer.start()
        if self.report and self.temp_box is not None:
            self._read_temps()
            self.t_temps.start()

    def al_ocultar(self):
        self.timer.stop()
        self.t_temps.stop()

    def apaga(self):
        self.timer.stop()
        self.t_temps.stop()

    # ------------------------------------------------------------------
    def run(self):
        self.btn.set_enabled(False)
        self.msg.setText("Analizando tu equipo… (puede tardar unos segundos)")
        self.msg.tono("accent")
        self.pb.setVisible(True)
        self.app.status("Analizando hardware…")
        self.app.bg(sysinfo.analyze, self.done, self.fail)

    def fail(self, e):
        self.pb.setVisible(False)
        self.btn.set_enabled(True)
        self.msg.setText(f"No pude completar el análisis: {e}")
        self.msg.tono("red")
        self.app.status("Análisis fallido")

    def done(self, rep):
        self.pb.setVisible(False)
        self.btn.set_enabled(True)
        self.btn.set_text("⚡   ANALIZAR DE NUEVO")
        self.msg.setText("Análisis completado ✓")
        self.msg.tono("green")
        self.app.status("Análisis completado")
        self.report = rep
        self.render(rep)

    # ------------------------------------------------------------------
    def render(self, rep):
        self.rgen += 1
        self.t_temps.stop()
        self.temp_box = None
        vacia(self.res_lay)
        lay = self.res_lay

        grid = Rejilla(2, 12)
        for key in ("cpu", "board", "ram", "gpu", "disks", "os"):
            title, rows = rep["sections"][key]
            c = Tarjeta(tone=ACCENTS[key], titulo=f"{ICONS[key]}  {title}")
            c.add(kv_rows(rows))
            grid.add(c)
        lay.addWidget(grid)

        if rep["ram"]:
            self._ram_card(rep["ram"])
        self._temps_card()
        self._recs_card(rep["recs"])
        self._drivers_card(rep["drivers"])

        nxt = Tarjeta(tone="green", titulo="➜  Siguiente paso")
        nxt.add(Etiqueta("Con estos datos ya puedo proponerte optimizaciones a medida. Te las iré preguntando una por una."))
        nxt.add(Boton("Ir a Optimizar  →", lambda: self.app.ir("optimize"), kind="primary", tone="green"), 0, Qt.AlignmentFlag.AlignLeft)
        lay.addWidget(nxt)

    def _ram_card(self, ram):
        c = Tarjeta(tone="red", titulo="▥  Memoria RAM · mejores tiempos para tu equipo")
        tone = {"ok": "green", "warn": "yellow", "info": "accent"}.get(ram["level"], "accent")
        c.add(Etiqueta(ram["headline"], "h3", tone))
        for g in ram["goal"]:
            c.add(Etiqueta("•  " + g))
        if ram["steps"]:
            c.add(Etiqueta(f"Cómo activar {ram['xmp']} en la BIOS", "h3", "red"))
            for i, s in enumerate(ram["steps"], 1):
                c.add(Etiqueta(f"{i}.  {s}"))
        self.res_lay.addWidget(c)

    def _temps_card(self):
        c = Tarjeta(tone="yellow", titulo="♨  Temperaturas")
        self.temp_box = QWidget()
        self.temp_lay = QVBoxLayout(self.temp_box)
        self.temp_lay.setContentsMargins(0, 0, 0, 0)
        self.temp_lay.setSpacing(6)
        self.temp_lay.addWidget(Etiqueta("Leyendo sensores…", None, "muted"))
        c.add(self.temp_box)
        c.add(Etiqueta("Se actualiza cada pocos segundos. Windows no expone todos los sensores: para lecturas precisas de CPU "
                       "deja abierto LibreHardwareMonitor y la app las usará automáticamente.", "small", "muted"))
        self.res_lay.addWidget(c)
        self._read_temps()
        self.t_temps.start()

    def _read_temps(self):
        if self.temp_busy or self.temp_box is None:
            return
        self.temp_busy = True
        g = self.rgen
        self.app.bg(sysinfo.read_temps, lambda t: self._temps_done(t, g), lambda e: self._temps_done([], g))

    def _temps_done(self, temps, g):
        self.temp_busy = False
        if g != self.rgen or self.temp_box is None or self.temp_lay is None:
            return
        vacia(self.temp_lay)
        if not temps:
            self.temp_lay.addWidget(Etiqueta("Windows no ha dado lecturas de temperatura en este equipo.", None, "muted"))
        for t in temps:
            tone = TEMP_TONE.get(t["level"], "green")
            items = [Etiqueta(f"{t['value']:.0f} °C", "h2", tone, wrap=False), Etiqueta(t["label"], wrap=False)]
            items[0].setMinimumWidth(80)
            if t["level"] != "ok":
                items.append(Insignia("CALIENTE" if t["level"] == "warn" else "CRÍTICA", tone))
            if t["note"]:
                items.append(Etiqueta(t["note"], "small", "yellow" if "aprox" in t["note"] else "red", wrap=False))
            items.append(None)
            self.temp_lay.addWidget(fila(*items))

    def _recs_card(self, recs):
        c = Tarjeta(tone="teal", titulo="✚  Salud y recomendaciones")
        for level, title, detail in recs:
            icon, tone = LEVEL_STYLE.get(level, LEVEL_STYLE["info"])
            ic = Etiqueta(icon, "h2", tone, wrap=False)
            ic.setFixedWidth(30)
            ic.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignHCenter)
            col = QVBoxLayout()
            col.setSpacing(2)
            col.addWidget(Etiqueta(title, "h3"))
            col.addWidget(Etiqueta(detail, None, "muted"))
            row = QHBoxLayout()
            row.setSpacing(8)
            row.addWidget(ic, 0, Qt.AlignmentFlag.AlignTop)
            row.addLayout(col, 1)
            c.lay.addLayout(row)
        self.res_lay.addWidget(c)

    def _drivers_card(self, drivers):
        c = Tarjeta(tone="accent", titulo="⚙  Drivers")
        if not drivers:
            c.add(Etiqueta("No se pudieron leer los drivers.", None, "muted"))
            self.res_lay.addWidget(c)
            return
        c.add(Etiqueta("Una fecha antigua no siempre significa que falte una versión nueva: compruébalo en la web del fabricante. "
                       "Actualiza siempre desde la página oficial.", "small", "muted"))
        for d in drivers[:14]:
            ins = Insignia("ANTIGUO", "yellow") if d["old"] else Insignia("AL DÍA", "green")
            col = QVBoxLayout()
            col.setSpacing(1)
            col.addWidget(Etiqueta(d["name"], "h3"))
            col.addWidget(Etiqueta(f"versión {d['version']} · {d['date']} ({age_text(d['age_days'])})", "small", "muted"))
            row = QHBoxLayout()
            row.setSpacing(10)
            row.addWidget(ins, 0, Qt.AlignmentFlag.AlignTop)
            row.addLayout(col, 1)
            if d["old"] and d["url"]:
                row.addWidget(Boton("Buscar actualización", lambda u=d["url"]: webbrowser.open(u), kind="soft"), 0, Qt.AlignmentFlag.AlignTop)
            c.lay.addLayout(row)
        self.res_lay.addWidget(c)
