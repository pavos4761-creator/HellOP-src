"""Pantalla «Monitor en vivo»: gráficas de CPU, RAM, gráfica (uso, VRAM, temperatura, reloj) y red."""
import math
import random
import threading
import time

from PySide6.QtCore import QPointF, QRectF, Qt, QTimer
from PySide6.QtGui import QPainter, QPainterPath, QPen
from PySide6.QtWidgets import QSizePolicy, QWidget

import psutil

from util import DEMO, nvsmi, run_cmd

from .. import theme
from ..widgets import Etiqueta, Pagina, Rejilla, Tarjeta

POINTS = 90


class GraficaVivo(QWidget):
    """Gráfica de líneas con rejilla; hasta 2 series. Eje Y fijo (ymax) o automático."""

    def __init__(self, title, unit, series, ymax=None, alto=170, parent=None):
        super().__init__(parent)
        self.title, self.unit, self.series, self.ymax = title, unit, series, ymax      # series: [(nombre, tono)]
        self.data = [[] for _ in series]
        self.setMinimumHeight(alto)
        self.setFixedHeight(alto)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

    def push(self, values):
        for i, v in enumerate(values):
            self.data[i].append(v)
            self.data[i] = self.data[i][-POINTS:]
        self.update()

    def paintEvent(self, _e):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()
        if w < 60:
            return
        l, r, t, b = 44, 6, 34, 22
        pw, ph = w - l - r, h - t - b
        allv = [v for s in self.data for v in s if v is not None]
        top = self.ymax or max(10, math.ceil((max(allv) if allv else 10) * 1.2 / 10) * 10)
        p.setPen(theme.color("fg"))
        p.setFont(theme.fuente(13, True))
        p.drawText(QRectF(0, 0, w * 0.5, 24), int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter), self.title)
        fp = theme.fuente(11)
        for i in range(5):                                   # rejilla
            y = t + ph * i / 4
            p.setPen(QPen(theme.color("border") if i in (0, 4) else theme.mezcla("panel", "border", 0.5), 1))
            p.drawLine(QPointF(l, y), QPointF(w - r, y))
            p.setPen(theme.color("muted"))
            p.setFont(fp)
            p.drawText(QRectF(0, y - 8, l - 6, 16), int(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter), f"{top * (1 - i / 4):.0f}")
        # leyenda y valor actual (de derecha a izquierda)
        x = w - r
        p.setFont(theme.fuente(12, True))
        fm = p.fontMetrics()
        for (name, tone), s in reversed(list(zip(self.series, self.data))):
            cur = next((v for v in reversed(s) if v is not None), None)
            txt = f"{name} {cur:.0f}{self.unit}" if cur is not None else f"{name} —"
            ancho = fm.horizontalAdvance(txt)
            p.setPen(theme.color(tone))
            p.drawText(QRectF(x - ancho, 0, ancho, 24), int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter), txt)
            x -= ancho + 14
        for (name, tone), s in zip(self.series, self.data):
            pen = QPen(theme.color(tone), 2, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin)
            p.setPen(pen)
            tramo = []
            for i, v in enumerate(s):
                if v is None:
                    self._traza(p, tramo)
                    tramo = []
                    continue
                px = l + pw * (i + POINTS - len(s)) / (POINTS - 1)
                py = t + ph * (1 - min(v, top) / top)
                tramo.append(QPointF(px, py))
            self._traza(p, tramo)
        p.setPen(theme.color("muted"))
        p.setFont(fp)
        p.drawText(QRectF(l, h - 18, 120, 16), int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter), "hace 90 s")
        p.drawText(QRectF(w - r - 120, h - 18, 120, 16), int(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter), "ahora")

    @staticmethod
    def _traza(p, pts):
        if len(pts) < 2:
            return
        path = QPainterPath(pts[0])
        for q in pts[1:]:
            path.lineTo(q)
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawPath(path)


def _gpu_read():
    exe = nvsmi()
    if not exe:
        return None
    q = "utilization.gpu,memory.used,memory.total,temperature.gpu,clocks.sm,power.draw,fan.speed"
    rc, out, _ = run_cmd([exe, f"--query-gpu={q}", "--format=csv,noheader,nounits"], timeout=5)
    if rc != 0 or not out:
        return None
    p = [x.strip() for x in out.splitlines()[0].split(",")]
    if len(p) < 7:
        return None

    def n(x):
        try:
            return float(x)
        except ValueError:
            return None
    mem = (n(p[1]) / n(p[2]) * 100) if n(p[1]) is not None and n(p[2]) else None
    return {"gpu": n(p[0]), "vram": mem, "temp": n(p[3]), "clk": n(p[4]), "pw": n(p[5]), "fan": n(p[6])}


