"""Asistente de primera vez (5 pasos). Nada se aplica sin que la persona lo marque; todo queda en el Historial."""
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QDialog, QFrame, QHBoxLayout, QScrollArea, QVBoxLayout, QWidget

import actions
import cleanup
import hidden
import licencia
import sysinfo
import tweaks
import json
from util import APP_DIR, DEMO, fmt_bytes, is_admin

from ..widgets import Boton, Casilla, Etiqueta, Tarjeta, fila, vacia

FLAG = APP_DIR / "asistente.json"


def visto():
    try:
        return bool(json.loads(FLAG.read_text("utf-8")).get("hecho"))
    except Exception:  # noqa: BLE001
        return False


def marcar_visto():
    try:
        APP_DIR.mkdir(parents=True, exist_ok=True)
        FLAG.write_text(json.dumps({"hecho": True}), "utf-8")
    except OSError:
        pass


PASOS = ["Bienvenida", "Tu PC", "Lo importante", "Lo seguro", "Listo"]
SEV_TONO = {"bad": "red", "warn": "yellow", "info": "accent"}
SEV_TXT = {"bad": "PROBLEMA", "warn": "MEJORABLE", "info": "A REVISAR"}


class Asistente(QDialog):
    def __init__(self, app):
        super().__init__(app)
        self.app = app
        self.setWindowTitle("Asistente de HellOP")
        self.setModal(True)
        self.resize(900, 680)
        self.setStyleSheet("")
        self.i = 0
        self.pro = licencia.is_pro()
        self.hw = self.hallazgos = self.limpieza = self.ajustes = None
        self.hecho = {"liberado": 0, "ajustes": 0}
        self.vars = {}
        self.destino = None
        self.cerrado = False
        v = QVBoxLayout(self)
        v.setContentsMargins(36, 24, 36, 24)
        top = QHBoxLayout()
        self.paso_txt = Etiqueta("", "small", wrap=False)
        top.addWidget(self.paso_txt)
        top.addStretch(1)
        top.addWidget(Boton("Saltar el asistente", lambda: self.cerrar(None), kind="ghost"))
        v.addLayout(top)
        self.titulo = Etiqueta("", "title")
        self.sub = Etiqueta("", "muted")
        v.addWidget(self.titulo)
        v.addWidget(self.sub)
        self.sc = QScrollArea()
        self.sc.setWidgetResizable(True)
        self.sc.setFrameShape(QFrame.Shape.NoFrame)
        self.host = QWidget()
        self.host.setObjectName("pagina")
        self.body = QVBoxLayout(self.host)
        self.body.setContentsMargins(0, 8, 8, 8)
        self.body.setSpacing(10)
        self.body.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.sc.setWidget(self.host)
        v.addWidget(self.sc, 1)
        pie = QHBoxLayout()
        self.b_back = Boton("←  Atrás", self.atras, kind="ghost")
        self.msg = Etiqueta("", "muted", wrap=False)
        self.b_next = Boton("Siguiente  →", self.siguiente, kind="primary")
        pie.addWidget(self.b_back)
        pie.addWidget(self.msg, 1)
        pie.addWidget(self.b_next)
        v.addLayout(pie)
        self.mostrar()

    # ------------------------------------------------------------------
    def vivo(self):
        return not self.cerrado

    def mostrar(self):
        vacia(self.body)
        self.msg.setText("")
        self.paso_txt.setText(f"Paso {self.i + 1} de {len(PASOS)}  ·  {PASOS[self.i]}")
        self.b_back.setEnabled(self.i > 0)
        self.b_next.setEnabled(True)
        self.b_next.setText("Empezar a usar HellOP" if self.i == len(PASOS) - 1 else "Siguiente  →")
        [self._p1, self._p2, self._p3, self._p4, self._p5][self.i]()

    def siguiente(self):
        if self.i >= len(PASOS) - 1:
            self.cerrar(None)
            return
        self.i += 1
        self.mostrar()

    def atras(self):
        if self.i > 0:
            self.i -= 1
            self.mostrar()

    def cerrar(self, ir_a):
        if self.cerrado:
            return
        self.cerrado = True
        marcar_visto()
        self.destino = ir_a
        self.accept()
        if ir_a:
            self.app.ir(ir_a)

    def done(self, r):
        self.cerrado = True
        super().done(r)

    def _cab(self, titulo, sub):
        self.titulo.setText(titulo)
        self.sub.setText(sub)

    def _cargando(self, texto):
        lb = Etiqueta(texto, tone="accent")
        self.body.addWidget(lb)
        return lb

    # ---- 1 · Bienvenida ----
    def _p1(self):
        self._cab("Bienvenido a HellOP", "En 2 minutos miramos tu PC y dejamos lo más importante bien puesto. Tú decides cada cosa.")
        c = Tarjeta(tone="accent", titulo="Antes de empezar, las reglas")
        for t in ("No se aplica nada sin que lo marques tú. Si no estás seguro de algo, se queda como está.",
                  "Todo lo que se cambie queda guardado en el Historial y se puede deshacer con un clic.",
                  "Te cuento la verdad: no hay ajuste mágico que doble tus FPS. Lo que más pesa es el monitor, la RAM, el calor y los gráficos del juego. "
                  "HellOP te ayuda a encontrar lo que de verdad te cuesta.",
                  "Puedes saltar el asistente cuando quieras. Lo vuelves a abrir desde Inicio."):
            c.add(Etiqueta("•  " + t, "muted"))
        self.body.addWidget(c)
        st = licencia.status()
        if self.pro:
            self.body.addWidget(Etiqueta("✓  Tienes PRO: puedes usar todas las funciones.", "h3", "green"))
        else:
            self.body.addWidget(Etiqueta("ⓘ  Estás en la versión GRATIS (análisis, limpieza, monitor, historial). Con una clave PRO se desbloquea el resto.", "h3", "yellow"))
        if st["level"] in ("expired", "invalid"):
            self.body.addWidget(Etiqueta(st["msg"], tone="red"))

    # ---- 2 · Tu PC ----
    def _p2(self):
        self._cab("Tu PC", "Esto es lo que he encontrado en tu equipo.")
        if self.hw is not None:
            self._pinta_pc()
            return
        lab = self._cargando("Leyendo procesador, RAM, gráfica y discos…")
        self.b_next.setEnabled(False)

        def listo(res):
            if not self.vivo() or self.i != 1:
                return
            self.hw = res
            self.b_next.setEnabled(True)
            lab.hide()
            self._pinta_pc()

        def fallo(e):
            if not self.vivo():
                return
            self.b_next.setEnabled(True)
            lab.setText(f"No pude leer tu equipo ({e}). Puedes seguir igualmente.")
            lab.tono("yellow")
        self.app.bg(sysinfo.analyze, listo, fallo)

    def _pinta_pc(self):
        sec = self.hw["sections"]
        c = Tarjeta(tone="accent", titulo="Resumen")
        for key in ("cpu", "gpu", "ram", "disks", "os"):
            if key not in sec:
                continue
            nombre, filas = sec[key]
            for k, val in filas[:2]:
                f = QHBoxLayout()
                a = Etiqueta(nombre if k == filas[0][0] else "", "small", "accent", wrap=False)
                a.setFixedWidth(110)
                f.addWidget(a)
                f.addWidget(Etiqueta(k, "h3", wrap=False))
                f.addWidget(Etiqueta(str(val), "muted"), 1)
                c.lay.addLayout(f)
        self.body.addWidget(c)
        recs = [r for r in self.hw.get("recs", []) if r[0] in ("warn", "bad")][:3]
        if recs:
            rc = Tarjeta(tone="yellow", titulo="Ojo con esto")
            for _k, titulo, texto in recs:
                rc.add(Etiqueta(titulo, "h3", "yellow"))
                rc.add(Etiqueta(texto, "muted"))
            self.body.addWidget(rc)

    # ---- 3 · Lo más importante ----
    def _p3(self):
        self._cab("Lo que más te cuesta", "Lo que más rendimiento y fluidez te quita ahora mismo, de más a menos importante.")
        if self.hallazgos is not None:
            self._pinta_hallazgos()
            return
        lab = self._cargando("Buscando lo que te cuesta rendimiento (unos segundos)…")
        self.b_next.setEnabled(False)

        def listo(res):
            if not self.vivo() or self.i != 2:
                return
            self.hallazgos = res
            self.b_next.setEnabled(True)
            lab.hide()
            self._pinta_hallazgos()

        def fallo(e):
            if not self.vivo():
                return
            self.b_next.setEnabled(True)
            lab.setText(f"No pude revisarlo ({e}). Puedes seguir igualmente.")
            lab.tono("yellow")
        self.app.bg(lambda: hidden.scan(), listo, fallo)

    def _pinta_hallazgos(self):
        malos = [f for f in self.hallazgos if f["sev"] in ("bad", "warn", "info")]
        if not malos:
            c = Tarjeta(tone="green", titulo="¡Todo en orden!")
            c.add(Etiqueta("No he encontrado nada importante: tu PC está bien configurado.", tone="green"))
            self.body.addWidget(c)
            return
        limite = len(malos) if self.pro else 2
        for f in malos[:limite]:
            tn = SEV_TONO[f["sev"]]
            c = Tarjeta(tone=tn)
            c.add(Etiqueta(f"{SEV_TXT[f['sev']]}   {f['title']}", "h3", tn))
            if f.get("impact"):
                c.add(Etiqueta("Impacto: " + f["impact"], tone=tn))
            if f.get("detail"):
                c.add(Etiqueta(f["detail"], "muted"))
            self.body.addWidget(c)
        if len(malos) > limite:
            self.body.addWidget(Etiqueta(f"+ {len(malos) - limite} cosa(s) más. Con una clave PRO las ves todas y las arreglas desde «Puntuación».", "h3", "yellow"))
        elif self.pro:
            self.body.addWidget(Etiqueta("Para ver tu nota y arreglarlas una a una, abre «Puntuación» cuando termines.", "muted"))

    # ---- 4 · Lo seguro ----
    def _p4(self):
        self._cab("Lo seguro", "Dos cosas sin riesgo que puedes hacer ya. No se marca nada que pueda dar problemas.")
        self.vars = {}
        self.c_clean = Tarjeta(tone="accent", titulo="Limpieza rápida de archivos temporales")
        self.clean_box = QVBoxLayout()
        self.c_clean.lay.addLayout(self.clean_box)
        self.body.addWidget(self.c_clean)
        self._pinta_limpieza()
        self.c_set = Tarjeta(tone="teal", titulo="Ajustes sin riesgo" + ("" if self.pro else "  ·  PRO"))
        self.set_box = QVBoxLayout()
        self.c_set.lay.addLayout(self.set_box)
        self.body.addWidget(self.c_set)
        if not self.pro:
            self.set_box.addWidget(Etiqueta("Aquí se aplicarían los ajustes seguros de Tweaks (menos latencia, sin avisos que te sacan del juego…). "
                                            "Con una clave PRO se activan. Mientras tanto, la limpieza de arriba sí funciona.", "muted"))
        else:
            self._pinta_ajustes()

    def _pinta_limpieza(self):
        vacia(self.clean_box)
        if self.limpieza is None:
            self.clean_box.addWidget(Etiqueta("Mirando cuánto se puede limpiar…", tone="accent"))

            def trabajo():
                items = [i for i in cleanup.build_items() if i.default and i.available()]
                for i in items:
                    i.scan()
                return [i for i in items if i.size > 0]

            def listo(items):
                if self.vivo():
                    self.limpieza = items
                    if self.i == 3:
                        self._pinta_limpieza()

            def fallo(_e):
                if self.vivo():
                    self.limpieza = []
                    if self.i == 3:
                        self._pinta_limpieza()
            self.app.bg(trabajo, listo, fallo)
            return
        total = sum(i.size for i in self.limpieza)
        if not self.limpieza or total < 1024 * 1024:
            self.clean_box.addWidget(Etiqueta("✓  No hay casi nada que limpiar.", "h3", "green"))
            return
        self.clean_box.addWidget(Etiqueta(f"Se pueden liberar unos {fmt_bytes(total)}.", "h2"))
        self.clean_box.addWidget(Etiqueta("Solo archivos temporales y restos que se vuelven a crear solos. No toca tus documentos, contraseñas ni historial.", "muted"))
        self.b_clean = Boton("✦  Limpiar ahora", self._limpiar_ahora)
        self.clean_box.addWidget(self.b_clean, 0, Qt.AlignmentFlag.AlignLeft)

    def _limpiar_ahora(self):
        self.b_clean.setEnabled(False)
        self.msg.setText("Limpiando…")

        def trabajo():
            freed = 0
            for i in self.limpieza:
                f, _fail = i.clean()
                freed += f
            return freed

        def listo(freed):
            if not self.vivo():
                return
            self.hecho["liberado"] += freed
            self.limpieza = []
            self.msg.setText(f"✓ Liberé {fmt_bytes(freed)}")
            if self.i == 3:
                self._pinta_limpieza()
        self.app.bg(trabajo, listo, lambda e: self.msg.setText(f"✗ {e}") if self.vivo() else None)

    def _pinta_ajustes(self):
        vacia(self.set_box)
        if self.ajustes is None:
            self.set_box.addWidget(Etiqueta("Buscando ajustes seguros para tu PC (unos segundos)…", tone="accent"))

            def trabajo():
                admin = is_admin() or DEMO
                return [a for a in tweaks.collect() if (type(a).__name__ == "RegTweak" or DEMO) and a.risk == "bajo" and not getattr(a, "warning", "")
                        and (admin or not a.needs_admin) and getattr(a, "effect", "") in ("real", "pequeño")][:10]

            def listo(acts):
                if self.vivo():
                    self.ajustes = acts
                    if self.i == 3:
                        self._pinta_ajustes()

            def fallo(_e):
                if self.vivo():
                    self.ajustes = []
                    if self.i == 3:
                        self._pinta_ajustes()
            self.app.bg(trabajo, listo, fallo)
            return
        if not self.ajustes:
            self.set_box.addWidget(Etiqueta("✓  No queda ningún ajuste seguro por aplicar.", "h3", "green"))
            return
        self.set_box.addWidget(Etiqueta("Marcados los de riesgo bajo. Desmarca el que no quieras. Se crea un punto de restauración antes.", "muted"))
        for a in self.ajustes:
            cb = Casilla(a.title, True)
            self.vars[a.id] = cb
            self.set_box.addWidget(cb)
            self.set_box.addWidget(Etiqueta(a.desc, "small"))
        self.b_set = Boton("⚡  Aplicar los marcados", self._aplicar, kind="primary", tone="teal")
        self.set_box.addWidget(self.b_set, 0, Qt.AlignmentFlag.AlignLeft)

    def _aplicar(self):
        elegidos = [a for a in self.ajustes if self.vars.get(a.id) and self.vars[a.id].isChecked()]
        if not elegidos:
            self.msg.setText("Marca primero algún ajuste.")
            return
        self.b_set.setEnabled(False)
        self.msg.setText("Creando punto de restauración…")

        def trabajo():
            try:
                actions.create_restore_point()
            except Exception:  # noqa: BLE001
                pass
            ok = 0
            for a in elegidos:
                ok += bool(actions.execute(a).ok)
            return ok, any(a.reboot for a in elegidos)

        def listo(res):
            if not self.vivo():
                return
            ok, reinicio = res
            self.hecho["ajustes"] += ok
            self.ajustes = []
            self.msg.setText(f"✓ {ok} ajuste(s) aplicados" + ("  ·  reinicia el PC para completarlos" if reinicio else ""))
            if self.i == 3:
                self._pinta_ajustes()
        self.app.bg(trabajo, listo, lambda e: self.msg.setText(f"✗ {e}") if self.vivo() else None)

    # ---- 5 · Listo ----
    def _p5(self):
        self._cab("¡Listo!", "Esto es lo que hemos hecho y por dónde seguir.")
        c = Tarjeta(tone="green", titulo="Resumen")
        lib, aj = self.hecho["liberado"], self.hecho["ajustes"]
        for t in (f"Limpieza: liberé {fmt_bytes(lib)}." if lib else "Limpieza: no hizo falta o la dejaste para luego.",
                  f"Ajustes: {aj} aplicado(s) (puedes deshacerlos desde el Historial)." if aj else
                  ("Ajustes: no apliqué ninguno." if self.pro else "Ajustes: se activan con una clave PRO.")):
            c.add(Etiqueta("•  " + t))
        self.body.addWidget(c)
        self.body.addWidget(Etiqueta("¿Por dónde sigues?", "h2"))
        destinos = [("◎  Analizar mi PC a fondo", "analysis")]
        destinos += [("★  Ver mi puntuación", "score"), ("▣  Añadir mis juegos", "games")] if self.pro else [("★  Activar una clave PRO", "license")]
        self.body.addWidget(fila(*[Boton(t, lambda p=p: self.cerrar(p), kind="soft") for t, p in destinos], None))
        self.body.addWidget(Etiqueta("Lo que necesites cambiar después, está en el menú de la izquierda. Si algo no te cuadra, el Historial lo deshace.", "muted"))
