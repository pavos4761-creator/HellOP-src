"""Pantalla «Mis juegos»: biblioteca, perfil por juego y modo juego automático (versión Qt)."""
import os
import subprocess

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import QDialog, QFileDialog, QHBoxLayout, QVBoxLayout

import games
import licencia
from util import DEMO

from ..widgets import Boton, Casilla, Etiqueta, Insignia, Pagina, Tarjeta, fila, vacia

SRC_TONE = {"Steam": "teal", "Epic": "accent", "Riot": "red", "Manual": "yellow"}


class Juegos(Pagina):
    titulo_texto = "Mis juegos"
    sub_texto = "Tu biblioteca y el modo automático: abres un juego y HellOP lo optimiza solo; lo cierras y deja todo como estaba."

    def __init__(self, app):
        super().__init__(app)
        self.watcher = None

        a = Tarjeta(tone="green", titulo="◉  Modo juego automático", margen=18)
        a.add(Etiqueta("Con esto activado, HellOP vigila tus juegos. Cuando abres uno de tu biblioteca activa el Modo Extremo con el perfil "
                       "de ESE juego (prioridad, procesos de fondo, plan de energía, temporizador…). Al cerrarlo lo devuelve todo a su sitio. "
                       "HellOP debe estar abierto (puede estar minimizado).", "muted"))
        self.auto_btn = Boton("▶   ACTIVAR MODO AUTOMÁTICO", self.toggle_auto, kind="primary", tone="green")
        self.auto_btn.setMinimumHeight(44)
        self.state = Etiqueta("Desactivado", "h3", "muted", wrap=False)
        a.add(fila(self.auto_btn, self.state, None, espacio=16))
        self.add(a)

        lib = Tarjeta(tone="teal", titulo="▣  Mi biblioteca")
        self.info = Etiqueta("", "small", "muted")
        lib.add(fila(Boton("↻  Buscar juegos (Steam, Epic)", self.scan, kind="primary"),
                     Boton("＋  Añadir un .exe", self.add_exe, kind="soft"), self.info, None, espacio=8))
        self.list = QVBoxLayout()
        self.list.setContentsMargins(0, 6, 0, 0)
        self.list.setSpacing(6)
        lib.lay.addLayout(self.list)
        self.add(lib)

        self.add(Etiqueta("Cada juego usa su propio perfil: pulsa «Perfil» para elegir qué se optimiza. Todo lo que cambia se restaura solo al cerrar el juego "
                          "(o al cerrar HellOP). No se toca nada del juego en sí: solo el sistema alrededor.", "muted"))
        self.render()

        self.timer = QTimer(self)
        self.timer.setInterval(1000)
        self.timer.timeout.connect(self._tick)
        self.timer.start()

    # ------------------------------------------------------------------
    def _info(self, texto, tone="muted"):
        self.info.setText(texto)
        self.info.tono(tone)

    def boot(self):
        """Al abrir la app: si el modo automático estaba activado, lo reanuda."""
        if games.load()["auto"] and not licencia.locked("games"):
            self._ensure_watcher().start()
            self._refresh_state()

    def _ensure_watcher(self):
        if self.watcher is None:
            bp = self.app.pages["booster"]
            self.watcher = games.Watcher(bp.b, log=lambda m: self.app.ui(bp._log, m), on_change=lambda: self.app.ui(self._changed))
        return self.watcher

    def _changed(self):
        self._refresh_state()
        bp = self.app.pages["booster"]
        bp.sync()

    def apaga(self):
        """Al cerrar la app."""
        self.timer.stop()
        if self.watcher:
            self.watcher.running = False
            if self.watcher.current:
                self.watcher.current = None

    shutdown = apaga

    # ------------------------------------------------------------------
    def toggle_auto(self):
        w = self._ensure_watcher()
        if w.running:
            games.set_auto(False)
            w.stop()
        else:
            if not games.load()["games"]:
                self._info("Primero busca o añade algún juego.", "yellow")
                return
            games.set_auto(True)
            w.start()
        self._refresh_state()

    def _refresh_state(self):
        w = self.watcher
        on = bool(w and w.running)
        self.auto_btn.set_text("■   DESACTIVAR MODO AUTOMÁTICO" if on else "▶   ACTIVAR MODO AUTOMÁTICO")
        self.auto_btn.estilo(tone="red" if on else "green")
        txt, secs = w.status() if w else ("Desactivado", None)
        if secs is not None:
            m, s = divmod(int(secs), 60)
            txt += f" · {m:02d}:{s:02d}"
        self.state.setText(txt)
        self.state.tono("green" if on else "muted")
        b = self.app.nav.get("games") if hasattr(self.app, "nav") else None
        if b is not None:
            b.punto = (("red" if (w and w.current) else "green") if on else None)
            b.update()
        if on:
            self.app.status(txt)

    def _tick(self):
        if self.watcher and self.watcher.running:
            self._refresh_state()

    # ------------------------------------------------------------------
    def scan(self):
        self._info("Buscando…", "teal")
        self.app.bg(games.scan_all, self._scanned, lambda e: self._info(f"Error: {e}", "red"))

    def _scanned(self, new):
        n = len(games.load()["games"])
        self._info((f"{new} juego(s) nuevo(s) · {n} en total" if n else
                    "No encontré juegos de Steam ni Epic. Puedes añadir un .exe a mano."), "green" if n else "yellow")
        self.render()

    def add_exe(self):
        p, _f = QFileDialog.getOpenFileName(self, "Elige el .exe del juego", "", "Programa (*.exe)")
        if p:
            self._info("Añadido." if games.add_manual(p) else "Ese juego ya estaba en la lista.", "green")
            self.render()

    def render(self):
        vacia(self.list)
        gl = games.load()["games"]
        if not gl:
            self.list.addWidget(Etiqueta("Aún no hay juegos. Pulsa «Buscar juegos» para detectar los de Steam y Epic, o añade un .exe.", "muted"))
            return
        for g in gl:
            card = Tarjeta(soft=True, margen=12, espacio=2)
            cab = fila(Etiqueta(g["name"], "h3", wrap=False), Insignia(g["source"], SRC_TONE.get(g["source"], "muted")), None, espacio=8)
            texto = Etiqueta(cab_perfil(g), "small", "muted")
            izq = card.lay
            izq.addWidget(cab)
            izq.addWidget(texto)
            botones = fila(Boton("▶ Jugar", lambda gg=g: self.play(gg), kind="primary", tone="green"),
                           Boton("Perfil", lambda gg=g: self.edit_profile(gg), kind="soft"),
                           Boton("Quitar", lambda gid=g["id"]: self.remove(gid), kind="ghost"), None, espacio=8)
            izq.addWidget(botones)
            self.list.addWidget(card)

    def remove(self, gid):
        games.remove(gid)
        self.render()

    def play(self, g):
        if not (self.watcher and self.watcher.running):
            games.set_auto(True)
            self._ensure_watcher().start()
            self._refresh_state()
        if DEMO or not g.get("launch"):
            self._info(f"(Demo) Abriría «{g['name']}» y se optimizaría solo.", "green")
            return
        try:
            if g["launch"].startswith(("steam:", "com.epicgames")):
                os.startfile(g["launch"])  # noqa: S606 (abre Steam/Epic con el juego)
            else:
                subprocess.Popen([g["launch"]], cwd=os.path.dirname(g["launch"]) or None)
            self._info(f"Abriendo «{g['name']}»… se optimizará solo en cuanto arranque.", "green")
        except (OSError, AttributeError) as e:
            self._info(f"No pude abrirlo: {e}", "red")

    # ------------------------------------------------------------------
    def edit_profile(self, g):
        dlg = QDialog(self.window())
        dlg.setWindowTitle(f"Perfil · {g['name']}")
        dlg.resize(640, 520)
        lay = QVBoxLayout(dlg)
        lay.setContentsMargins(20, 16, 20, 16)
        lay.setSpacing(8)
        lay.addWidget(Etiqueta(g["name"], "h2"))
        lay.addWidget(Etiqueta("Qué se optimiza cuando abres este juego:", "muted"))
        cajas = {}
        for k, text, _d in games.OPTIONS:
            cb = Casilla(text, bool(g["profile"].get(k)))
            cajas[k] = cb
            lay.addWidget(cb)
        lay.addStretch(1)

        def ok(everyone=False):
            games.set_profile(g["id"], {k: c.isChecked() for k, c in cajas.items()}, everyone)
            dlg.accept()
            self.render()

        btns = QHBoxLayout()
        btns.setSpacing(10)
        btns.addWidget(Boton("Guardar", lambda: ok(False), kind="primary", tone="green"))
        btns.addWidget(Boton("Guardar y copiar a todos los juegos", lambda: ok(True), kind="soft"))
        btns.addWidget(Boton("Cancelar", dlg.reject, kind="ghost"))
        btns.addStretch(1)
        lay.addLayout(btns)
        dlg.exec()


def cab_perfil(g):
    return "Perfil: " + games.summary(g["profile"])
