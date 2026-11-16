"""Pantalla «Gestor de arranque»: qué abre Windows al encender, con su impacto, para desactivarlo o reactivarlo."""
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QHBoxLayout, QVBoxLayout, QWidget

import arranque

from ..widgets import Pagina, Tarjeta, Etiqueta, Boton, Insignia, vacia

IMPACT_TONE = {"alto": "red", "medio": "yellow", "bajo": "green"}


class Arranque(Pagina):
    titulo_texto = "Gestor de arranque"
    sub_texto = "Qué se abre solo al encender Windows y cuánto lo retrasa. Desactivas y reactivas cuando quieras."

    def __init__(self, app):
        super().__init__(app)
        self.busy = False
        self.items, self.boot = [], None
        self._loaded = False

        c = Tarjeta(tone="yellow", titulo="Antes de empezar")
        self.add(c)
        for t in ("Desactivar NO desinstala nada: el programa sigue en tu PC y se abrirá cuando tú lo lances.",
                  "Todo queda en el Historial y se puede deshacer. Los componentes de seguridad salen marcados como protegidos.",
                  "Honestidad: en un SSD moderno el arranque ya es rápido y ganarás pocos segundos. Se nota más con disco duro, "
                  "con muchos programas activos o con RAM justa. No sube los FPS en el juego."):
            c.add(Etiqueta("•  " + t, "small", "muted"))

        barra = QWidget()
        hb = QHBoxLayout(barra)
        hb.setContentsMargins(0, 0, 0, 0)
        hb.setSpacing(14)
        self.b_scan = Boton("↻  REVISAR MI ARRANQUE", self.scan, kind="primary")
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
        self._msg("Leyendo el arranque de Windows (unos segundos)…", "teal")
        self.app.bg(arranque.entries, self._scanned, self._fail)

    def _fail(self, e):
        self.busy = False
        self.b_scan.set_enabled(True)
        self._msg(f"Error: {e}", "red")

    def _scanned(self, res):
        self.busy = False
        self.b_scan.set_enabled(True)
        self.items, self.boot = res
        self.render()

    def render(self):
        vacia(self.body_lay)
        on = [i for i in self.items if i["enabled"]]
        off = [i for i in self.items if not i["enabled"]]
        alto = sum(1 for i in on if i["impact"] == "alto" and not i["protected"])
        resumen = f"{len(on)} activos · {len(off)} desactivados"
        if self.boot:
            resumen = f"Último arranque: {self.boot:.0f} s  ·  " + resumen
        self._msg(resumen, "green")
        if alto:
            self.body_lay.addWidget(Etiqueta(f"Hay {alto} programa(s) de impacto ALTO que puedes desactivar para arrancar antes.",
                                             "h3", "yellow"))
        for titulo, grupo, tone in (("Se abren al iniciar", on, "accent"), ("Desactivados", off, "muted")):
            c = Tarjeta(tone=tone, titulo=titulo)
            self.body_lay.addWidget(c)
            if not grupo:
                c.add(Etiqueta("Nada por aquí.", None, "muted"))
            for it in grupo:
                self._row(c, it)

    def _row(self, card, it):
        r = QWidget()
        h = QHBoxLayout(r)
        h.setContentsMargins(0, 4, 0, 4)
        h.setSpacing(12)
        tx = QVBoxLayout()
        tx.setSpacing(2)
        head = QHBoxLayout()
        head.setSpacing(8)
        head.addWidget(Etiqueta(it["name"], "h3", wrap=False))
        if it["enabled"]:
            head.addWidget(Insignia(f"impacto {it['impact']} ({it['how']})", IMPACT_TONE.get(it["impact"], "muted")))
        if it["protected"]:
            head.addWidget(Insignia("protegido", "muted"))
        head.addStretch(1)
        tx.addLayout(head)
        tx.addWidget(Etiqueta(it["desc"], "small", "muted"))
        cmd = it["command"].strip()
        tx.addWidget(Etiqueta(cmd if len(cmd) <= 95 else cmd[:92] + "…", "mono", "muted", wrap=False))
        h.addLayout(tx, 1)
        if not it["protected"]:
            if it["enabled"]:
                b = Boton("Desactivar", lambda i=it: self.toggle(i, False), kind="soft",
                          tone="red" if it["impact"] == "alto" else None)
            else:
                b = Boton("Activar", lambda i=it: self.toggle(i, True), kind="soft", tone="green")
            h.addWidget(b, 0, Qt.AlignmentFlag.AlignTop)
        card.add(r)

    def toggle(self, it, on):
        if self.busy:
            return
        self.busy = True
        self._msg("Aplicando…", "teal")
        fn = arranque.enable if on else arranque.disable

        def done(res):
            self.busy = False
            if res.ok:
                it["enabled"] = on
                self.render()
                self._msg("✓ " + res.msg + f" · «{it['name']}» " + ("activado" if on else "desactivado"), "green")
            else:
                self._msg("✗ " + res.msg, "red")
        self.app.bg(lambda: fn(it), done, self._fail)
