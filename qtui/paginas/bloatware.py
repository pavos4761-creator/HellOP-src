"""Pantalla «Quitar bloatware»: apps de Windows y programas de fabricante que sobran."""
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QHBoxLayout, QVBoxLayout, QWidget

import actions
import debloat
from util import DEMO

from ..widgets import Pagina, Tarjeta, Etiqueta, Boton, Casilla, Insignia, vacia


class Bloatware(Pagina):
    titulo_texto = "Quitar bloatware"
    sub_texto = "Apps preinstaladas y programas de fabricante que gastan RAM y procesador sin que los uses."

    def __init__(self, app):
        super().__init__(app)
        self.busy = False
        self.appx, self.win32 = [], []
        self.vars = {}          # nombre de app -> Casilla
        self._loaded = False

        c = Tarjeta(tone="yellow", titulo="Antes de empezar")
        self.add(c)
        for t in ("No se marca nada solo: tú eliges. Las apps de Windows se pueden volver a instalar desde la Microsoft Store.",
                  "Los programas se desinstalan con su propio desinstalador: verás sus pantallas y tendrás que confirmar.",
                  "No se muestran componentes de Windows, drivers ni lanzadores de juegos para que no rompas nada.",
                  "Honestidad: quitar esto libera espacio y algo de RAM, pero no sube los FPS de forma notable. Lo que más "
                  "pesa es un antivirus de prueba (McAfee, Norton) o un asistente del fabricante que corre siempre."):
            c.add(Etiqueta("•  " + t, "small", "muted"))

        barra = QWidget()
        hb = QHBoxLayout(barra)
        hb.setContentsMargins(0, 0, 0, 0)
        hb.setSpacing(14)
        self.b_scan = Boton("↻  BUSCAR MIS APPS", self.scan, kind="primary")
        self.msg = Etiqueta("", "muted")
        hb.addWidget(self.b_scan, 0)
        hb.addWidget(self.msg, 1)
        self.add(barra)

        self.body = QWidget()
        self.body_lay = QVBoxLayout(self.body)
        self.body_lay.setContentsMargins(0, 0, 0, 0)
        self.body_lay.setSpacing(12)
        self.add(self.body)

    def al_mostrar(self):
        if not self._loaded:
            self._loaded = True
            self.scan()

    def _msg(self, texto, tone="muted"):
        self.msg.setText(texto)
        self.msg.tono(tone)

    # ------------------------------------------------------------------
    def scan(self):
        if self.busy:
            return
        self.busy = True
        self.b_scan.set_enabled(False)
        self._msg("Buscando (puede tardar unos segundos)…", "teal")
        self.app.bg(debloat.scan, self._scanned, self._scan_fail)

    def _scan_fail(self, e):
        self.busy = False
        self.b_scan.set_enabled(True)
        self._msg(f"Error: {e}", "red")

    def _scanned(self, res):
        self.busy = False
        self.b_scan.set_enabled(True)
        self.appx, self.win32 = res
        self._msg(f"{len(self.appx)} apps de Windows y {len(self.win32)} programas", "green")
        self.render()

    def render(self):
        vacia(self.body_lay)
        self.vars = {}
        # ---- apps de Windows
        c = Tarjeta(tone="accent", titulo="Apps de Windows")
        self.body_lay.addWidget(c)
        if not self.appx:
            c.add(Etiqueta("No he encontrado apps que sobren.", None, "green"))
        else:
            row = QWidget()
            h = QHBoxLayout(row)
            h.setContentsMargins(0, 0, 0, 6)
            h.setSpacing(8)
            h.addWidget(Boton("Marcar las recomendadas", self.mark_rec, kind="soft"))
            h.addWidget(Boton("Desmarcar todo", self.unmark, kind="ghost"))
            h.addStretch(1)
            self.b_remove = Boton("✖  QUITAR LAS MARCADAS", self.remove_marked, kind="primary", tone="red")
            h.addWidget(self.b_remove)
            c.add(row)
            for a in self.appx[:80]:
                cb = Casilla(a["title"], False)
                self.vars[a["name"]] = cb
                line = QWidget()
                hl = QHBoxLayout(line)
                hl.setContentsMargins(0, 1, 0, 1)
                hl.setSpacing(8)
                hl.addWidget(cb, 0)
                if a["rec"]:
                    hl.addWidget(Insignia("recomendada", "green"))
                if a["why"]:
                    hl.addWidget(Etiqueta(a["why"], "small", "muted"), 1)
                else:
                    hl.addStretch(1)
                c.add(line)
        # ---- programas
        p = Tarjeta(tone="teal", titulo="Programas instalados")
        self.body_lay.addWidget(p)
        if not self.win32:
            p.add(Etiqueta("No he encontrado programas que sobren.", None, "green"))
        for a in self.win32[:60]:
            r = QWidget()
            h = QHBoxLayout(r)
            h.setContentsMargins(0, 3, 0, 3)
            h.setSpacing(12)
            tx = QVBoxLayout()
            tx.setSpacing(2)
            head = QHBoxLayout()
            head.setSpacing(8)
            head.addWidget(Etiqueta(a["name"], "h3", wrap=False))
            if a["rec"]:
                head.addWidget(Insignia("recomendado quitar", "green"))
            head.addStretch(1)
            tx.addLayout(head)
            info = a["publisher"] or ""
            if a["size"]:
                info += ("  ·  " if info else "") + (f"{a['size']:.0f} MB" if a["size"] < 1024 else f"{a['size'] / 1024:.1f} GB")
            tx.addWidget(Etiqueta(info, "small", "muted"))
            h.addLayout(tx, 1)
            h.addWidget(Boton("Desinstalar", lambda n=a["name"]: self.uninstall(n), kind="soft",
                              tone="red" if a["rec"] else None), 0, Qt.AlignmentFlag.AlignTop)
            p.add(r)

    def mark_rec(self):
        for a in self.appx:
            cb = self.vars.get(a["name"])
            if cb is not None:
                cb.setChecked(bool(a["rec"]))

    def unmark(self):
        for cb in self.vars.values():
            cb.setChecked(False)

    # ------------------------------------------------------------------
    def remove_marked(self):
        chosen = [a for a in self.appx if self.vars.get(a["name"]) is not None and self.vars[a["name"]].isChecked()]
        if not chosen:
            self._msg("Marca primero alguna app.", "yellow")
            return
        if self.busy:
            return
        if not DEMO and not self.app.pregunta(
                "Quitar apps", f"Se van a quitar {len(chosen)} apps de Windows:\n\n" + "\n".join("· " + a["title"] for a in chosen[:12])
                + ("\n…" if len(chosen) > 12 else "") + "\n\nPodrás volver a instalarlas desde la Microsoft Store.\n¿Continuar?"):
            return
        self.busy = True
        self.b_scan.set_enabled(False)
        self._msg(f"Quitando {len(chosen)} apps…", "teal")

        def work():
            ok = fail = 0
            for a in chosen:
                r = actions.execute(debloat.AppxRemoveAction(a["name"], a["title"]))
                ok += r.ok
                fail += (not r.ok)
            return ok, fail

        self.app.bg(work, self._removed, self._scan_fail)

    def _removed(self, res):
        ok, fail = res
        self.busy = False
        self._msg(f"✓ {ok} quitadas" + (f"  ·  {fail} no se pudieron quitar" if fail else ""), "green" if not fail else "yellow")
        if DEMO:
            self.b_scan.set_enabled(True)
            return
        self.scan()

    def uninstall(self, name):
        if self.busy:
            return
        if not DEMO and not self.app.pregunta("Desinstalar", f"Se abrirá el desinstalador de:\n\n{name}\n\n¿Continuar?"):
            return
        self.app.bg(lambda: actions.execute(debloat.Win32UninstallAction(name)),
                    lambda r: self._msg(("✓ " if r.ok else "✗ ") + r.msg, "green" if r.ok else "red"),
                    lambda e: self._msg(f"✗ {e}", "red"))
