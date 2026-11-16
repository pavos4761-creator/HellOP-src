"""Pantalla «Modo Extremo»: optimización EN VIVO mientras juegas (versión Qt)."""
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QFontDatabase
from PySide6.QtWidgets import QAbstractItemView, QListWidget, QPlainTextEdit

import booster
from util import DEMO, fmt_bytes, is_admin

from ..widgets import Boton, Casilla, Etiqueta, Pagina, Rejilla, Tarjeta, fila

OPTIONS = [
    ("timer", "Temporizador de Windows a 0,5 ms (la latencia del planificador baja de 15,6 ms a 0,5 ms)", True),
    ("game_prio", "Prioridad ALTA para tu juego", True),
    ("bg_prio", "Prioridad baja para todo lo de fondo (navegador, launchers, etc.)", True),
    ("bg_ram", "Liberar la RAM que usan los programas de fondo", True),
    ("services", "Pausar servicios que despiertan al disco y la CPU (SysMain, búsqueda, Windows Update…) · necesita administrador", True),
    ("standby", "Vaciar la memoria en caché cuando te quedas sin RAM libre (quita tirones en PC de 16 GB o menos) · necesita administrador", True),
    ("dns", "Vaciar la caché DNS", False),
    ("power", "Plan de energía de Alto rendimiento mientras juegas (se restaura al terminar)", True),
    ("affinity", "Dejar los núcleos 0 y 1 libres para Windows (solo CPU de 6 núcleos o más; prueba si te va mejor)", False),
]

TXT_ACTIVAR = "☢   ACTIVAR MODO EXTREMO"
TXT_DESACTIVAR = "■   DESACTIVAR Y DEJARLO TODO COMO ESTABA"


