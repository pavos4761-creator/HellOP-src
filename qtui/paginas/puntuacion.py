"""Pantalla «Puntuación HellOP»: la nota de tu PC con medalla, lo que te resta puntos y tus logros."""
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QHBoxLayout, QVBoxLayout, QWidget

import puntuacion

from ..graficos import Anillo
from ..widgets import Boton, Etiqueta, Insignia, Pagina, Tarjeta, vacia


class Puntuacion(Pagina):
    titulo_texto = "Puntuación HellOP"
    sub_texto = "Una nota para tu PC según lo bien configurado que está, con medallas y logros."

    def __init__(self, app):
        super().__init__(app)
        self.busy = False
        self._loaded = False

        self.btn = Boton("★   CALCULAR MI PUNTUACIÓN", self.run, kind="primary", tone="yellow")
        self.btn.setMinimumHeight(42)
        self.msg = Etiqueta("", None, "muted", wrap=False)
        self.add(fila_barra(self.btn, self.msg))

        c = Tarjeta(tone="muted", titulo="Qué mide (y qué no)")
        for t in ("Mide lo bien configurado que está tu PC: monitor a sus Hz, RAM en dual y con su perfil, juegos en SSD, plan de energía, "
                  "programas de inicio, espacio libre y programas de fondo.",
                  "NO mide la potencia de tu equipo: un PC modesto bien ajustado puede sacar más nota que uno caro mal configurado.",
                  "Cada punto que pierdes tiene su arreglo a un clic."):
            c.add(Etiqueta("•  " + t, "small", "muted"))
        self.add(c)

        self.res = QWidget()
        self.res.setObjectName("pagina")
        self.res_lay = QVBoxLayout(self.res)
        self.res_lay.setContentsMargins(0, 0, 0, 0)
        self.res_lay.setSpacing(12)
        self.add(self.res)

    def al_mostrar(self):
        if not self._loaded:
            self._loaded = True
            self.run()

    # ------------------------------------------------------------------
    def _msg(self, texto, tone):
        self.msg.setText(texto)
        self.msg.tono(tone)

    def run(self):
        if self.busy:
            return
        self.busy = True
        self.btn.set_enabled(False)
        self._msg("Calculando…", "yellow")
        self.app.bg(lambda: puntuacion.calcular(lambda s: self.app.ui(self._msg, s, "yellow")), self._done, self._fail)

    def _fail(self, e):
        self.busy = False
        self.btn.set_enabled(True)
        self._msg(f"Error: {e}", "red")

    def _done(self, r):
        self.busy = False
        self.btn.set_enabled(True)
        self._msg("✓ Listo", "green")
        vacia(self.res_lay)
        name, col = r["medal"]        # col: color hexadecimal de la medalla (viene de la lógica)

        c = Tarjeta(tone="yellow")
        linea = QHBoxLayout()
        linea.setSpacing(24)
        ring = Anillo(0, col, None, name.upper(), 190, 14)
        linea.addWidget(ring, 0, Qt.AlignmentFlag.AlignTop)
        side = QVBoxLayout()
        side.setSpacing(6)
        side.addWidget(Etiqueta("Lo que te resta puntos" if r["perdidos"] else "¡Tu PC está al máximo!", "h2"))
        if not r["perdidos"]:
            side.addWidget(Etiqueta("No encuentro nada que mejorar en lo que mido. Buen trabajo.", None, "green"))
        for title, pts, fix in r["perdidos"][:6]:
            rr = QHBoxLayout()
            rr.setSpacing(10)
            lp = Etiqueta(f"−{pts}", "h3", "red", wrap=False)
            lp.setMinimumWidth(40)
            rr.addWidget(lp, 0, Qt.AlignmentFlag.AlignVCenter)
            rr.addWidget(Etiqueta(title), 1)
            if fix and fix[0] == "goto":
                rr.addWidget(Boton(fix[2], lambda k=fix[1]: self.app.ir(k), kind="soft"), 0, Qt.AlignmentFlag.AlignVCenter)
            side.addLayout(rr)
        side.addStretch(1)
        linea.addLayout(side, 1)
        c.lay.addLayout(linea)
        self.res_lay.addWidget(c)
        ring.pon(r["score"], col, None, name.upper())

        hechos = sum(1 for x in r["logros"] if x["date"])
        lg = Tarjeta(tone="red", titulo=f"Logros  ({hechos}/{len(r['logros'])})")
        for x in r["logros"]:
            on = bool(x["date"])
            rr = QHBoxLayout()
            rr.setSpacing(10)
            st = Etiqueta("★" if on else "☆", "h2", "yellow" if on else "muted", wrap=False)
            st.setFixedWidth(26)
            rr.addWidget(st, 0, Qt.AlignmentFlag.AlignTop)
            tt = Etiqueta(x["title"], "h3", None if on else "muted")
            tt.setMinimumWidth(150)
            tt.setMaximumWidth(190)
            rr.addWidget(tt, 0, Qt.AlignmentFlag.AlignTop)
            rr.addWidget(Etiqueta(x["desc"] + (f"   ({x['date']})" if on else ""), "small", "muted"), 1, Qt.AlignmentFlag.AlignTop)
            if x["id"] in r["nuevos"]:
                rr.addWidget(Insignia("¡Nuevo!", "green"), 0, Qt.AlignmentFlag.AlignTop)
            lg.lay.addLayout(rr)
        self.res_lay.addWidget(lg)


def fila_barra(boton, mensaje):
    """Botón a la izquierda y mensaje de estado a su lado."""
    w = QWidget()
    h = QHBoxLayout(w)
    h.setContentsMargins(0, 0, 0, 0)
    h.setSpacing(16)
    h.addWidget(boton)
    h.addWidget(mensaje, 1)
    return w
