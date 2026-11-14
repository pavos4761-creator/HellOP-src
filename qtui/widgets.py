"""Componentes de HellOP: tarjetas, interruptor, botones, insignias, barras, tablas de datos…"""
from PySide6.QtCore import (Property, QEasingCurve, QPropertyAnimation, QRectF, QSize, Qt, QTimer, Signal)
from PySide6.QtGui import QColor, QPainter, QPen, QPainterPath, QBrush
from PySide6.QtWidgets import (QAbstractButton, QCheckBox, QFrame, QGridLayout, QHBoxLayout, QLabel, QProgressBar, QPushButton, QScrollArea,
                               QSizePolicy, QVBoxLayout, QWidget, QGraphicsDropShadowEffect)

from . import theme


def repulir(w):
    """Vuelve a aplicar el estilo tras cambiar una propiedad (role, tone, kind…)."""
    w.style().unpolish(w)
    w.style().polish(w)
    w.update()


def etiqueta(texto="", role=None, tone=None, wrap=True, selectable=False, align=None):
    lb = QLabel(texto)
    if role:
        lb.setProperty("role", role)
    if tone:
        lb.setProperty("tone", tone)
    lb.setWordWrap(wrap)
    lb.setTextFormat(Qt.TextFormat.PlainText)
    if selectable:
        lb.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
    if align:
        lb.setAlignment(align)
    return lb


class Etiqueta(QLabel):
    """QLabel con atajos para papel (title/h2/muted…) y tono (green/yellow/red/accent/teal/muted)."""

    def __init__(self, texto="", role=None, tone=None, wrap=True, parent=None):
        super().__init__(texto, parent)
        self.setWordWrap(wrap)
        self.setTextFormat(Qt.TextFormat.PlainText)
        if role:
            self.setProperty("role", role)
        if tone:
            self.setProperty("tone", tone)
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Minimum)

    def tono(self, tone):
        self.setProperty("tone", tone)
        repulir(self)

    def role(self, r):
        self.setProperty("role", r)
        repulir(self)


class Boton(QPushButton):
    def __init__(self, texto="", cmd=None, kind="primary", tone=None, parent=None, ancho=None):
        super().__init__(texto, parent)
        self.setProperty("kind", kind)
        if tone:
            self.setProperty("tone", tone)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        if cmd:
            self.clicked.connect(lambda _=False: cmd())
        if ancho:
            self.setMinimumWidth(ancho)
        self.setSizePolicy(QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Fixed)

    # compatibilidad con los nombres que usaban las páginas Tk
    def set_text(self, t):
        self.setText(t)

    def set_enabled(self, on):
        self.setEnabled(bool(on))

    def estilo(self, kind=None, tone=None):
        if kind:
            self.setProperty("kind", kind)
        if tone is not None:
            self.setProperty("tone", tone)
        repulir(self)


class Insignia(QLabel):
    """Etiqueta pequeña con fondo suave del color del tono (RIESGO BAJO, EFECTO PEQUEÑO…)."""

    def __init__(self, texto, tone="accent", parent=None):
        super().__init__(texto.upper(), parent)
        self.tone = tone
        self.setTextFormat(Qt.TextFormat.PlainText)
        self.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Fixed)
        self._aplica()

    def pon(self, texto, tone):
        self.setText(texto.upper())
        self.tone = tone
        self._aplica()

    def _aplica(self):
        col = theme.C.get(self.tone, theme.C["accent"])
        self.setStyleSheet(f"QLabel {{ background: {theme.hexa(self.tone, 0.16)}; color: {col}; border-radius: 5px; padding: 3px 8px; "
                           f"font-size: 11px; font-weight: 700; }}")

    def refresca(self):
        self._aplica()


class Interruptor(QAbstractButton):
    """Interruptor tipo Windows 11 con animación."""
    cambio = Signal(bool)

    def __init__(self, on=False, tone="accent", parent=None):
        super().__init__(parent)
        self.setCheckable(True)
        self.setChecked(on)
        self.tone = tone
        self._x = 1.0 if on else 0.0
        self.setFixedSize(46, 24)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._anim = QPropertyAnimation(self, b"pos_x", self)
        self._anim.setDuration(140)
        self._anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self.toggled.connect(self._cambia)

    def _get(self):
        return self._x

    def _set(self, v):
        self._x = v
        self.update()

    pos_x = Property(float, _get, _set)

    def _cambia(self, on):
        self._anim.stop()
        self._anim.setStartValue(self._x)
        self._anim.setEndValue(1.0 if on else 0.0)
        self._anim.start()
        self.cambio.emit(on)

    def poner(self, on, animar=True):
        self.blockSignals(True)
        self.setChecked(on)
        self.blockSignals(False)
        if animar:
            self._cambia_silencio(on)
        else:
            self._x = 1.0 if on else 0.0
            self.update()

    def _cambia_silencio(self, on):
        self._anim.stop()
        self._anim.setStartValue(self._x)
        self._anim.setEndValue(1.0 if on else 0.0)
        self._anim.start()

    def sizeHint(self):
        return QSize(46, 24)

    def paintEvent(self, _e):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()
        on = theme.color(self.tone)
        off = theme.mezcla("track", "muted", 0.25)
        fondo = theme.mezcla("track", self.tone, self._x) if self.isEnabled() else theme.color("track")
        if self._x < 0.02:
            fondo = off
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(fondo)
        p.drawRoundedRect(QRectF(0, 0, w, h), h / 2, h / 2)
        r = h - 8
        x = 4 + (w - 8 - r) * self._x
        p.setBrush(QColor("#ffffff") if self._x > 0.5 else theme.color("panel"))
        if self._x < 0.5:
            p.setBrush(QColor("#ffffff"))
        p.drawEllipse(QRectF(x, 4, r, r))
        if self.hasFocus():
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.setPen(QPen(on, 1.5))
            p.drawRoundedRect(QRectF(1, 1, w - 2, h - 2), h / 2 - 1, h / 2 - 1)


