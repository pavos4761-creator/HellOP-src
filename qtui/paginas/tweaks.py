"""Tweaks: ajustes de rendimiento y latencia por nivel de riesgo, cada uno en su cuadrado."""
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QHBoxLayout, QVBoxLayout, QWidget

import actions
import tweaks
import tweaks_extra
from util import DEMO

from ..widgets import Boton, Casilla, Etiqueta, Pagina, Rejilla, Tarjeta, fila, vacia
from .optimizar import Cuadro

TONO = {"green": "green", "yellow": "yellow", "red": "red"}


class Tweaks(Pagina):
    titulo_texto = "Tweaks"
    sub_texto = "Latencia y rendimiento en tres niveles de riesgo: tú eliges y cada uno explica qué hace."

    def __init__(self, app):
        super().__init__(app)
        self.busy = False
        self.acts, self.cuadros = [], []
        self._cargado = False
        self._rest = False
        self.v_restore = Casilla("Crear un punto de restauración de Windows antes de aplicar (recomendado)", True)
        c = Tarjeta(tone="yellow", titulo="Cómo funciona")
        for t in ("No se marca nada solo. Marca los cuadrados que quieras y pulsa «Aplicar los marcados», o aplica uno solo con su botón.",
                  "Todo queda en el Historial: puedes deshacer cualquier tweak uno a uno o todos a la vez.",
                  "«Efecto real» significa que se mide en la mayoría de equipos; «casi nulo» se ofrece por completitud. "
                  "Sé realista: estos ajustes dan mejoras pequeñas; los saltos grandes vienen de los gráficos del juego y del calor.",
                  "Muchos piden reiniciar y administrador; te lo indico en cada uno. Solo aparecen los que aplican a TU equipo."):
            c.add(Etiqueta("•  " + t, "muted"))
        self.add(c)
        self.b_scan = Boton("↻  Buscar tweaks para mi PC", self.scan, kind="primary")
        self.msg = Etiqueta("", "muted", wrap=True)
        self.add(fila(self.b_scan, self.msg, None))
        self.cuerpo = QVBoxLayout()
        self.cuerpo.setSpacing(10)
        self.col.addLayout(self.cuerpo)
        self.pie_tw = QVBoxLayout()
        self.col.addLayout(self.pie_tw)
        m = Tarjeta(tone="muted", titulo="Tweaks famosos que NO incluyo (y por qué)")
        m.add(Etiqueta("Hay listas enormes de «tweaks de regedit» en vídeos y foros. Casi todos vienen de guías antiguas o se copian sin probar. "
                       "Según la documentación de Microsoft y pruebas públicas, estos no hacen lo que prometen, así que HellOP no te los ofrece:", "muted"))
        for name, why in tweaks_extra.MITOS:
            f = QHBoxLayout()
            f.addWidget(Etiqueta("✗", "h3", "red", wrap=False), 0, Qt.AlignmentFlag.AlignTop)
            f.addWidget(Etiqueta(f"{name}: {why}", "muted"), 1)
            m.lay.addLayout(f)
        self.col.addSpacing(10)
        self.add(m)

    def al_mostrar(self):
        if not self._cargado:
            self._cargado = True
            self.scan()

    # ------------------------------------------------------------------
    def scan(self):
        if self.busy:
            return
        self.busy = True
        self.b_scan.setEnabled(False)
        self.msg.setText("Revisando tu equipo (puede tardar unos segundos)…")
        self.msg.tono("accent")
        self.app.bg(lambda: tweaks.collect(lambda m: self.app.ui(self._say, m)), self._scanned, self._fail)

    def _say(self, texto):
        self.msg.setText(texto)
        self.msg.tono("accent")

    def _fail(self, e):
        self.busy = False
        self.b_scan.setEnabled(True)
        self.msg.setText(f"Error: {e}")
        self.msg.tono("red")

    def _scanned(self, acts):
        self.busy = False
        self.b_scan.setEnabled(True)
        self.acts = acts
        ya = f"  ·  otros {tweaks.SKIPPED} ya están aplicados o no aplican a tu equipo" if tweaks.SKIPPED else ""
        self.msg.setText((f"{len(acts)} tweaks disponibles en tu equipo" if acts else "No queda ningún tweak por aplicar. ¡Todo hecho!") + ya)
        self.msg.tono("green")
        self.dibuja()

    def dibuja(self):
        vacia(self.cuerpo)
        vacia(self.pie_tw)
        self.cuadros = []
        if not self.acts:
            return
        for risk, name, blurb, color in tweaks.LEVELS:
            items = [a for a in self.acts if a.risk == risk]
            if not items:
                continue
            tn = TONO.get(color, "accent")
            cab = QHBoxLayout()
            cab.addWidget(Etiqueta(name.upper(), "h3", tn, wrap=False))
            cab.addWidget(Etiqueta(str(len(items)), "small", wrap=False))
            cab.addWidget(Boton("marcar todos", lambda it=items: self._marca(it, True), kind="link"))
            cab.addStretch(1)
            w = QWidget()
            w.setLayout(cab)
            self.cuerpo.addWidget(w)
            self.cuerpo.addWidget(Etiqueta(blurb, "muted"))
            rej = Rejilla(3)
            for a in items:
                c = Cuadro(self, a)
                self.cuadros.append(c)
                rej.add(c)
            self.cuerpo.addWidget(rej)
        self.pie_tw.addWidget(self.v_restore)
        self.b_apply = Boton("Aplicar los marcados", lambda: self.aplicar([c for c in self.cuadros if c.sel()]), kind="primary", tone="teal")
        self.pie_tw.addWidget(self.b_apply, 0, Qt.AlignmentFlag.AlignLeft)
        self.actualiza_barra()

    def actualiza_barra(self):
        b = getattr(self, "b_apply", None)
        if b is None:
            return
        try:
            n = sum(1 for c in self.cuadros if c.sel())
            b.setText(f"Aplicar los marcados ({n})" if n else "Aplicar los marcados")
            b.setEnabled(n > 0 and not self.busy)
        except RuntimeError:
            pass

    def _marca(self, items, flag):
        ids = {id(a) for a in items}
        for c in self.cuadros:
            if id(c.a) in ids:
                c.poner_sel(flag)
        self.actualiza_barra()

    def aplicar(self, lista):
        lista = [c for c in lista if c.estado in ("idle", "bad")]
        if self.busy or not lista:
            return
        duros = [c for c in lista if c.a.risk == "alto"]
        if duros and not DEMO and not self.app.pregunta(
                "Ajustes de nivel EXTREMO", f"{len(duros)} cambian seguridad o el arranque. Si juegas con anti-cheat estricto, revísalos antes.\n"
                                            "Se pueden deshacer desde el Historial.\n\n¿Continuar?"):
            return
        self.busy = True
        self.b_scan.setEnabled(False)
        self.b_apply.setEnabled(False)
        restore = self.v_restore.isChecked() and not self._rest
        for c in lista:
            c.corriendo()

        def trabajo():
            if restore:
                self.app.ui(self._say, "Creando punto de restauración…")
                actions.create_restore_point()
                self._rest = True
            hechos = fallos = 0
            reinicio = False
            for i, c in enumerate(lista, 1):
                self.app.ui(self._say, f"Aplicando {i}/{len(lista)}: {c.a.title[:60]}")
                r = actions.execute(c.a)
                self.app.ui(c.fin, r)
                if r.ok:
                    hechos += 1
                    reinicio = reinicio or c.a.reboot
                else:
                    fallos += 1
            return hechos, fallos, reinicio

        self.app.bg(trabajo, self._aplicado, self._fail)

    def _aplicado(self, res):
        hechos, fallos, reinicio = res
        self.busy = False
        self.msg.setText(f"✓ {hechos} aplicados" + (f"  ·  {fallos} con error" if fallos else "") + ("  ·  reinicia el PC para completar" if reinicio else ""))
        self.msg.tono("green" if not fallos else "yellow")
        self.b_scan.setEnabled(True)
        self.actualiza_barra()
