"""Pantalla «Monitor en el móvil»: servidor local de solo lectura + código QR para abrirlo desde el móvil."""
from PySide6.QtCore import QRectF, QSize, Qt, QTimer
from PySide6.QtGui import QGuiApplication, QPainter
from PySide6.QtWidgets import QSizePolicy, QWidget

import movil

from ..widgets import Boton, Etiqueta, Pagina, Tarjeta


class CodigoQR(QWidget):
    """Dibuja la matriz de módulos del QR (fondo blanco y módulos negros, como exige un QR)."""
    PX = 5

    def __init__(self, parent=None):
        super().__init__(parent)
        self.matriz = None
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self.setFixedSize(1, 1)

    def pon(self, matriz):
        self.matriz = matriz
        if matriz:
            tot = (len(matriz) + 4) * self.PX
            self.setFixedSize(tot, tot)
        else:
            self.setFixedSize(1, 1)
        self.update()

    def sizeHint(self):
        return self.size() if self.matriz else QSize(1, 1)

    def paintEvent(self, _e):
        if not self.matriz:
            return
        p = QPainter(self)
        px = self.PX
        p.fillRect(self.rect(), Qt.GlobalColor.white)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(Qt.GlobalColor.black)
        for y, fila in enumerate(self.matriz):
            for x, v in enumerate(fila):
                if v:
                    p.drawRect(QRectF((x + 2) * px, (y + 2) * px, px, px))


class Movil(Pagina):
    titulo_texto = "Monitor en el móvil"
    sub_texto = "Mira CPU, gráfica y temperaturas de tu PC en el móvil mientras juegas."

    def __init__(self, app):
        super().__init__(app)
        c = Tarjeta(tone="accent", titulo="Cómo funciona")
        for t in ("Enciendes el monitor, escaneas el código con la cámara del móvil (o escribes el enlace) y se abre una página con tus datos en vivo.",
                  "Tu móvil y tu PC deben estar en el mismo Wi-Fi. No sale a Internet ni abre nada en tu router.",
                  "Es solo lectura y lleva una clave al azar dentro del enlace; cambia cada vez que lo enciendes. Se apaga al cerrar HellOP.",
                  "Windows te preguntará si permites el acceso: marca «Redes privadas». La conexión no va cifrada, úsalo en tu casa, no en Wi-Fi públicas."):
            c.add(Etiqueta("•  " + t))
        self.add(c)

        self.card = Tarjeta(tone="accent", titulo="Estado")
        self.estado = Etiqueta("Apagado", "h3", "muted")
        self.card.add(self.estado)
        self.link = Etiqueta("", "small", "accent")
        self.link.setCursor(Qt.CursorShape.PointingHandCursor)
        self.link.setTextInteractionFlags(Qt.TextInteractionFlag.NoTextInteraction)
        self.link.mousePressEvent = lambda _e: self.copia()
        self.card.add(self.link)
        self.qr = CodigoQR()
        self.card.add(self.qr, 0, Qt.AlignmentFlag.AlignLeft)
        self.btn = Boton("Encender", self.alterna, kind="primary")
        self.card.add(self.btn, 0, Qt.AlignmentFlag.AlignLeft)
        self.add(self.card)

        self.timer = QTimer(self)
        self.timer.setInterval(1500)
        self.timer.timeout.connect(self._refresca)

    def al_mostrar(self):
        self.pinta()
        self.timer.start()

    def al_ocultar(self):
        self.timer.stop()

    def apaga(self):
        self.timer.stop()

    def _refresca(self):
        if movil.encendido():
            self.pinta(solo_estado=True)

    def _estado(self, texto, tone):
        self.estado.setText(texto)
        self.estado.tono(tone)

    def pinta(self, solo_estado=False):
        if movil.encendido():
            if movil.conectado():
                self._estado("● Encendido · un móvil está mirando", "green")
            else:
                self._estado("● Encendido · esperando a tu móvil", "yellow")
            if solo_estado:
                return
            url = movil.enlace()
            self.link.setText(url + "   (pulsa para copiar)")
            self.btn.set_text("Apagar")
            self.qr.pon(movil.matriz_qr(url))
        else:
            self._estado("Apagado", "muted")
            self.link.setText("")
            self.qr.pon(None)
            self.btn.set_text("Encender")

    def alterna(self):
        try:
            if movil.encendido():
                movil.apagar()
                self.app.toast("Monitor en el móvil apagado", "accent")
            else:
                movil.encender()
                self.app.toast("Monitor en el móvil encendido", "green")
        except OSError as e:
            self.app.toast(str(e), "red")
        self.pinta()

    def copia(self):
        u = movil.enlace()
        if u:
            QGuiApplication.clipboard().setText(u)
            self.app.toast("Enlace copiado", "green")
