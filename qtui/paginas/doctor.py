"""Pantalla «Doctor»: eliges el síntoma y mira tu PC para decirte las causas más probables."""
import time

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QHBoxLayout, QWidget

import doctor

from ..widgets import Barra, Boton, Etiqueta, Insignia, Pagina, Rejilla, Tarjeta, vacia

COL = {"bad": "red", "warn": "yellow", "info": "accent"}
ETIQ = {"bad": "GRAVE", "warn": "REVISAR", "info": "PISTA"}


class _TarjetaClic(Tarjeta):
    """Tarjeta que reacciona al clic en cualquier punto."""

    def __init__(self, cmd, **kw):
        super().__init__(**kw)
        self._cmd = cmd
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def mousePressEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton:
            self._cmd()
        super().mousePressEvent(e)


class Doctor(Pagina):
    titulo_texto = ""
    sub_texto = ""

    def __init__(self, app):
        super().__init__(app)
        self.hechos, self.t_hechos = None, 0

    def al_mostrar(self):
        self.gen += 1
        self.portada()

    def _limpia(self):
        vacia(self.col)
        self.scroll.verticalScrollBar().setValue(0)

    def portada(self):
        self._limpia()
        self.encabezado("Doctor", "Dime qué te pasa y miro tu PC para decirte por qué. Cada causa sale de un dato real de tu equipo.")
        grid = Rejilla(2, 12)
        for k, ic, t, d in doctor.SINTOMAS:
            c = _TarjetaClic(lambda k_=k: self.diagnostica(k_), tone="red", espacio=6)
            c.add(Etiqueta(f"{ic}  {t}", "h2"))
            c.add(Etiqueta(d, "small", "muted"))
            c.add(Boton("Diagnosticar", lambda k_=k: self.diagnostica(k_), kind="soft", tone="red"), 0, Qt.AlignmentFlag.AlignLeft)
            grid.add(c)
        self.col.addWidget(grid)
        self.col.addWidget(Etiqueta("Tarda unos 15 segundos. Solo lee: no cambia nada en tu PC.", "small", "muted"))

    def diagnostica(self, sintoma):
        self.gen += 1
        g = self.gen
        if self.hechos and time.time() - self.t_hechos < 180:
            self.resultado(sintoma)
            return
        self._limpia()
        self.encabezado("Mirando tu PC…", f"Síntoma: {doctor.NOMBRES[sintoma]}")
        pb = Barra(0, "accent")
        pb.setRange(0, 0)
        pb.setMaximumWidth(380)
        self.col.addWidget(pb, 0, Qt.AlignmentFlag.AlignLeft)
        self.col.addWidget(Etiqueta("Temperaturas, latencia de drivers, errores de Windows, memoria y programas de fondo…", None, "muted"))

        def listo(h):
            if g != self.gen:
                return
            self.hechos, self.t_hechos = h, time.time()
            self.resultado(sintoma)

        def falla(e):
            if g != self.gen:
                return
            self.portada()
            self.app.toast(f"No pude mirar tu PC: {e}", "red")

        self.app.bg(doctor.recoger, listo, falla)

    def _otra_vez(self, sintoma):
        self.hechos = None
        self.diagnostica(sintoma)

    def resultado(self, sintoma):
        self._limpia()
        self.encabezado(doctor.NOMBRES[sintoma], "Esto es lo más probable en tu PC, de más a menos.")
        lista = doctor.para(sintoma, doctor.causas(self.hechos))
        if not lista:
            c = Tarjeta(tone="green")
            c.add(Etiqueta("No veo nada raro en tu PC para este síntoma. Si pasa solo en un juego, mira sus ajustes de vídeo y verifica sus archivos. "
                           "Para algo más fino, usa «Diagnóstico» mientras juegas."))
            self.col.addWidget(c)
        for n, c in enumerate(lista):
            tone = COL.get(c["sev"], "accent")
            card = Tarjeta(tone=tone)
            top = QHBoxLayout()
            top.setSpacing(10)
            top.addWidget(Etiqueta(f"{n + 1}.  " + c["titulo"], "h3"), 1)
            top.addWidget(Insignia("LO MÁS PROBABLE" if n == 0 else ETIQ.get(c["sev"], "PISTA"), tone), 0, Qt.AlignmentFlag.AlignTop)
            card.lay.addLayout(top)
            card.add(Etiqueta(c["detalle"], None, "muted"))
            if c["fix"]:
                _g, page, txt = c["fix"]
                card.add(Boton(txt, lambda p=page: self.app.ir(p), kind="soft", tone=tone), 0, Qt.AlignmentFlag.AlignLeft)
            self.col.addWidget(card)
        fila = QHBoxLayout()
        fila.setSpacing(10)
        fila.addWidget(Boton("← Otro síntoma", self.portada, kind="soft", tone="red"))
        fila.addWidget(Boton("Volver a medir", lambda: self._otra_vez(sintoma), kind="soft"))
        fila.addStretch(1)
        w = QWidget()
        w.setLayout(fila)
        fila.setContentsMargins(0, 4, 0, 0)
        self.col.addWidget(w)
