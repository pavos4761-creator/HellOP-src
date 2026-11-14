"""Gráficos pintados a mano: anillo de nota, línea de evolución (sparkline) y medidor."""
from PySide6.QtCore import QPointF, QRectF, Qt, QPropertyAnimation, QEasingCurve, Property
from PySide6.QtGui import QPainter, QPainterPath, QPen, QLinearGradient, QColor, QFont
from PySide6.QtWidgets import QWidget, QSizePolicy

from . import theme


class Anillo(QWidget):
    """Anillo de progreso con un número grande en el centro y una etiqueta pequeña debajo."""

    def __init__(self, valor=0, tone="accent", texto=None, sub="", tam=150, grosor=12, parent=None):
        super().__init__(parent)
        self._v = 0.0
        self.meta = float(valor)
        self.tone, self.texto, self.sub, self.grosor = tone, texto, sub, grosor
        self.setFixedSize(tam, tam)
        self._anim = QPropertyAnimation(self, b"valor", self)
        self._anim.setDuration(700)
        self._anim.setEasingCurve(QEasingCurve.Type.OutCubic)

    def _get(self):
        return self._v

    def _set(self, v):
        self._v = v
        self.update()

    valor = Property(float, _get, _set)

    def pon(self, valor, tone=None, texto=None, sub=None, animar=True):
        self.meta = float(valor)
        if tone:
            self.tone = tone
        if texto is not None:
            self.texto = texto
        if sub is not None:
            self.sub = sub
        if animar:
            self._anim.stop()
            self._anim.setStartValue(self._v)
            self._anim.setEndValue(self.meta)
            self._anim.start()
        else:
            self._v = self.meta
            self.update()

    def paintEvent(self, _e):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        g = self.grosor
        r = QRectF(g / 2 + 1, g / 2 + 1, self.width() - g - 2, self.height() - g - 2)
        p.setPen(QPen(theme.color("track"), g, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        p.drawArc(r, 0, 360 * 16)
        p.setPen(QPen(theme.color(self.tone), g, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        p.drawArc(r, 90 * 16, int(-360 * 16 * max(0.0, min(100.0, self._v)) / 100.0))
        p.setPen(theme.color("fg"))
        f = theme.fuente(self.width() * 0.26, True)
        p.setFont(f)
        txt = self.texto if self.texto is not None else f"{self._v:.0f}"
        p.drawText(QRectF(0, self.height() * 0.22, self.width(), self.height() * 0.4), Qt.AlignmentFlag.AlignCenter, txt)
        if self.sub:
            p.setPen(theme.color("muted"))
            p.setFont(theme.fuente(max(10, self.width() * 0.085)))
            p.drawText(QRectF(0, self.height() * 0.56, self.width(), self.height() * 0.2), Qt.AlignmentFlag.AlignCenter, self.sub)


class Linea(QWidget):
    """Gráfica de línea con relleno suave. `puntos` es una lista de números; `maximo` fija el techo (p. ej. 100 %)."""

    def __init__(self, tone="accent", maximo=100.0, alto=70, n=60, parent=None):
        super().__init__(parent)
        self.tone, self.maximo, self.n = tone, maximo, n
        self.puntos = []
        self.setMinimumHeight(alto)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setFixedHeight(alto)

    def pon(self, puntos):
        self.puntos = list(puntos)[-self.n:]
        self.update()

    def añade(self, v):
        self.puntos.append(v)
        self.puntos = self.puntos[-self.n:]
        self.update()

    def paintEvent(self, _e):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()
        p.setPen(QPen(theme.color("border"), 1))
        for i in range(1, 4):
            y = h * i / 4
            p.drawLine(0, int(y), w, int(y))
        if len(self.puntos) < 2:
            return
        mx = self.maximo or max(self.puntos) or 1.0
        n = len(self.puntos)
        pts = [QPointF(w * i / max(1, self.n - 1) + (w - w * (n - 1) / max(1, self.n - 1)), h - 3 - (h - 6) * min(1.0, v / mx)) for i, v in enumerate(self.puntos)]
        path = QPainterPath(pts[0])
        for q in pts[1:]:
            path.lineTo(q)
        rel = QPainterPath(path)
        rel.lineTo(pts[-1].x(), h)
        rel.lineTo(pts[0].x(), h)
        rel.closeSubpath()
        gr = QLinearGradient(0, 0, 0, h)
        c1 = theme.color(self.tone)
        c1.setAlphaF(0.30)
        c2 = theme.color(self.tone)
        c2.setAlphaF(0.0)
        gr.setColorAt(0, c1)
        gr.setColorAt(1, c2)
        p.fillPath(rel, gr)
        p.setPen(QPen(theme.color(self.tone), 2, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
        p.drawPath(path)


class Medidor(QWidget):
    """Barra horizontal con etiqueta a la izquierda y valor a la derecha (p. ej. «CPU   37 %»)."""

    def __init__(self, nombre, tone="accent", parent=None):
        super().__init__(parent)
        from .widgets import Barra, Etiqueta
        from PySide6.QtWidgets import QHBoxLayout, QVBoxLayout
        v = QVBoxLayout(self)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(3)
        h = QHBoxLayout()
        self.nombre = Etiqueta(nombre, "small", wrap=False)
        self.valor = Etiqueta("", "small", wrap=False)
        h.addWidget(self.nombre)
        h.addStretch(1)
        h.addWidget(self.valor)
        v.addLayout(h)
        self.barra = Barra(0, tone)
        v.addWidget(self.barra)

    def pon(self, v, texto=None, tone=None):
        self.barra.pon(v, tone)
        self.valor.setText(texto if texto is not None else f"{v:.0f} %")