class Casilla(QCheckBox):
    """Casilla de verificación pintada a mano (la de Qt por defecto no sigue nuestro tema)."""

    def __init__(self, texto="", marcada=False, parent=None):
        super().__init__(texto, parent)
        self.setChecked(marcada)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setStyleSheet("QCheckBox { spacing: 10px; background: transparent; } QCheckBox::indicator { width: 0px; height: 0px; }")

    def sizeHint(self):
        s = super().sizeHint()
        return QSize(s.width() + 28, max(s.height(), 24))

    def paintEvent(self, e):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        h = self.height()
        r = QRectF(2, (h - 18) / 2, 18, 18)
        if self.isChecked():
            p.setBrush(theme.color("accent"))
            p.setPen(Qt.PenStyle.NoPen)
            p.drawRoundedRect(r, 5, 5)
            pen = QPen(theme.color("on_accent"), 2.2, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin)
            p.setPen(pen)
            path = QPainterPath()
            path.moveTo(r.left() + 4.5, r.center().y() + 0.5)
            path.lineTo(r.left() + 8, r.bottom() - 5)
            path.lineTo(r.right() - 4, r.top() + 5)
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawPath(path)
        else:
            p.setBrush(theme.color("panel2"))
            p.setPen(QPen(theme.color("muted"), 1.4))
            p.drawRoundedRect(r.adjusted(0.7, 0.7, -0.7, -0.7), 5, 5)
        p.setPen(theme.color("fg") if self.isEnabled() else theme.color("muted"))
        p.setFont(self.font())
        from PySide6.QtCore import QRect
        p.drawText(QRect(28, 0, self.width() - 28, h), int(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft), self.text())


class Tarjeta(QFrame):
    """Tarjeta con borde redondeado. `.lay` es su QVBoxLayout. tone pinta un filo de color a la izquierda."""

    def __init__(self, tone=None, parent=None, margen=16, espacio=8, titulo=None, soft=False):
        super().__init__(parent)
        self.setObjectName("cardsoft" if soft else "card")
        if tone:
            self.setProperty("tone", tone)
        self.lay = QVBoxLayout(self)
        self.lay.setContentsMargins(margen, margen, margen, margen)
        self.lay.setSpacing(espacio)
        if titulo:
            self.lay.addWidget(Etiqueta(titulo, "h2"))

    def add(self, w, *a, **k):
        self.lay.addWidget(w, *a, **k)
        return w

    def tono(self, tone):
        self.setProperty("tone", tone)
        repulir(self)

    def marcada(self, on):
        self.setProperty("sel", "true" if on else "false")
        repulir(self)


class Barra(QProgressBar):
    def __init__(self, valor=0, tone=None, maximo=100, parent=None):
        super().__init__(parent)
        self.setRange(0, maximo)
        self.setValue(int(valor))
        self.setTextVisible(False)
        if tone:
            self.setProperty("tone", tone)
        self.setFixedHeight(8)

    def pon(self, v, tone=None):
        self.setValue(int(max(0, min(self.maximum(), v))))
        if tone is not None:
            self.setProperty("tone", tone)
            repulir(self)


class Separador(QFrame):
    def __init__(self):
        super().__init__()
        self.setObjectName("sep")
        self.setFrameShape(QFrame.Shape.NoFrame)


def fila(*ws, espacio=10, margenes=(0, 0, 0, 0), stretch_ultimo=False):
    w = QWidget()
    w.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, False)
    h = QHBoxLayout(w)
    h.setContentsMargins(*margenes)
    h.setSpacing(espacio)
    for x in ws:
        if x is None:
            h.addStretch(1)
        else:
            h.addWidget(x)
    return w


def columna(*ws, espacio=6, margenes=(0, 0, 0, 0)):
    w = QWidget()
    v = QVBoxLayout(w)
    v.setContentsMargins(*margenes)
    v.setSpacing(espacio)
    for x in ws:
        if x is None:
            v.addStretch(1)
        else:
            v.addWidget(x)
    return w


