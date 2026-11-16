"""Pantalla que sustituye a una página PRO cuando no hay clave activa."""
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QHBoxLayout

import licencia as lic

from ..widgets import Boton, Etiqueta, Insignia, Pagina


class Bloqueada(Pagina):
    def __init__(self, app):
        super().__init__(app, titulo="", sub="")
        self.col.setAlignment(Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignVCenter)
        self.col.addStretch(1)
        self.insignia = Insignia("FUNCIÓN PRO", "yellow")
        self.col.addWidget(self.insignia, 0, Qt.AlignmentFlag.AlignHCenter)
        self.titulo = Etiqueta("", "title", wrap=True)
        self.titulo.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        self.col.addWidget(self.titulo)
        self.msg = Etiqueta("", "muted")
        self.msg.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        self.msg.setMaximumWidth(560)
        self.col.addWidget(self.msg, 0, Qt.AlignmentFlag.AlignHCenter)
        self.col.addSpacing(8)
        botones = QHBoxLayout()
        botones.setSpacing(10)
        botones.addStretch(1)
        botones.addWidget(Boton("Activar mi clave", lambda: self.app.ir("license"), kind="primary", tone="yellow"))
        botones.addWidget(Boton("Volver al inicio", lambda: self.app.ir("home"), kind="soft"))
        botones.addStretch(1)
        self.col.addLayout(botones)
        self.col.addStretch(2)

    def pon(self, nombre):
        st = lic.status()
        self.titulo.setText(nombre)
        extra = {"expired": st["msg"] + " Pide una clave nueva a quien te dio la anterior.",
                 "invalid": st["msg"]}.get(st["level"], "Esta función es de la versión PRO. Necesitas una clave de activación.")
        self.msg.setText(extra)
