"""Ventana principal de HellOP en Qt: barra de título propia, menú lateral con grupos, páginas perezosas, avisos."""
import base64
import importlib
import json
import os
import sys
import unicodedata

import psutil
from PySide6.QtCore import QEasingCurve, QPoint, QPropertyAnimation, QRect, QSize, Qt, QTimer, QEvent
from PySide6.QtGui import QAction, QColor, QCursor, QFont, QGuiApplication, QIcon, QKeySequence, QPainter, QPixmap, QShortcut
from PySide6.QtWidgets import (QApplication, QFrame, QHBoxLayout, QLabel, QLineEdit, QListWidget, QListWidgetItem, QMainWindow, QMessageBox,
                               QPushButton, QScrollArea, QSizePolicy, QStackedWidget, QVBoxLayout, QWidget, QGraphicsOpacityEffect)

import licencia
import logo_data
import updater
import version
from util import APP_DIR, DEMO, IS_WIN, is_admin, relaunch_as_admin

from . import theme
from .bridge import Puente
from .widgets import Barra, Boton, Etiqueta, Insignia, Tarjeta, repulir

SECTIONS = [
    ("INICIO", [("home", "⌂", "Inicio"), ("analysis", "◎", "Análisis de PC"), ("score", "★", "Puntuación")]),
    ("OPTIMIZAR", [("optimize", "⚡", "Optimizar"), ("streaming", "◉", "Streaming"), ("mando", "✜", "Mando"), ("clean", "✦", "Limpieza"),
                   ("shaders", "❖", "Limpiar shaders"), ("arranque", "⏻", "Gestor de arranque")]),
    ("GAMING", [("games", "▣", "Mis juegos"), ("gameprof", "✧", "Ajustes de juego"), ("booster", "☢", "Modo Extremo"), ("monitor", "≈", "Monitor"),
                ("noche", "☾", "Modo noche"), ("movil", "▯", "Monitor en el móvil"), ("diag", "◈", "Diagnóstico"), ("doctor", "✚", "Doctor"),
                ("fps", "▤", "FPS reales")]),
    ("AVANZADO", [("tweaks", "☄", "Tweaks"), ("cuello", "⬆", "Qué pieza mejorar"), ("bios", "▦", "BIOS"), ("oc", "⚙", "Overclock")]),
    ("SISTEMA", [("health", "♥", "Salud del PC"), ("debloat", "✖", "Quitar bloatware"), ("history", "↺", "Historial / Deshacer"),
                 ("update", "⟳", "Actualizaciones"), ("license", "◇", "Licencia")]),
]
PAGES = [i for _t, items in SECTIONS for i in items]
NOMBRES = {k: t for k, _i, t in PAGES}

# clave → (módulo, clase). Cada pantalla se crea la primera vez que se abre.
FABRICA = {
    "home": ("home", "Inicio"), "analysis": ("analisis", "Analisis"), "score": ("puntuacion", "Puntuacion"),
    "optimize": ("optimizar", "Optimizar"), "streaming": ("optimizar", "Streaming"), "mando": ("optimizar", "Mando"),
    "clean": ("limpieza", "Limpieza"), "shaders": ("shaders", "Shaders"), "arranque": ("arranque", "Arranque"),
    "games": ("juegos", "Juegos"), "gameprof": ("ajustes_juego", "AjustesJuego"), "booster": ("extremo", "Extremo"),
    "monitor": ("monitor", "Monitor"), "noche": ("noche", "Noche"), "movil": ("movil", "Movil"), "diag": ("diagnostico", "Diagnostico"),
    "doctor": ("doctor", "Doctor"), "fps": ("fps", "Fps"), "tweaks": ("tweaks", "Tweaks"), "cuello": ("cuello", "Cuello"),
    "bios": ("bios", "Bios"), "oc": ("overclock", "Overclock"), "health": ("salud", "Salud"), "debloat": ("bloatware", "Bloatware"),
    "history": ("historial", "Historial"), "update": ("actualizar", "Actualizar"), "license": ("licencia_pagina", "Licencia"),
    "locked": ("bloqueada", "Bloqueada"),
}

BORDE = 6        # grosor de la zona de redimensionado


