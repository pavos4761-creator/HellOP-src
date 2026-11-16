"""Pantalla «Limpiar shaders»: borra las cachés de shaders (DirectX, NVIDIA, AMD, Intel, Steam) para arreglar tirones raros."""
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QHBoxLayout, QVBoxLayout, QWidget

import shaders
from util import DEMO, fmt_bytes

from ..widgets import Pagina, Tarjeta, Etiqueta, Boton, Casilla, vacia


class Shaders(Pagina):
    titulo_texto = "Limpiar shaders"
    sub_texto = "Arregla tirones, parpadeos o artefactos tras actualizar el driver o un juego."

    def __init__(self, app):
        super().__init__(app)
        self.busy = False
        self.items = []
        self.vars = {}          # id -> Casilla
        self._loaded = False

        c = Tarjeta(tone="yellow", titulo="Cuándo sirve (y cuándo no)")
        self.add(c)
        for t in ("Los shaders son «trozos» de gráficos que tu PC guarda ya preparados. A veces se corrompen o quedan viejos y dan "
                  "tirones raros, parpadeos o texturas rotas, sobre todo tras actualizar el driver de la gráfica o el juego.",
                  "Honestidad: limpiar esto NO sube los FPS. Solo arregla fallos. Si tu juego va bien, déjalo como está.",
                  "La primera partida después irá algo peor (tirones mientras se vuelven a crear) y luego vuelve a la normalidad.",
                  "Se borra solo el contenido de esas carpetas de caché. Cierra los juegos antes. No se puede deshacer, "
                  "pero tampoco hace falta: se regeneran solas."):
            c.add(Etiqueta("•  " + t, "small", "muted"))

        barra = QWidget()
        hb = QHBoxLayout(barra)
        hb.setContentsMargins(0, 0, 0, 0)
        hb.setSpacing(14)
        self.b_scan = Boton("↻  BUSCAR CACHÉS", self.scan, kind="primary")
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
        self._msg("Midiendo las cachés…", "teal")
        self.app.bg(shaders.scan, self._scanned, self._fail)

    def _fail(self, e):
        self.busy = False
        self.b_scan.set_enabled(True)
        self._msg(f"Error: {e}", "red")

    def _scanned(self, items):
        self.busy = False
        self.b_scan.set_enabled(True)
        self.items = items
        total = sum(i["size"] for i in items)
        self._msg(f"{len(items)} cachés · {fmt_bytes(total)} en total" if items else "No he encontrado cachés de shaders.", "green")
        self.render()

    def render(self):
        vacia(self.body_lay)
        self.vars = {}
        if not self.items:
            return
        c = Tarjeta(tone="accent", titulo="Cachés encontradas")
        self.body_lay.addWidget(c)
        for it in self.items:
            cb = Casilla(f"{it['label']}   ({fmt_bytes(it['size'])})", False)
            self.vars[it["id"]] = cb
            c.add(cb)
            desc = Etiqueta(it["desc"], "small", "muted")
            f = QWidget()
            h = QHBoxLayout(f)
            h.setContentsMargins(28, 0, 0, 6)
            h.addWidget(desc, 1)
            c.add(f)
        fb = QWidget()
        hb = QHBoxLayout(fb)
        hb.setContentsMargins(0, 0, 0, 0)
        hb.addWidget(Boton("✖  LIMPIAR LAS MARCADAS", self.clean, kind="primary", tone="red"))
        hb.addStretch(1)
        self.body_lay.addWidget(fb)

    def clean(self):
        if self.busy:
            return
        chosen = [i for i in self.items if self.vars.get(i["id"]) is not None and self.vars[i["id"]].isChecked()]
        if not chosen:
            self._msg("Marca primero alguna caché.", "yellow")
            return
        if not DEMO and not self.app.pregunta(
                "Limpiar shaders", "Se borrará el contenido de:\n\n" + "\n".join("· " + i["label"] for i in chosen)
                + "\n\nCierra antes tus juegos. La primera partida irá algo peor mientras se regeneran.\n¿Continuar?"):
            return
        self.busy = True
        self._msg("Limpiando…", "teal")

        def done(res):
            self.busy = False
            freed, errs = res
            self._msg(f"✓ Liberados {fmt_bytes(freed)}" if not errs else "✗ " + " · ".join(errs), "green" if not errs else "red")
            if not DEMO:
                self.scan()
        self.app.bg(lambda: shaders.clean(chosen), done, self._fail)