class Monitor(Pagina):
    titulo_texto = "Monitor en vivo"
    sub_texto = "Gráficas de los últimos 90 segundos. Déjalo abierto en otra pantalla mientras juegas."

    def __init__(self, app):
        super().__init__(app)
        self.run = False
        self.last = {}
        self._thread = None
        self._tok = 0
        self._net = None
        self._demo = {"cpu": 30.0, "gpu": 55.0, "temp": 60.0}
        specs = [("cpu", "CPU", "%", [("Total", "accent"), ("Núcleo más cargado", "teal")], 100),
                 ("ram", "Memoria RAM", "%", [("Uso", "accent")], 100),
                 ("gpu", "Gráfica", "%", [("Uso", "green"), ("VRAM", "yellow")], 100),
                 ("temp", "Temperatura de la gráfica", "°", [("GPU", "red")], 100),
                 ("clk", "Reloj de la gráfica", " MHz", [("GPU", "teal")], None),
                 ("net", "Red", " KB/s", [("Bajada", "green"), ("Subida", "accent")], None)]
        grid = Rejilla(2, 12)
        self.charts = {}
        for key, title, unit, series, ymax in specs:
            c = Tarjeta(tone=series[0][1], margen=10)
            ch = GraficaVivo(title, unit, series, ymax)
            c.add(ch)
            grid.add(c)
            self.charts[key] = ch
        self.add(grid)
        self.note = Etiqueta("", "small")
        self.add(self.note)
        self.timer = QTimer(self)
        self.timer.setInterval(1000)
        self.timer.timeout.connect(self._tick)

    # ------------------------------------------------------------------
    def al_mostrar(self):
        self._arranca()
        self.timer.start()

    def al_ocultar(self):
        self.timer.stop()
        self.run = False

    def apaga(self):
        self.timer.stop()
        self.run = False

    def _arranca(self):
        if not self.run:
            self.run = True
            self._tok += 1
            self._net = None
            self._thread = threading.Thread(target=self._sampler, args=(self._tok,), daemon=True)
            self._thread.start()

    def _sampler(self, tok):
        if not DEMO:
            psutil.cpu_percent(None, percpu=True)
        while self.run and tok == self._tok:
            t0 = time.time()
            try:
                self.last = self._read()
            except Exception:  # noqa: BLE001
                pass
            time.sleep(max(0.1, 1.0 - (time.time() - t0)))

    def _read(self):
        if DEMO:
            d = self._demo
            d["cpu"] = min(98, max(5, d["cpu"] + random.uniform(-9, 9)))
            d["gpu"] = min(99, max(10, d["gpu"] + random.uniform(-10, 12)))
            d["temp"] = min(86, max(40, d["temp"] + random.uniform(-1.5, 2.0) + (d["gpu"] - 55) / 80))
            return {"cpu": d["cpu"], "hot": min(100, d["cpu"] + random.uniform(10, 35)), "ram": 61 + random.uniform(-1, 1),
                    "gpu": {"gpu": d["gpu"], "vram": 48 + random.uniform(-1, 1), "temp": d["temp"],
                            "clk": 1500 + d["gpu"] * 4 + random.uniform(-20, 20), "pw": 50 + d["gpu"], "fan": 40 + d["temp"] / 3},
                    "down": random.uniform(100, 2500), "up": random.uniform(10, 300)}
        per = psutil.cpu_percent(None, percpu=True)
        net = psutil.net_io_counters()
        now = time.time()
        down = up = 0.0
        if self._net:
            dt = max(0.1, now - self._net[0])
            down, up = (net.bytes_recv - self._net[1]) / 1024 / dt, (net.bytes_sent - self._net[2]) / 1024 / dt
        self._net = (now, net.bytes_recv, net.bytes_sent)
        return {"cpu": sum(per) / len(per) if per else 0, "hot": max(per) if per else 0, "ram": psutil.virtual_memory().percent,
                "gpu": _gpu_read(), "down": down, "up": up}

    def _tick(self):
        if not self.last:
            return
        s = self.last
        g = s.get("gpu") or {}
        self.charts["cpu"].push([s["cpu"], s["hot"]])
        self.charts["ram"].push([s["ram"]])
        self.charts["gpu"].push([g.get("gpu"), g.get("vram")])
        self.charts["temp"].push([g.get("temp")])
        self.charts["clk"].push([g.get("clk")])
        self.charts["net"].push([s["down"], s["up"]])
        msg = []
        if not g:
            msg.append("No pude leer la gráfica: las gráficas de GPU solo funcionan con tarjetas NVIDIA que tengan nvidia-smi (viene con el driver).")
        else:
            extra = []
            if g.get("pw") is not None:
                extra.append(f"consumo {g['pw']:.0f} W")
            if g.get("fan") is not None:
                extra.append(f"ventilador {g['fan']:.0f} %")
            if extra:
                msg.append("Gráfica: " + " · ".join(extra) + ".")
            if g.get("temp") and g["temp"] >= 84:
                msg.append("⚠ La gráfica está muy caliente: puede bajar su velocidad.")
        msg.append("La temperatura de la CPU no se muestra: Windows no la expone sin un driver especial.")
        self.note.setText("  ".join(msg))