class Rejilla(QWidget):
    """Cuadrícula de N columnas iguales. add(widget) los coloca en orden."""

    def __init__(self, columnas=3, espacio=12, parent=None):
        super().__init__(parent)
        self.g = QGridLayout(self)
        self.g.setContentsMargins(0, 0, 0, 0)
        self.g.setSpacing(espacio)
        self.n, self.i = columnas, 0
        for c in range(columnas):
            self.g.setColumnStretch(c, 1)

    def add(self, w):
        self.g.addWidget(w, self.i // self.n, self.i % self.n, Qt.AlignmentFlag.AlignTop)
        self.i += 1
        return w

    def limpia(self):
        while self.g.count():
            it = self.g.takeAt(0)
            if it.widget():
                it.widget().deleteLater()
        self.i = 0


def vacia(layout):
    while layout.count():
        it = layout.takeAt(0)
        w = it.widget()
        if w is not None:
            w.setParent(None)
            w.deleteLater()
        elif it.layout() is not None:
            vacia(it.layout())


class Pagina(QWidget):
    """Base de todas las pantallas: título, subtítulo y una columna con scroll. `self.col` es el QVBoxLayout interior."""
    titulo_texto = ""
    sub_texto = ""

    def __init__(self, app, titulo=None, sub=None):
        super().__init__()
        self.setObjectName("pagina")
        self.app = app
        self.gen = 0
        raiz = QVBoxLayout(self)
        raiz.setContentsMargins(0, 0, 0, 0)
        raiz.setSpacing(0)
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.inner = QWidget()
        self.inner.setObjectName("pagina")
        self.col = QVBoxLayout(self.inner)
        self.col.setContentsMargins(4, 2, 18, 24)
        self.col.setSpacing(12)
        self.col.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.scroll.setWidget(self.inner)
        raiz.addWidget(self.scroll, 1)
        self.pie = None
        t = titulo if titulo is not None else self.titulo_texto
        s = sub if sub is not None else self.sub_texto
        if t:
            self.encabezado(t, s)

    def encabezado(self, titulo, sub=""):
        self.col.addWidget(Etiqueta(titulo, "title"))
        if sub:
            self.sub = Etiqueta(sub, "muted")
            self.col.addWidget(self.sub)
            self.col.addSpacing(6)

    def add(self, w, *a, **k):
        self.col.addWidget(w, *a, **k)
        return w

    def limpia(self):
        self.gen += 1
        vacia(self.col)

    def barra_inferior(self):
        """Barra fija abajo (fuera del scroll). Devuelve el QHBoxLayout."""
        if self.pie is None:
            self.pie = QFrame()
            self.pie.setObjectName("barra")
            self.layout().addSpacing(8)
            self.layout().addWidget(self.pie)
            self.hpie = QHBoxLayout(self.pie)
            self.hpie.setContentsMargins(16, 10, 16, 10)
        return self.hpie

    def al_mostrar(self):
        """Se llama cada vez que la pantalla se abre."""

    def al_ocultar(self):
        """Se llama al salir de la pantalla."""

    def sombra(self, w, blur=24, dy=4, alpha=40):
        ef = QGraphicsDropShadowEffect(w)
        ef.setBlurRadius(blur)
        ef.setOffset(0, dy)
        ef.setColor(theme.color("shadow", alpha / 255))
        w.setGraphicsEffect(ef)


from PySide6.QtWidgets import QAbstractItemView, QHeaderView, QTableWidget, QTableWidgetItem  # noqa: E402


class Tabla(QTableWidget):
    """Tabla de solo lectura con filas alternas. `rellena(filas)` recibe una lista de listas de texto.
    `tonos` (opcional) es una lista paralela con el tono de cada fila (green/yellow/red/muted) para colorear la primera columna."""

    def __init__(self, columnas, anchos=None, alto_fila=34, parent=None):
        super().__init__(0, len(columnas), parent)
        self.setHorizontalHeaderLabels(columnas)
        self.verticalHeader().setVisible(False)
        self.verticalHeader().setDefaultSectionSize(alto_fila)
        self.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.setAlternatingRowColors(True)
        self.setShowGrid(False)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        hh = self.horizontalHeader()
        hh.setStretchLastSection(True)
        hh.setHighlightSections(False)
        if anchos:
            for i, a in enumerate(anchos):
                if a:
                    self.setColumnWidth(i, a)
                else:
                    hh.setSectionResizeMode(i, QHeaderView.ResizeMode.Stretch)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

    def rellena(self, filas, tonos=None, alto_max=None):
        self.setRowCount(len(filas))
        for r, fila in enumerate(filas):
            for c, v in enumerate(fila):
                it = QTableWidgetItem(str(v))
                if c == 0 and tonos and tonos[r]:
                    it.setForeground(theme.color(tonos[r]))
                self.setItem(r, c, it)
        h = self.horizontalHeader().height() + self.rowCount() * self.verticalHeader().defaultSectionSize() + 4
        self.setFixedHeight(min(h, alto_max) if alto_max else h)

    def seleccion(self):
        f = self.currentRow()
        return f if f >= 0 else None
