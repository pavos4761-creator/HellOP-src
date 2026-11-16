"""Pantalla «Historial / Deshacer»: todo lo que la app ha cambiado, con botón para volver atrás (versión Qt)."""
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QHBoxLayout, QVBoxLayout, QWidget

import actions

from ..widgets import Boton, Etiqueta, Insignia, Pagina, Tarjeta, fila, vacia


class Historial(Pagina):
    titulo_texto = "Historial / Deshacer"
    sub_texto = "Todo lo que la app ha cambiado. Puedes volver atrás cambio por cambio."

    LOTE = 25          # cuántos cambios se dibujan de una vez (dibujar cientos de tarjetas hacía lag)

    def __init__(self, app):
        super().__init__(app)
        self.limite = self.LOTE
        self.b_all = Boton("↺  Deshacer todo lo reversible", self.undo_all, kind="soft", tone="yellow")
        self.add(fila(self.b_all, None))
        self.lista = QWidget()
        self.lista_lay = QVBoxLayout(self.lista)
        self.lista_lay.setContentsMargins(0, 0, 0, 0)
        self.lista_lay.setSpacing(8)
        self.add(self.lista)

    def al_mostrar(self):
        self.render(reset=True)

    def render(self, reset=True):
        if reset:
            self.limite = self.LOTE
        vacia(self.lista_lay)
        entries = list(reversed(actions.load_log()))
        pending = [e for e in entries if e["reversible"] and not e["undone"]]
        self.b_all.set_enabled(bool(pending))
        if not entries:
            c = Tarjeta(tone="teal")
            c.add(Etiqueta("Todavía no has cambiado nada. Cuando apliques optimizaciones aparecerán aquí."))
            self.lista_lay.addWidget(c)
            return
        for e in entries[:self.limite]:
            c = Tarjeta(tone="muted" if e["undone"] else "green", margen=12)
            h = QHBoxLayout()
            h.setSpacing(12)
            t = QVBoxLayout()
            t.setSpacing(2)
            t.addWidget(Etiqueta(e["title"], "h3", "muted" if e["undone"] else None))
            t.addWidget(Etiqueta(str(e["ts"]), "small"))
            h.addLayout(t, 1)
            if e["undone"]:
                h.addWidget(Insignia("DESHECHO", "muted"), 0, Qt.AlignmentFlag.AlignVCenter)
            elif e["reversible"]:
                h.addWidget(Boton("Deshacer", lambda i=e["id"]: self.undo(i), kind="soft", tone="yellow"), 0, Qt.AlignmentFlag.AlignVCenter)
            else:
                h.addWidget(Insignia("NO REVERSIBLE", "red"), 0, Qt.AlignmentFlag.AlignVCenter)
            c.lay.addLayout(h)
            self.lista_lay.addWidget(c)
        if len(entries) > self.limite:
            resto = len(entries) - self.limite
            b = Boton(f"Ver {min(self.LOTE, resto)} más ({resto} sin mostrar)", self.mas, kind="soft")
            self.lista_lay.addWidget(fila(None, b, None, margenes=(0, 4, 0, 12)))

    def mas(self):
        self.limite += self.LOTE
        self.render(reset=False)

    def undo(self, entry_id):
        res = actions.undo_entry(entry_id)
        self.app.status(res.msg)
        if not res.ok:
            self.app.aviso_modal("Deshacer", res.msg)
        self.render(reset=False)

    def undo_all(self):
        if not self.app.pregunta("Deshacer todo", "Se revertirán todos los cambios reversibles pendientes.\n¿Continuar?"):
            return
        done, fail = actions.undo_all()
        self.app.status(f"Deshechos {done} cambios" + (f" · {fail} con error" if fail else ""))
        self.render(reset=False)
