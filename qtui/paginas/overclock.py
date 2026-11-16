"""Pantalla «Overclock seguro»: guía (undervolt y subidas pequeñas) adaptada a TU equipo (versión Qt)."""
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QHBoxLayout, QVBoxLayout, QWidget

import bios
import oc

from ..widgets import Barra, Boton, Etiqueta, Pagina, Tarjeta, fila, vacia

# colores que usa oc.build -> tonos de Qt
TONO = {"green": "green", "red": "red", "yellow": "yellow", "cyan": "teal"}


class Overclock(Pagina):
    titulo_texto = "Overclock seguro"
    sub_texto = "Más rendimiento de tu gráfica, procesador y RAM con pasos adaptados a TU equipo, límites seguros y pruebas."

    def __init__(self, app):
        super().__init__(app)
        self.btn = Boton("⚙   GENERAR MI GUÍA DE OVERCLOCK", self.run, kind="primary", tone="yellow")
        self.msg = Etiqueta("", "muted", wrap=True)
        self.add(fila(self.btn, self.msg, None, espacio=16))
        self.pb = Barra(0, "yellow")
        self.pb.setRange(0, 0)
        self.pb.hide()
        self.add(self.pb)

        intro = Tarjeta(tone="yellow")
        intro.add(Etiqueta(
            "HellOP no cambia nada en este apartado: es una guía de pasos para hacer tú con herramientas gratuitas "
            "(MSI Afterburner, la BIOS, OCCT). Pulsa el botón y leo tu equipo para darte los pasos exactos de tu procesador, "
            "tu gráfica y tu RAM, con límites seguros y cómo volver atrás.", "muted"))
        self.add(intro)

        self.body = QWidget()
        self.body_lay = QVBoxLayout(self.body)
        self.body_lay.setContentsMargins(0, 0, 0, 0)
        self.body_lay.setSpacing(12)
        self.add(self.body)

    # ------------------------------------------------------------------
    def run(self):
        self.btn.set_enabled(False)
        self.msg.setText("Leyendo tu equipo…")
        self.msg.tono("teal")
        self.pb.show()
        cached = self.app.pages["bios"].guide

        def work():
            g = cached or bios.build_guide()
            return g, oc.build(g)

        self.app.bg(work, self.done, self.fail)

    def fail(self, e):
        self.pb.hide()
        self.btn.set_enabled(True)
        self.msg.setText(f"No pude leer tu equipo: {e}")
        self.msg.tono("red")

    def done(self, res):
        guide, (summary, sections) = res
        self.app.pages["bios"].guide = guide
        self.pb.hide()
        self.btn.set_enabled(True)
        self.btn.set_text("↻   GENERAR DE NUEVO")
        self.msg.setText("Guía lista: " + summary)
        self.msg.tono("green")
        vacia(self.body_lay)
        for label, title, steps, color in sections:
            tone = TONO.get(color, "teal")
            c = Tarjeta(tone=tone, titulo=f"{label}  ·  {title}")
            for i, s in enumerate(steps, 1):
                h = QHBoxLayout()
                h.setSpacing(8)
                num = Etiqueta(f"{i}.", "h3", tone, wrap=False)
                num.setFixedWidth(26)
                num.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignTop)
                h.addWidget(num, 0, Qt.AlignmentFlag.AlignTop)
                h.addWidget(Etiqueta(s), 1)
                c.lay.addLayout(h)
            self.body_lay.addWidget(c)
