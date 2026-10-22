"""Página «Monitor»: gráficas en vivo de CPU, RAM, gráfica (uso, VRAM, temperatura, reloj, consumo) y red."""
import math
import random
import threading
import time
import tkinter as tk

import psutil

from util import DEMO, nvsmi, run_cmd
from widgets import (BG, BORDER, CYAN, F, FG, GREEN, MUTED, PANEL, PANEL2, PINK, RED, VIOLET, YELLOW, Card, ScrollFrame,
                     WrapLabel, mix, page_title)

POINTS = 90


class LineChart(tk.Canvas):
    """Gráfica de líneas con rejilla; hasta 2 series. Eje Y fijo (ymax) o automático."""

    def __init__(self, parent, title, unit, series, ymax=None, height=170):
        super().__init__(parent, bg=PANEL, height=height, highlightthickness=0, bd=0)
        self.title, self.unit, self.series, self.ymax = title, unit, series, ymax     # series: [(nombre, color)]
        self.data = [[] for _ in series]
        self.bind("<Configure>", lambda e: self.redraw())

    def push(self, values):
        for i, v in enumerate(values):
            self.data[i].append(v)
            self.data[i] = self.data[i][-POINTS:]
        self.redraw()

    def redraw(self):
        self.delete("all")
        w, h = self.winfo_width(), self.winfo_height()
        if w < 60:
            return
        l, r, t, b = 44, 14, 34, 22
        pw, ph = w - l - r, h - t - b
        allv = [v for s in self.data for v in s if v is not None]
        top = self.ymax or max(10, math.ceil((max(allv) if allv else 10) * 1.2 / 10) * 10)
        self.create_text(12, 12, text=self.title, anchor="w", fill=FG, font=F(10, True))
        for i in range(5):                                   # rejilla
            y = t + ph * i / 4
            self.create_line(l, y, w - r, y, fill=BORDER if i in (0, 4) else mix(PANEL, BORDER, 0.5))
            self.create_text(l - 6, y, text=f"{top * (1 - i / 4):.0f}", anchor="e", fill=MUTED, font=F(8))
        # leyenda y valor actual
        x = w - r
        for (name, col), s in reversed(list(zip(self.series, self.data))):
            cur = next((v for v in reversed(s) if v is not None), None)
            txt = f"{name} {cur:.0f}{self.unit}" if cur is not None else f"{name} —"
            tid = self.create_text(x, 12, text=txt, anchor="e", fill=col, font=F(9, True))
            bb = self.bbox(tid)
            x = bb[0] - 14
        for (name, col), s in zip(self.series, self.data):
            pts = []
            for i, v in enumerate(s):
                if v is None:
                    if len(pts) >= 4:
                        self.create_line(*pts, fill=col, width=2, smooth=True)
                    pts = []
                    continue
                px = l + pw * (i + POINTS - len(s)) / (POINTS - 1)
                py = t + ph * (1 - min(v, top) / top)
                pts += [px, py]
            if len(pts) >= 4:
                self.create_line(*pts, fill=col, width=2, smooth=True)
        self.create_text(l, h - 8, text="hace 90 s", anchor="w", fill=MUTED, font=F(8))
        self.create_text(w - r, h - 8, text="ahora", anchor="e", fill=MUTED, font=F(8))


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


class MonitorPage(tk.Frame):
    def __init__(self, parent, app):
        super().__init__(parent, bg=BG)
        self.app = app
        self.run = False
        self.last = {}
        self._thread = None
        self._net = None
        self._demo = {"cpu": 30.0, "gpu": 55.0, "temp": 60.0}
        top = tk.Frame(self, bg=BG)
        top.pack(fill="x", padx=26, pady=(22, 6))
        page_title(top, "Monitor en vivo",
                   "Gráficas de los últimos 90 segundos. Déjalo abierto en otra pantalla mientras juegas.",
                   accent=CYAN).pack(anchor="w")
        self.scroll = ScrollFrame(self)
        self.scroll.pack(fill="both", expand=True, padx=(26, 10), pady=(8, 10))
        root = self.scroll.inner
        grid = tk.Frame(root, bg=BG)
        grid.pack(fill="x")
        grid.columnconfigure((0, 1), weight=1, uniform="c")
        specs = [("cpu", "CPU", "%", [("Total", CYAN), ("Núcleo más cargado", PINK)], 100),
                 ("ram", "Memoria RAM", "%", [("Uso", VIOLET)], 100),
                 ("gpu", "Gráfica", "%", [("Uso", GREEN), ("VRAM", YELLOW)], 100),
                 ("temp", "Temperatura de la gráfica", "°", [("GPU", RED)], 100),
                 ("clk", "Reloj de la gráfica", " MHz", [("GPU", CYAN)], None),
                 ("net", "Red", " KB/s", [("Bajada", GREEN), ("Subida", PINK)], None)]
        self.charts = {}
        for i, (key, title, unit, series, ymax) in enumerate(specs):
            c = Card(grid, accent=series[0][1])
            c.grid(row=i // 2, column=i % 2, sticky="nsew", padx=6, pady=6)
            ch = LineChart(c.body, title, unit, series, ymax)
            ch.pack(fill="x")
            self.charts[key] = ch
        self.note = WrapLabel(root, bg=BG, fg=MUTED, font=F(9), text="")
        self.note.pack(fill="x", pady=(8, 14))
        self.after(1000, self._tick)

    # ------------------------------------------------------------------
    def _sampler(self):
        if not DEMO:
            psutil.cpu_percent(None, percpu=True)
        while self.run:
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
        # solo medimos mientras esta pestaña está a la vista (no gastamos CPU en otras)
        visible = self.app.current == "monitor"
        if visible and not self.run:
            self.run = True
            self._thread = threading.Thread(target=self._sampler, daemon=True)
            self._thread.start()
        elif not visible and self.run:
            self.run = False
        if visible and self.last:
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
            self.note.config(text="  ".join(msg))
        self.after(1000, self._tick)

    def shutdown(self):
        self.run = False
