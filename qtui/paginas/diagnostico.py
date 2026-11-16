"""Pantalla «Diagnóstico de juego»: mide mientras juegas y te dice qué te frena y qué causa los tirones."""
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QGridLayout, QVBoxLayout, QWidget

import bios
import diag
from util import DEMO

from ..widgets import Barra, Boton, Etiqueta, Insignia, Pagina, Tarjeta, fila, vacia

LEVEL = {"mal": ("PROBLEMA", "red"), "ojo": ("OJO", "yellow"), "bien": ("BIEN", "green"), "info": ("INFO", "accent")}
COUNTDOWN = 10


def _kv(rows):
    """Filas «etiqueta · valor» en dos columnas."""
    w = QWidget()
    g = QGridLayout(w)
    g.setContentsMargins(0, 0, 0, 0)
    g.setHorizontalSpacing(14)
    g.setVerticalSpacing(6)
    g.setColumnStretch(1, 1)
    for i, (k, v) in enumerate(rows):
        g.addWidget(Etiqueta(str(k), "small"), i, 0, Qt.AlignmentFlag.AlignTop)
        g.addWidget(Etiqueta(str(v)), i, 1, Qt.AlignmentFlag.AlignTop)
    g.setColumnMinimumWidth(0, 190)
    return w


class Diagnostico(Pagina):
    titulo_texto = "Diagnóstico de juego"
    sub_texto = "Mide tu PC mientras juegas y te dice si te frena la CPU, la gráfica, la RAM, el disco o el calor, y qué causa los tirones."

    def __init__(self, app):
        super().__init__(app)
        self.secs = 30
        self.busy = False

        how = Tarjeta(tone="accent", titulo="Cómo se usa (3 pasos)")
        for t in ("1.  Pulsa «Empezar medición». Tienes 10 segundos de cuenta atrás.",
                  "2.  Vuelve a tu juego (Alt+Tab) y juega con normalidad, mejor en una zona exigente.",
                  "3.  Cuando termine, vuelve a HellOP y lee el resultado. No cambia ningún ajuste: solo mide y te aconseja."):
            how.add(Etiqueta(t))
        self.add(how)

        ctl = Tarjeta(tone="teal", titulo="Medición")
        self.dur = {}
        botones = [Etiqueta("Duración:", "h3", wrap=False)]
        for s in (20, 30, 60):
            b = Boton(f"{s} s", lambda v=s: self.set_secs(v), kind="primary" if s == self.secs else "soft")
            self.dur[s] = b
            botones.append(b)
        botones.append(None)
        ctl.add(fila(*botones, espacio=8))
        self.btn = Boton("▶   EMPEZAR MEDICIÓN", self.start, kind="primary")
        ctl.add(self.btn, 0, Qt.AlignmentFlag.AlignLeft)
        self.msg = Etiqueta("", "h3", "muted")
        ctl.add(self.msg)
        self.pb = Barra(0, "accent")
        self.pb.hide()
        ctl.add(self.pb)
        self.add(ctl)

        self.results = QWidget()
        self.res_lay = self._lay_vertical(self.results)
        self.add(self.results)

    @staticmethod
    def _lay_vertical(w):
        v = QVBoxLayout(w)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(12)
        return v

    # ------------------------------------------------------------------
    def set_secs(self, v):
        if self.busy:
            return
        self.secs = v
        for s, b in self.dur.items():
            b.estilo(kind="primary" if s == v else "soft")

    def say(self, text, tone="muted"):
        self.msg.setText(text)
        self.msg.tono(tone)

    def start(self):
        if self.busy:
            return
        self.busy = True
        self.btn.set_enabled(False)
        vacia(self.res_lay)
        self.pb.pon(0)
        self._count(0 if DEMO else COUNTDOWN)

    def _count(self, n):
        if n > 0:
            self.say(f"Vuelve a tu juego ahora (Alt+Tab). Empiezo a medir en {n} s…", "yellow")
            self.app.after(1000, lambda: self._count(n - 1))
            return
        self.pb.show()
        self.say("Midiendo… juega con normalidad.", "accent")
        secs = self.secs
        self.app.bg(lambda: diag.measure(secs, lambda p, t: self.app.ui(self._prog, p, t)), self.measured, self.failed)

    def _prog(self, p, t):
        self.pb.pon(p)
        self.say(t, "accent")

    def failed(self, e):
        self.busy = False
        self.pb.hide()
        self.btn.set_enabled(True)
        self.say(f"No pude completar la medición: {e}", "red")

    def measured(self, m):
        self.pb.hide()
        self.say("Analizando resultados y revisando causas de tirones…", "accent")
        self.app.bg(lambda: self._analyze(m), self.show_result, self.failed)

    def _analyze(self, m):
        res = diag.analyze(m)
        guide = self.app.pages["bios"].guide
        ram = None
        try:
            if guide is None and not DEMO:
                guide = bios.build_guide()
                self.app.pages["bios"].guide = guide
            if guide and guide.get("ram"):
                ram = {"running": guide["ram"].get("running"), "kit": guide["ram"].get("target")}
        except Exception:  # noqa: BLE001
            ram = None
        res["checks"] = diag.static_checks(ram)
        res["prev"] = diag.load_history()
        diag.save_run(res["kpi"])
        return res

    # ------------------------------------------------------------------
    def show_result(self, r):
        self.busy = False
        self.btn.set_enabled(True)
        self.btn.set_text("↻   MEDIR OTRA VEZ")
        self.say("Listo. Aquí tienes el resultado.", "green")
        root = self.res_lay
        vacia(root)
        tone = {"bien": "green", "mal": "red", "ojo": "yellow"}.get(r["color"], "accent")

        v = Tarjeta(tone=tone)
        v.add(Etiqueta("CUELLO DE BOTELLA", "small"))
        v.add(Etiqueta(r["bottleneck"], "big", tone, wrap=False))
        v.add(Etiqueta(r["headline"], "h3"))
        v.add(_kv(r["stats"]))
        prev = r["prev"][-1] if r["prev"] else None
        if prev:
            k = r["kpi"]
            bits = [f"latencia p99: {prev['j99']} → {k['j99']} ms", f"DPC: {prev['dpc']} → {k['dpc']} %",
                    f"núcleo más cargado: {prev['hot']} → {k['hot']} %"]
            v.add(Etiqueta(f"Comparado con la medición anterior ({prev['ts']}):  " + "  ·  ".join(bits), "small"))
        root.addWidget(v)

        root.addWidget(Etiqueta("Qué he encontrado", "h2"))
        for level, title, detail, fix in r["findings"] + r["checks"]:
            self._finding(root, level, title, detail, fix)

        if r["top"]:
            c = Tarjeta(tone="teal", titulo="Programas que más CPU gastaron mientras jugabas")
            c.add(_kv([(n, f"{p:.1f} % de la CPU") for n, p in r["top"]]))
            c.add(Etiqueta("Si ves aquí navegadores, launchers o programas que no necesitas, ciérralos antes de jugar "
                           "(el Modo Extremo lo hace por ti).", "small"))
            root.addWidget(c)

    def _finding(self, root, level, title, detail, fix):
        name, tone = LEVEL[level]
        c = Tarjeta(tone=tone)
        c.add(fila(Insignia(name, tone), Etiqueta(title, "h3"), espacio=10))
        if detail:
            c.add(Etiqueta(detail, "muted"))
        if fix:
            c.add(Etiqueta("Qué hacer:  " + fix, "h3", tone if level != "bien" else None))
        root.addWidget(c)