def _pix(b64, size=None):
    p = QPixmap()
    p.loadFromData(base64.b64decode(b64))
    if size:
        p = p.scaled(size, size, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
    return p


def _norm(s):
    return "".join(c for c in unicodedata.normalize("NFD", s.lower()) if unicodedata.category(c) != "Mn")


class _Paginas(dict):
    def __init__(self, ventana):
        super().__init__()
        self.v = ventana

    def __missing__(self, key):
        mod, cls = FABRICA[key]
        try:
            pagina = getattr(importlib.import_module(f"qtui.paginas.{mod}"), cls)(self.v)
        except ModuleNotFoundError as e:
            if not str(e).startswith("No module named 'qtui.paginas"):
                raise
            from .widgets import Pagina
            pagina = Pagina(self.v, NOMBRES.get(key, key), "Esta pantalla se está montando.")
            pagina.pendiente = True
        self.v.stack.addWidget(pagina)
        self[key] = pagina
        return pagina

    def creada(self, key):
        return dict.__contains__(self, key)


class BotonNav(QPushButton):
    def __init__(self, icono, texto, cmd):
        super().__init__(f"  {icono}   {texto}")
        self.setObjectName("nav")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedHeight(34)
        self.clicked.connect(lambda _=False: cmd())
        self.base = f"  {icono}   {texto}"
        self.pro = False
        self.punto = None

    def activo(self, on):
        self.setProperty("activo", "true" if on else "false")
        repulir(self)

    def marca_pro(self, on):
        self.pro = on
        self.setText(self.base + ("      PRO" if on else ""))

    def paintEvent(self, e):
        super().paintEvent(e)
        if self.punto:
            p = QPainter(self)
            p.setRenderHint(QPainter.RenderHint.Antialiasing)
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(theme.color(self.punto))
            p.drawEllipse(self.width() - 20, self.height() // 2 - 4, 8, 8)


class Buscador(QFrame):
    """Ctrl+K: escribe y salta a cualquier apartado."""

    def __init__(self, ventana):
        super().__init__(ventana, Qt.WindowType.Popup | Qt.WindowType.FramelessWindowHint)
        self.v = ventana
        self.setObjectName("card")
        lay = QVBoxLayout(self)
        lay.setContentsMargins(10, 10, 10, 10)
        self.ed = QLineEdit()
        self.ed.setPlaceholderText("Buscar o saltar a…")
        self.lista = QListWidget()
        self.lista.setFrameShape(QFrame.Shape.NoFrame)
        lay.addWidget(self.ed)
        lay.addWidget(self.lista)
        self.resize(520, 360)
        self.ed.textChanged.connect(self.filtra)
        self.ed.returnPressed.connect(self.elige)
        self.lista.itemActivated.connect(lambda _i: self.elige())
        self.lista.itemClicked.connect(lambda _i: self.elige())
        try:
            import paleta
            self.claves = paleta.CLAVES
        except Exception:  # noqa: BLE001
            self.claves = {}
        self.items = [(k, t, self.claves.get(k, "")) for k, _i, t in PAGES] + [
            ("cmd:informe", "Exportar informe", self.claves.get("cmd:informe", "")),
            ("cmd:modo", "Cambiar modo claro / oscuro", self.claves.get("cmd:modo", "")),
            ("cmd:atras", "Volver atrás", self.claves.get("cmd:atras", ""))]

    def abre(self):
        g = self.v.geometry()
        self.move(g.x() + (g.width() - self.width()) // 2, g.y() + 60)
        self.ed.clear()
        self.filtra("")
        self.show()
        self.ed.setFocus()

    def filtra(self, txt):
        q = _norm(txt).split()
        self.lista.clear()
        for k, t, extra in self.items:
            h = _norm(t + " " + extra)
            if all(w in h for w in q):
                it = QListWidgetItem(t)
                it.setData(Qt.ItemDataRole.UserRole, k)
                self.lista.addItem(it)
        if self.lista.count():
            self.lista.setCurrentRow(0)

    def keyPressEvent(self, e):
        if e.key() == Qt.Key.Key_Down:
            self.lista.setCurrentRow(min(self.lista.count() - 1, self.lista.currentRow() + 1))
        elif e.key() == Qt.Key.Key_Up:
            self.lista.setCurrentRow(max(0, self.lista.currentRow() - 1))
        elif e.key() == Qt.Key.Key_Escape:
            self.close()
        else:
            super().keyPressEvent(e)

    def elige(self):
        it = self.lista.currentItem()
        if not it:
            return
        k = it.data(Qt.ItemDataRole.UserRole)
        self.close()
        if k == "cmd:informe":
            self.v.exportar_informe()
        elif k == "cmd:modo":
            self.v.cambia_modo()
        elif k == "cmd:atras":
            self.v.navega(-1)
        else:
            self.v.ir(k)


class Aviso(QLabel):
    """Aviso flotante abajo a la derecha."""

    def __init__(self, parent):
        super().__init__(parent)
        self.setObjectName("toast")
        self.setWordWrap(True)
        self.setMaximumWidth(380)
        self.hide()
        self.t = QTimer(self)
        self.t.setSingleShot(True)
        self.t.timeout.connect(self.hide)

    def muestra(self, texto, tone="accent", ms=4500):
        col = theme.C.get(tone, theme.C["accent"])
        self.setStyleSheet(f"QLabel#toast {{ border-left: 4px solid {col}; }}")
        self.setText(texto)
        self.adjustSize()
        self.reposiciona()
        self.show()
        self.raise_()
        self.t.start(ms)

    def reposiciona(self):
        p = self.parentWidget()
        if p:
            self.move(p.width() - self.width() - 22, p.height() - self.height() - 22)


class Ventana(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowFlag(Qt.WindowType.FramelessWindowHint, True)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setMouseTracking(True)
        self.setMinimumSize(980, 640)
        self.setWindowTitle("HellOP" + (" · MODO DEMO" if DEMO else ""))
        self.setWindowIcon(QIcon(_pix(logo_data.LOGO_64)))
        self.puente = Puente(self._error_por_defecto)
        self.current = None
        self._hist, self._hist_i = [], -1
        self._upd_btn = None
        self._arrastre = None
        self.setGeometry(self._geometria())
        self._construye()
        self.pages = _Paginas(self)
        self._atajos()
        self.refresh_license()
        self.ir("home")
        QTimer.singleShot(1500, self._tick_live)
        QTimer.singleShot(4000, self._auto_check)
        QTimer.singleShot(6000, self._check_revoked)
        QTimer.singleShot(3000, self._admin_prompt)
        QTimer.singleShot(1200, self._asistente_primera_vez)
        QTimer.singleShot(3200, self._arranca_juegos)
        self.live = QTimer(self)
        self.live.timeout.connect(self._tick_live)
        self.live.start(1500)
        try:
            import booster
            rec = booster.recover_after_crash()
            if rec:
                self.status("Se reanudaron servicios que el Modo Extremo había pausado: " + ", ".join(rec))
        except Exception:  # noqa: BLE001
            pass

    # ---- construcción ---------------------------------------------------------------
    def _construye(self):
        raiz = QWidget()
        raiz.setObjectName("raiz")
        self.setCentralWidget(raiz)
        marco = QVBoxLayout(raiz)
        marco.setContentsMargins(0, 0, 0, 0)
        self.ventana = QWidget()
        self.ventana.setObjectName("ventana")
        marco.addWidget(self.ventana)
        v = QVBoxLayout(self.ventana)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(0)
        v.addWidget(self._titulo())
        cuerpo = QHBoxLayout()
        cuerpo.setContentsMargins(12, 4, 12, 10)
        cuerpo.setSpacing(12)
        cuerpo.addWidget(self._lateral())
        derecha = QVBoxLayout()
        derecha.setSpacing(4)
        self.stack = QStackedWidget()
        derecha.addWidget(self.stack, 1)
        self.lbl_estado = Etiqueta("", "small", wrap=False)
        derecha.addWidget(self.lbl_estado)
        cuerpo.addLayout(derecha, 1)
        v.addLayout(cuerpo, 1)
        self.aviso = Aviso(self.ventana)

    def _titulo(self):
        f = QFrame()
        f.setObjectName("titulo")
        f.setFixedHeight(54)
        h = QHBoxLayout(f)
        h.setContentsMargins(14, 8, 8, 4)
        h.setSpacing(10)
        logo = QLabel()
        logo.setPixmap(_pix(logo_data.LOGO_64, 30))
        h.addWidget(logo)
        nom = QLabel("Hell <span style='color:%s'>OP</span>" % theme.C["accent"])
        nom.setTextFormat(Qt.TextFormat.RichText)
        nom.setStyleSheet("font-size: 21px; font-weight: 800; letter-spacing: 1px;")
        h.addWidget(nom)
        h.addSpacing(14)
        self.busca = QPushButton("   Buscar o saltar a…   (Ctrl K)")
        self.busca.setProperty("kind", "ghost")
        self.busca.setCursor(Qt.CursorShape.PointingHandCursor)
        self.busca.setFixedSize(300, 34)
        self.busca.setStyleSheet("text-align: left; font-weight: 400; color: %s;" % theme.C["muted"])
        self.busca.clicked.connect(self.abrir_buscador)
        h.addWidget(self.busca)
        h.addStretch(1)
        self.zona_der = QHBoxLayout()
        self.zona_der.setSpacing(8)
        h.addLayout(self.zona_der)
        self.btn_modo = Boton("", self.cambia_modo, kind="ghost")
        self._texto_modo()
        h.addWidget(self.btn_modo)
        for txt, nombre, cmd in (("–", "win", self.showMinimized), ("▢", "win", self._maximiza), ("✕", "winx", self.close)):
            b = QPushButton(txt)
            b.setObjectName(nombre)
            b.setCursor(Qt.CursorShape.ArrowCursor)
            b.setFixedSize(40, 30)
            b.clicked.connect(lambda _=False, c=cmd: c())
            h.addWidget(b)
        f.installEventFilter(self)
        self._titlebar = f
        return f

    def _lateral(self):
        lat = QFrame()
        lat.setObjectName("sidebar")
        lat.setFixedWidth(232)
        v = QVBoxLayout(lat)
        v.setContentsMargins(8, 8, 8, 10)
        v.setSpacing(0)
        sc = QScrollArea()
        sc.setWidgetResizable(True)
        sc.setFrameShape(QFrame.Shape.NoFrame)
        sc.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        cont = QWidget()
        cont.setObjectName("pagina")
        lv = QVBoxLayout(cont)
        lv.setContentsMargins(0, 0, 4, 0)
        lv.setSpacing(1)
        self.nav, self.grupos, self.botones_grupo = {}, {}, {}
        for titulo, items in SECTIONS:
            gb = QPushButton(f"▾  {titulo}")
            gb.setObjectName("grupo")
            gb.setCursor(Qt.CursorShape.PointingHandCursor)
            lv.addWidget(gb)
            caja = QWidget()
            cv = QVBoxLayout(caja)
            cv.setContentsMargins(0, 0, 0, 4)
            cv.setSpacing(1)
            for k, ic, t in items:
                b = BotonNav(ic, t, lambda k=k: self.ir(k))
                self.nav[k] = b
                cv.addWidget(b)
            lv.addWidget(caja)
            self.grupos[titulo] = caja
            self.botones_grupo[titulo] = gb
            gb.clicked.connect(lambda _=False, c=caja, g=gb, t=titulo: self._pliega(c, g, t))
            if titulo in ("GAMING", "AVANZADO"):
                caja.hide()
                gb.setText(f"▸  {titulo}")
        lv.addStretch(1)
        sc.setWidget(cont)
        v.addWidget(sc, 1)
        live = QVBoxLayout()
        live.setSpacing(3)
        live.addWidget(Etiqueta("● EN VIVO", "small", "green", wrap=False))
        self.bar_cpu, self.lbl_cpu = self._mini("CPU", live)
        self.bar_ram, self.lbl_ram = self._mini("RAM", live)
        v.addLayout(live)
        return lat

    def _mini(self, nombre, lay):
        fila = QHBoxLayout()
        fila.addWidget(Etiqueta(nombre, "small", wrap=False))
        fila.addStretch(1)
        lb = Etiqueta("0%", "small", wrap=False)
        fila.addWidget(lb)
        lay.addLayout(fila)
        b = Barra(0)
        b.setFixedHeight(5)
        lay.addWidget(b)
        return b, lb

    def _pliega(self, caja, boton, titulo):
        caja.setVisible(not caja.isVisible())
        boton.setText(("▾  " if caja.isVisible() else "▸  ") + titulo)

    def _texto_modo(self):
        self.btn_modo.setText("☀  Claro" if theme.MODO == "oscuro" else "☾  Oscuro")

    # ---- arrastrar / redimensionar la ventana sin marco -------------------------------
    def eventFilter(self, obj, ev):
        if obj is self._titlebar:
            if ev.type() == QEvent.Type.MouseButtonPress and ev.button() == Qt.MouseButton.LeftButton:
                if self._borde(ev.globalPosition().toPoint()) == 0:
                    wh = self.windowHandle()
                    if wh:
                        wh.startSystemMove()
                        return True
            elif ev.type() == QEvent.Type.MouseButtonDblClick:
                self._maximiza()
                return True
        return super().eventFilter(obj, ev)

    def _borde(self, gp):
        p = self.mapFromGlobal(gp)
        r = self.rect()
        e = 0
        if p.x() <= BORDE:
            e |= 1
        if p.x() >= r.width() - BORDE:
            e |= 2
        if p.y() <= BORDE:
            e |= 4
        if p.y() >= r.height() - BORDE:
            e |= 8
        return e if not self.isMaximized() else 0

    def mouseMoveEvent(self, ev):
        e = self._borde(ev.globalPosition().toPoint())
        cur = {1: Qt.CursorShape.SizeHorCursor, 2: Qt.CursorShape.SizeHorCursor, 4: Qt.CursorShape.SizeVerCursor, 8: Qt.CursorShape.SizeVerCursor,
               5: Qt.CursorShape.SizeFDiagCursor, 10: Qt.CursorShape.SizeFDiagCursor, 6: Qt.CursorShape.SizeBDiagCursor,
               9: Qt.CursorShape.SizeBDiagCursor}.get(e)
        self.setCursor(cur if cur else Qt.CursorShape.ArrowCursor)
        super().mouseMoveEvent(ev)

    def mousePressEvent(self, ev):
        if ev.button() == Qt.MouseButton.LeftButton:
            e = self._borde(ev.globalPosition().toPoint())
            if e:
                edges = Qt.Edge(0)
                if e & 1:
                    edges |= Qt.Edge.LeftEdge
                if e & 2:
                    edges |= Qt.Edge.RightEdge
                if e & 4:
                    edges |= Qt.Edge.TopEdge
                if e & 8:
                    edges |= Qt.Edge.BottomEdge
                wh = self.windowHandle()
                if wh:
                    wh.startSystemResize(edges)
                    return
        super().mousePressEvent(ev)

    def _maximiza(self):
        if self.isMaximized():
            self.showNormal()
        else:
            self.showMaximized()

    def resizeEvent(self, e):
        super().resizeEvent(e)
        if hasattr(self, "aviso"):
            self.aviso.reposiciona()

    # ---- geometría ----------------------------------------------------------------------
    def _geometria(self):
        pant = QGuiApplication.primaryScreen().availableGeometry()
        w, h = min(1240, pant.width() - 40), min(820, pant.height() - 60)
        x, y = pant.x() + (pant.width() - w) // 2, pant.y() + max(0, (pant.height() - h) // 2 - 10)
        try:
            g = json.loads((APP_DIR / "ventana_qt.json").read_text("utf-8"))
            gw, gh, gx, gy = int(g["w"]), int(g["h"]), int(g["x"]), int(g["y"])
            if pant.contains(QPoint(gx + 100, gy + 30)) and gw >= 980 and gh >= 640:
                x, y, w, h = gx, gy, min(gw, pant.width()), min(gh, pant.height())
        except Exception:  # noqa: BLE001
            pass
        return QRect(x, y, w, h)

    def _guarda_geometria(self):
        try:
            if self.isMaximized():
                return
            g = self.geometry()
            APP_DIR.mkdir(parents=True, exist_ok=True)
            (APP_DIR / "ventana_qt.json").write_text(json.dumps({"x": g.x(), "y": g.y(), "w": g.width(), "h": g.height()}), "utf-8")
        except Exception:  # noqa: BLE001
            pass

    def _atajos(self):
        for seq, fn in (("Ctrl+K", self.abrir_buscador), ("Alt+Left", lambda: self.navega(-1)), ("Alt+Right", lambda: self.navega(1))):
            QShortcut(QKeySequence(seq), self, activated=fn)

    # ---- navegación -----------------------------------------------------------------------
    def ir(self, key, _hist=True):
        if key != self.current and key != "locked" and _hist:
            self._hist = self._hist[:self._hist_i + 1] + [key]
            self._hist_i = len(self._hist) - 1
        if self.current and self.pages.creada(self._real(self.current)):
            try:
                self.pages[self._real(self.current)].al_ocultar()
            except Exception:  # noqa: BLE001
                pass
        for k, b in self.nav.items():
            b.activo(k == key)
        self.current = key
        # abre el grupo que contiene la página
        for t, items in SECTIONS:
            if any(k == key for k, _i, _n in items) and not self.grupos[t].isVisible():
                self.grupos[t].show()
                self.botones_grupo[t].setText(f"▾  {t}")
        if licencia.locked(key):
            self.pages["locked"].pon(NOMBRES.get(key, key))
            page = self.pages["locked"]
        else:
            page = self.pages[key]
        self.stack.setCurrentWidget(page)
        self._entra(page)
        try:
            page.al_mostrar()
        except Exception:  # noqa: BLE001
            self._registra_error()

    def _real(self, key):
        return "locked" if licencia.locked(key) else key

    def _entra(self, page):
        """Aparece con un fundido corto."""
        ef = QGraphicsOpacityEffect(page)
        page.setGraphicsEffect(ef)
        a = QPropertyAnimation(ef, b"opacity", page)
        a.setDuration(160)
        a.setStartValue(0.0)
        a.setEndValue(1.0)
        a.setEasingCurve(QEasingCurve.Type.OutCubic)
        a.finished.connect(lambda: page.setGraphicsEffect(None))
        a.start()
        self._anim = a

    def navega(self, delta):
        i = self._hist_i + delta
        if 0 <= i < len(self._hist):
            self._hist_i = i
            self.ir(self._hist[i], _hist=False)

    # ---- servicios que usan las pantallas ------------------------------------------------
    def bg(self, fn, done=None, fail=None):
        self.puente.bg(fn, done, fail)

    def ui(self, fn, *args):
        self.puente.ui(fn, *args)

    def after(self, ms, fn):
        QTimer.singleShot(int(ms), fn)

    def status(self, texto):
        self.lbl_estado.setText(texto)

    def toast(self, texto, color=None, ms=4500):
        tone = {"GREEN": "green", "RED": "red", "YELLOW": "yellow"}.get(color, color) if isinstance(color, str) else "accent"
        if tone not in theme.TONOS:
            tone = "accent"
        self.aviso.muestra(texto, tone, ms)

    def _error_por_defecto(self, e):
        self.status(f"Error: {e}")
        self.toast("Algo no salió bien. Queda anotado en errores.log", "red")

    def _registra_error(self):
        import traceback
        self.puente._registra(traceback.format_exc())
        self.toast("Algo no salió bien. Queda anotado en errores.log", "red")

    def pregunta(self, titulo, texto):
        return QMessageBox.question(self, titulo, texto) == QMessageBox.StandardButton.Yes

    def info(self, titulo, texto):
        QMessageBox.information(self, titulo, texto)

    def aviso_modal(self, titulo, texto):
        QMessageBox.warning(self, titulo, texto)

    # ---- licencia / actualizaciones -----------------------------------------------------
    def refresh_license(self):
        st = licencia.status()
        txt = {"owner": "CREADOR", "pro": "PRO" + (f" · {st['days']} d" if st["days"] is not None else ""), "free": "GRATIS",
               "expired": "CLAVE CADUCADA", "invalid": "CLAVE NO VÁLIDA"}[st["level"]]
        tone = {"owner": "teal", "pro": "accent", "free": "muted", "expired": "yellow", "invalid": "red"}[st["level"]]
        for w in getattr(self, "_insig", []):
            w.setParent(None)
            w.deleteLater()
        self._insig = []
        lic = Insignia(txt, tone)
        lic.setCursor(Qt.CursorShape.PointingHandCursor)
        lic.mousePressEvent = lambda e: self.ir("license")
        self.zona_der.addWidget(lic)
        self._insig.append(lic)
        if is_admin() or DEMO:
            ad = Insignia("administrador", "green")
            self.zona_der.addWidget(ad)
            self._insig.append(ad)
        for k, b in self.nav.items():
            b.marca_pro(licencia.locked(k))
        if self._upd_btn is not None:
            self.zona_der.insertWidget(0, self._upd_btn)
        if self.pages.creada("home"):
            home = self.pages["home"]
            if hasattr(home, "caja_lic"):
                home.caja_lic(st)

    def mark_update_available(self, latest):
        if self._upd_btn is not None:
            return
        self._upd_btn = Boton(f"⬇  Actualización v{latest} disponible", lambda: self.ir("update"), kind="primary", tone="green")
        self.zona_der.insertWidget(0, self._upd_btn)
        self.status(f"Hay una versión nueva: v{latest}")
        self.toast(f"Hay una versión nueva: v{latest}. Pulsa el botón verde de arriba.", "green")

    def _auto_check(self):
        if DEMO or not updater.get_repo():
            return

        def done(info):
            if info["newer"]:
                self.pages["update"].recibe(info)
        self.bg(updater.check, done, lambda e: None)

    def _check_revoked(self):
        if DEMO:
            return
        antes = licencia.status()["level"]

        def trabajo():
            licencia.refresh_revoked()
            return licencia.status()

        def hecho(st):
            if antes == "pro" and st["level"] == "invalid":
                self.refresh_license()
                self.ir("license")
                self.info("Clave anulada", st["msg"] + "\n\nHellOP vuelve al modo gratis.")
            elif antes != st["level"]:
                self.refresh_license()
        self.bg(trabajo, hecho, lambda e: None)
        QTimer.singleShot(3 * 3600 * 1000, self._check_revoked)

    def _admin_prompt(self):
        if IS_WIN and not DEMO and not is_admin():
            if self.pregunta("Permisos de administrador", "Para optimizar a fondo (servicios, energía, restauración del sistema) necesito "
                                                           "permisos de administrador.\n\n¿Reabrir la app como administrador?"):
                self.restart_admin()

    def _asistente_primera_vez(self):
        try:
            import asistente
            if os.environ.get("HELLOP_ASISTENTE") == "1" or (not DEMO and not asistente.visto()):
                self.abrir_asistente()
        except Exception:  # noqa: BLE001
            pass

    def abrir_asistente(self):
        try:
            from .paginas.asistente import Asistente
            Asistente(self).exec()
        except Exception:  # noqa: BLE001
            self._registra_error()

    def _arranca_juegos(self):
        try:
            self.pages["games"].boot()
        except Exception:  # noqa: BLE001
            pass

    def _tick_live(self):
        try:
            c, r = psutil.cpu_percent(interval=None), psutil.virtual_memory().percent
            self.bar_cpu.pon(c, "red" if c > 90 else None)
            self.bar_ram.pon(r, "yellow" if r > 85 else None)
            self.lbl_cpu.setText(f"{c:.0f}%")
            self.lbl_ram.setText(f"{r:.0f}%")
        except Exception:  # noqa: BLE001
            pass

    # ---- modo claro / oscuro --------------------------------------------------------------------
    def cambia_modo(self):
        nuevo = "oscuro" if theme.MODO == "claro" else "claro"
        theme.pon_modo(nuevo)
        theme.guarda_modo(nuevo)
        QApplication.instance().setStyleSheet(theme.qss())
        actual = self.current
        for k in list(self.pages.keys()):
            p = self.pages.pop(k)
            self.stack.removeWidget(p)
            p.deleteLater()
        self._texto_modo()
        self.busca.setStyleSheet("text-align: left; font-weight: 400; color: %s;" % theme.C["muted"])
        self.refresh_license()
        self.ir(actual or "home", _hist=False)

    # ---- varios -----------------------------------------------------------------------------------
    def abrir_buscador(self):
        if not hasattr(self, "_buscador"):
            self._buscador = Buscador(self)
        self._buscador.abre()

    def exportar_informe(self):
        import informe
        self.toast("Preparando tu informe…")
        self.bg(lambda: informe.guardar(), lambda r: (self.toast("Informe guardado en tu Escritorio y abierto en el navegador", "green"), informe.abrir(r)),
                lambda e: self.toast(f"No pude crear el informe: {e}", "red"))

    def restart_admin(self):
        if relaunch_as_admin():
            QApplication.quit()
            sys.exit(0)
        self.aviso_modal("Administrador", "No se pudo reabrir como administrador.")

    def restart_now(self):
        if DEMO or not IS_WIN:
            self.status("Reinicio no disponible en este modo: cierra y abre HellOP.")
            return
        self._apaga_paginas()
        if relaunch_as_admin():
            QApplication.quit()
            sys.exit(0)
        self.status("No pude reiniciar solo: cierra y abre HellOP.")

    def _apaga_paginas(self):
        for p in list(self.pages.values()):
            f = getattr(p, "apaga", None)
            if f:
                try:
                    f()
                except Exception:  # noqa: BLE001
                    pass

    def closeEvent(self, e):
        self._guarda_geometria()
        try:
            import noche
            noche.restaurar()
            import movil
            movil.apagar()
        except Exception:  # noqa: BLE001
            pass
        self._apaga_paginas()
        e.accept()
        QApplication.quit()