class Extremo(Pagina):
    titulo_texto = "Modo Extremo"
    sub_texto = "Optimiza TU PC mientras juegas y lo deja todo como estaba al terminar. Mantén esta app abierta."

    def __init__(self, app):
        super().__init__(app)
        self.b = booster.Booster()
        self.games = []
        self.busy = False
        self.cajas = {}
        self.tiles = {}
        self._construye()
        self.refresh_games()
        self.timer = QTimer(self)
        self.timer.setInterval(1000)
        self.timer.timeout.connect(self._loop)
        self.timer.start()

    # ------------------------------------------------------------------
    def _construye(self):
        c1 = Tarjeta(tone="teal", titulo="1 · Elige tu juego")
        c1.add(Etiqueta("Abre tu juego primero y pulsa «Actualizar». Si no aparece, escríbeme su nombre de proceso en el Administrador de tareas.",
                        "muted"))
        self.lb = QListWidget()
        self.lb.setFont(QFontDatabase.systemFont(QFontDatabase.SystemFont.FixedFont))
        self.lb.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.lb.setFixedHeight(170)
        c1.add(self.lb)
        self.no_game = Casilla("Sin juego concreto (solo limpiar el fondo)")
        c1.add(fila(Boton("↻  Actualizar lista", self.refresh_games, kind="soft"), self.no_game, None, espacio=14))
        self.add(c1)

        c2 = Tarjeta(tone="accent", titulo="2 · Qué quieres que haga")
        for k, texto, d in OPTIONS:
            cb = Casilla(texto, d)
            self.cajas[k] = cb
            c2.add(cb)
        self.add(c2)

        c3 = Tarjeta(tone="red", titulo="3 · Activar", margen=18)
        self.btn = Boton(TXT_ACTIVAR, self.toggle, kind="primary")
        self.btn.setMinimumHeight(48)
        c3.add(fila(self.btn, None))
        if not is_admin() and not DEMO:
            c3.add(Etiqueta("Sin administrador no se pueden pausar servicios ni cambiar la prioridad de algunos procesos.", "small", "yellow"))

        grid = Rejilla(3, 10)
        specs = [("timer", "TEMPORIZADOR", "teal"), ("game", "PRIORIDAD DEL JUEGO", "red"), ("low", "FONDO FRENADO", "accent"),
                 ("ram", "RAM LIBERADA", "green"), ("svc", "SERVICIOS EN PAUSA", "yellow"), ("time", "TIEMPO ACTIVO", "muted")]
        for key, label, tone in specs:
            t = Tarjeta(soft=True, margen=12, espacio=2)
            t.add(Etiqueta(label, "small", "muted"))
            v = Etiqueta("—", "h2", tone)
            t.add(v)
            self.tiles[key] = v
            grid.add(t)
        c3.add(grid)

        self.log = QPlainTextEdit()
        self.log.setReadOnly(True)
        self.log.setFont(QFontDatabase.systemFont(QFontDatabase.SystemFont.FixedFont))
        self.log.setFixedHeight(150)
        c3.add(self.log)
        self._log("Listo. Elige tu juego y pulsa ACTIVAR.")
        self.add(c3)

        self.add(Etiqueta("Honestidad: esto no crea FPS de la nada. Reduce latencia y tirones quitando lo que compite con tu juego. "
                          "En un PC ya ligero la mejora es pequeña; en uno con muchas cosas abiertas se nota más. "
                          "Al desactivar (o cerrar la app) todo vuelve a su estado normal.", "muted"))

    # ------------------------------------------------------------------
    def _log(self, msg):
        self.log.appendPlainText(str(msg))
        sb = self.log.verticalScrollBar()
        sb.setValue(sb.maximum())

    def refresh_games(self):
        self.games = booster.candidate_games()
        self.lb.clear()
        for name, rss, pid in self.games:
            self.lb.addItem(f"{name:<44} {fmt_bytes(rss):>9}   pid {pid}")
        if self.games:
            self.lb.setCurrentRow(0)

    def _boton_activo(self, on):
        if on:
            self.btn.set_text(TXT_DESACTIVAR)
            self.btn.estilo(tone="green")
        else:
            self.btn.set_text(TXT_ACTIVAR)
            self.btn.estilo(tone="")

    def toggle(self):
        if self.busy:
            return
        if self.b.active:
            self.deactivate()
        else:
            self.activate()

    def activate(self):
        game = None
        if not self.no_game.isChecked():
            fila_sel = self.lb.currentRow()
            if fila_sel < 0 or fila_sel >= len(self.games):
                self._log("⚠ Elige un juego de la lista (o marca «Sin juego concreto»).")
                return
            game = self.games[fila_sel][0]
        opts = {k: cb.isChecked() for k, cb in self.cajas.items()}
        self.busy = True
        self.btn.set_enabled(False)
        self._log("Activando… (mido el fondo, puede tardar un segundo)")
        self.app.bg(lambda: self.b.start(game, opts, lambda m: self.app.ui(self._log, m)), self._activated, self._failed)

    def _activated(self, _r=None):
        self.busy = False
        self.btn.set_enabled(True)
        self._boton_activo(True)
        self.app.status("Modo Extremo ACTIVO")

    def _failed(self, e):
        self.busy = False
        self.btn.set_enabled(True)
        self._log(f"✗ Error: {type(e).__name__}: {e}")

    def deactivate(self):
        self.busy = True
        self.btn.set_enabled(False)
        self.app.bg(lambda: self.b.stop(lambda m: self.app.ui(self._log, m)), self._deactivated, self._failed)

    def _deactivated(self, _r=None):
        self.busy = False
        self.btn.set_enabled(True)
        self._boton_activo(False)
        for t in self.tiles.values():
            t.setText("—")
        self.app.status("Modo Extremo desactivado")

    # ------------------------------------------------------------------
    def sync(self):
        """El modo automático puede activar o desactivar el Modo Extremo: ajusta el botón."""
        if self.busy:
            return
        if self.b.active:
            self._boton_activo(True)
        else:
            self._boton_activo(False)
            for t in self.tiles.values():
                t.setText("—")

    def _loop(self):
        if not self.b.active:
            return
        self.b.tick(self._log)
        s = self.b.stats()
        self.tiles["timer"].setText(f"{s['timer']:.2f} ms" if s["timer"] else "—")
        self.tiles["game"].setText(str(s["game_prio"]))
        self.tiles["low"].setText(f"{s['lowered']} procesos")
        self.tiles["ram"].setText(fmt_bytes(s["freed"]))
        self.tiles["svc"].setText(str(s["services"]))
        m, sec = divmod(int(s["elapsed"]), 60)
        self.tiles["time"].setText(f"{m:02d}:{sec:02d}")

    def apaga(self):
        """Se llama al cerrar la app: deja todo como estaba."""
        self.timer.stop()
        if self.b.active:
            self.b.stop()

    shutdown = apaga
