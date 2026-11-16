"""Pantalla «Qué pieza mejorar»: te dice qué te frena y si te compensa gastar dinero."""
import threading
import time

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QHBoxLayout, QLineEdit, QVBoxLayout, QWidget

import cuello
import fps
from util import DEMO

from ..widgets import Barra, Boton, Etiqueta, Pagina, Tarjeta, vacia
from .analisis import kv_rows

COL = {"green": "green", "yellow": "yellow", "red": "red", "cyan": "accent"}
PRIO_COL = {0: "red", 1: "yellow", 2: "accent", 3: "green"}


class Cuello(Pagina):
    titulo_texto = "Qué pieza mejorar"
    sub_texto = "Detecta qué te frena de verdad y te dice si te compensa gastar dinero (o no)."

    def __init__(self, app):
        super().__init__(app)
        self.busy = False
        self.stop = None
        self.m = None

        c = Tarjeta(tone="yellow", titulo="Cómo funciona")
        for t in ("Primero miro tu RAM, tus discos y dónde están tus juegos. Eso lo sé sin medir nada.",
                  "Para saber si limita la GRÁFICA o el PROCESADOR hay que medir un juego (30 s con PresentMon). Sin medir no adivino.",
                  "Te digo qué hacer primero y qué NO comprar. Si tu PC no tiene un cuello claro, te lo digo: ahorrarás dinero.",
                  "Es una guía basada en tus datos, no una garantía: cada juego se comporta distinto."):
            c.add(Etiqueta("•  " + t, "small", "muted"))
        self.add(c)

        sel = Tarjeta(tone="accent", titulo="Juego a medir (opcional, pero es lo que da la respuesta más útil)")
        self.entrada = QLineEdit(fps.KNOWN_GAMES[0])
        self.entrada.setMinimumWidth(320)
        self.entrada.setMaximumWidth(460)
        fl = QHBoxLayout()
        fl.setSpacing(10)
        fl.addWidget(self.entrada)
        fl.addWidget(Boton("↻  Juegos abiertos", self.refresh_candidates, kind="soft"))
        fl.addStretch(1)
        sel.lay.addLayout(fl)
        self.chips = QHBoxLayout()
        self.chips.setSpacing(6)
        sel.lay.addLayout(self.chips)
        self.add(sel)

        self.b_an = Boton("◎  ANALIZAR SIN MEDIR", lambda: self.analyze(False), kind="primary")
        self.b_me = Boton("▶  MEDIR UN JUEGO (30 s) Y ANALIZAR", lambda: self.analyze(True), kind="soft", tone="green")
        self.msg = Etiqueta("", None, "muted", wrap=False)
        bar = QHBoxLayout()
        bar.setSpacing(10)
        bar.addWidget(self.b_an)
        bar.addWidget(self.b_me)
        bar.addWidget(self.msg, 1)
        bw = QWidget()
        bw.setLayout(bar)
        bar.setContentsMargins(0, 0, 0, 0)
        self.add(bw)

        self.pb = Barra(0, "accent")
        self.pb.setMaximumWidth(420)
        self.pb.setVisible(False)
        self.col.addWidget(self.pb, 0, Qt.AlignmentFlag.AlignLeft)

        self.body = QWidget()
        self.body.setObjectName("pagina")
        self.body_lay = QVBoxLayout(self.body)
        self.body_lay.setContentsMargins(0, 0, 0, 0)
        self.body_lay.setSpacing(10)
        self.add(self.body)

    def al_mostrar(self):
        self.refresh_candidates()

    def _set_msg(self, texto, tone):
        self.msg.setText(texto)
        self.msg.tono(tone)

    def refresh_candidates(self):
        vacia(self.chips)
        names = fps.running_candidates()
        if names and names[0] in fps.KNOWN_GAMES:
            self.entrada.setText(names[0])
        for n in names[:6]:
            b = Boton(n, lambda n_=n: self.entrada.setText(n_), kind="soft", tone="green" if n in fps.KNOWN_GAMES else None)
            self.chips.addWidget(b)
        self.chips.addStretch(1)

    # ------------------------------------------------------------------
    def _prog(self, p, m):
        self.pb.pon(int(p * 100))
        self._set_msg(m, "accent")

    def _end(self):
        self.busy, self.stop = False, None
        self.pb.setVisible(False)
        self.b_an.set_enabled(True)
        self.b_me.set_text("▶  MEDIR UN JUEGO (30 s) Y ANALIZAR")
        self.b_me.set_enabled(True)

    def _fail(self, e):
        self._end()
        self._set_msg(("✗ " + str(e)) if isinstance(e, fps.FpsError) else f"✗ Error: {type(e).__name__}: {e}", "red")

    def analyze(self, measure):
        if self.busy:
            if self.stop:
                self.stop.set()
            return
        proc = self.entrada.text().strip()
        if measure:
            if not proc.lower().endswith(".exe"):
                self._set_msg("Escribe el programa del juego, por ejemplo VALORANT-Win64-Shipping.exe", "yellow")
                return
            if not DEMO and not fps.have_presentmon() and not self.app.pregunta(
                    "Descargar PresentMon", "Para medir hace falta PresentMon, una herramienta gratuita de Intel (≈1 MB).\n\n"
                    "Se descarga una sola vez y se comprueba su huella SHA256.\n\n¿Descargarla ahora?"):
                return
        self.busy, self.stop = True, threading.Event()
        self.b_an.set_enabled(False)
        if measure:
            self.b_me.set_text("■  Cancelar")
        else:
            self.b_me.set_enabled(False)
        self.pb.pon(0)
        self.pb.setVisible(True)
        stop = self.stop

        def work():
            m = None
            if measure:
                fps.ensure_presentmon()
                for i in range(5, 0, -1):
                    if stop.is_set():
                        raise fps.FpsError("Medición cancelada")
                    self.app.ui(self._prog, 0, f"Vuelve al juego (Alt+Tab): empiezo en {i}…")
                    time.sleep(1)
                ft, g, c = fps.capture(proc, 30, lambda p, msg: self.app.ui(self._prog, p, msg), stop, 0)
                m = fps.analyze(ft, g, c)
            return cuello.run(m, lambda s: self.app.ui(self._prog, 0, s)), m

        self.app.bg(work, self._done, self._fail)

    def _done(self, res):
        self._end()
        (txt, col), items, specs = res[0]
        self.m = res[1]
        self._set_msg("✓ Listo", "green")
        vacia(self.body_lay)
        tone = COL.get(col, "accent")
        c = Tarjeta(tone=tone, titulo="Mi conclusión")
        c.add(Etiqueta(txt, "h3", tone))
        filas = list(specs)
        if self.m:
            filas.append(("Medido", f"{self.m['avg']:.0f} FPS medios · 1 % low {self.m['low1']:.0f} · gráfica al {self.m.get('gpu_pct', '?')} %"))
        c.add(kv_rows(filas, key_width=110))
        self.body_lay.addWidget(c)
        for it in items:
            pt = PRIO_COL.get(it["prio"], "accent")
            card = Tarjeta(tone=pt, espacio=4)
            cab = QHBoxLayout()
            cab.setSpacing(12)
            cab.addWidget(Etiqueta(it["part"].upper(), "small", "muted", wrap=False))
            cab.addWidget(Etiqueta(cuello.PRIO_TXT[it["prio"]], "small", pt, wrap=False))
            if it["cost"]:
                cab.addWidget(Etiqueta("coste: " + it["cost"], "small", "muted", wrap=False))
            cab.addStretch(1)
            card.lay.addLayout(cab)
            card.add(Etiqueta(it["title"], "h3"))
            card.add(Etiqueta(it["why"], "small", "muted"))
            self.body_lay.addWidget(card)
