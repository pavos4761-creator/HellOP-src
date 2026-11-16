"""Optimizar, Streaming y Mando: cada optimización en su cuadrado, con interruptor y botón «Aplicar», paquetes de un clic y medidas antes/después."""
import time

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import QHBoxLayout, QLabel, QMessageBox, QVBoxLayout, QWidget

import actions
from util import DEMO, IS_WIN, is_admin, run_cmd

from ..widgets import (Barra, Boton, Casilla, Etiqueta, Insignia, Interruptor, Pagina, Rejilla, Tarjeta, fila, vacia, repulir)
from .. import theme

PROFILES = [   # clave, icono, nombre, tono, descripción
    ("work", "✎", "Trabajo", "accent", "Un PC ágil y silencioso para el día a día: menos programas de inicio, sin telemetría ni apps basura, menús instantáneos y mejor DNS. "
                                       "No toca el plan de energía."),
    ("gaming", "☄", "Gaming", "teal", "Máxima respuesta y mínima latencia: energía al máximo, Modo Juego, prioridad de GPU/CPU, ratón sin aceleración, "
                                       "red sin límites, además de limpiar inicio y servicios."),
    ("deep", "✧", "Limpieza profunda", "accent", "Quita lo que Windows hace sin que lo pidas: telemetría, tareas programadas, publicidad, Copilot/Recall, Edge en segundo plano, "
                                                   "reparto P2P de actualizaciones y servicios sobrantes."),
    ("extreme", "☢", "Extremo", "red", "Todo lo de Gaming MÁS ajustes profundos: arranque, energía de CPU/PCIe/USB, registro, red, modo MSI de la GPU y opciones que "
                                        "cambian seguridad por FPS. Cada uno dice su efecto REAL y su riesgo."),
    ("full", "⚙", "Completo", "green", "Todo lo anterior junto."),
]

# icono y tono de cada grupo de optimizaciones
VISUAL = {
    "power": ("⚡", "yellow"), "speed": ("▶", "accent"), "gaming": ("▣", "teal"), "latency": ("◎", "accent"), "advanced": ("✦", "accent"),
    "gpu": ("▤", "teal"), "deep": ("✧", "accent"), "tradeoff": ("☢", "red"), "startup": ("⏻", "yellow"), "services": ("⚙", "accent"),
    "bloat": ("✖", "red"), "procs": ("▦", "yellow"), "network": ("≈", "green"), "mando": ("✜", "teal"), "streaming": ("◉", "yellow"),
}

PAQUETES = [   # id, icono, nombre, tono, texto, qué ajustes entran
    ("seguro", "✔", "Todo lo seguro", "green", "Solo ajustes de riesgo bajo que se pueden deshacer. Lo que haría yo sin pensarlo.",
     lambda a: a.risk == "bajo" and a.reversible),
    ("latencia", "◎", "Menos latencia", "accent", "Reloj del sistema, red, energía y arranque: que todo responda al instante.",
     lambda a: a.group in ("latency", "advanced", "power", "network") and a.risk != "alto" and a.reversible),
    ("fps", "▣", "Más FPS", "teal", "Prioridades de juego, gráfica y energía para subir los mínimos y quitar tirones.",
     lambda a: a.group in ("gaming", "gpu", "power") and a.risk != "alto" and a.reversible),
    ("limpieza", "✦", "Limpieza de fondo", "yellow", "Programas de inicio, servicios y basura de Windows que consumen sin que lo sepas.",
     lambda a: a.group in ("startup", "services", "bloat", "deep") and a.risk != "alto" and a.reversible),
]

LIMPIEZA = ("startup", "services", "bloat", "procs", "deep")


def paquete_acciones(sel, acts):
    ok_admin = is_admin()
    return [a for a in acts if sel(a) and (ok_admin or not a.needs_admin)]


def paquetes_utiles(acts):
    vistos, out = [], []
    for datos in PAQUETES:
        ids = tuple(sorted(id(a) for a in paquete_acciones(datos[5], acts)))
        if not ids or ids in vistos:
            continue
        vistos.append(ids)
        out.append(datos)
    return out


def _medir():
    try:
        import medir
        return medir.instantanea()
    except Exception:  # noqa: BLE001
        return None


def _icono(glifo, tone, tam=40):
    """Cuadradito redondeado con un glifo."""
    lb = QLabel(glifo)
    lb.setAlignment(Qt.AlignmentFlag.AlignCenter)
    lb.setFixedSize(tam, tam)
    col = theme.C.get(tone, theme.C["accent"])
    lb.setStyleSheet(f"background: {theme.hexa(tone, 0.14)}; color: {col}; border-radius: {tam // 3}px; font-size: {int(tam * 0.42)}px; font-weight: 700;")
    return lb


# ---------------------------------------------------------------------------------- un cuadrado
class Cuadro(Tarjeta):
    def __init__(self, page, a):
        super().__init__(margen=14, espacio=0)
        self.page, self.a, self.estado, self.largo = page, a, "idle", False
        glifo, tone = VISUAL.get(a.group, ("•", "accent"))
        self.tone_g = tone
        cab = QHBoxLayout()
        cab.addWidget(_icono(glifo, tone))
        cab.addStretch(1)
        self.sw = Interruptor(False)
        self.sw.cambio.connect(lambda _on: self._cambia())
        cab.addWidget(self.sw)
        self.lay.addLayout(cab)
        t = Etiqueta(a.title, "h3")
        self.lay.addSpacing(10)
        self.lay.addWidget(t)
        if getattr(a, "status", ""):
            self.lay.addSpacing(4)
            self.lay.addWidget(Etiqueta(a.status, "mono"))
        self.texto_corto = a.desc if len(a.desc) <= 125 else a.desc[:122].rsplit(" ", 1)[0] + "…"
        self.d = Etiqueta(self.texto_corto, "muted")
        self.lay.addSpacing(6)
        self.lay.addWidget(self.d)
        self.mas = None
        if len(a.desc) > 125 or getattr(a, "warning", ""):
            self.mas = Boton("Ver más ▾", self._largo, kind="link")
            self.lay.addWidget(self.mas, 0, Qt.AlignmentFlag.AlignLeft)
        self.lay.addSpacing(10)
        t1 = QHBoxLayout()
        t1.setSpacing(5)
        rt, rc = {"bajo": ("Riesgo bajo", "green"), "medio": ("Riesgo medio", "yellow"), "alto": ("Riesgo alto", "red")}.get(a.risk, ("Riesgo medio", "yellow"))
        t1.addWidget(Insignia(rt, rc))
        ef = {"real": ("Efecto real", "green"), "pequeño": ("Efecto pequeño", "yellow"), "depende": ("Depende de tu PC", "accent"),
              "mínimo": ("Casi nulo", "muted")}.get(getattr(a, "effect", ""))
        if ef:
            t1.addWidget(Insignia(*ef))
        t1.addStretch(1)
        self.lay.addLayout(t1)
        extras = []
        if a.reboot:
            extras.append(("↻ Reinicio", "accent"))
        if not a.reversible:
            extras.append(("No se deshace", "yellow"))
        if a.needs_admin and not is_admin():
            extras.append(("Necesita admin", "red"))
        if extras:
            t2 = QHBoxLayout()
            t2.setSpacing(5)
            for tx, tn in extras:
                t2.addWidget(Insignia(tx, tn))
            t2.addStretch(1)
            self.lay.addSpacing(4)
            self.lay.addLayout(t2)
        self.lay.addStretch(1)
        self.lay.addSpacing(12)
        pie = QHBoxLayout()
        self.btn = Boton("Aplicar", lambda: self.page.aplicar([self]), kind="soft", tone=tone if tone not in ("yellow",) else None)
        pie.addWidget(self.btn)
        self.msg = Etiqueta("", "small", "muted", wrap=True)
        pie.addWidget(self.msg, 1)
        self.lay.addLayout(pie)

    # ---- selección ----
    def sel(self):
        return self.sw.isChecked() and self.estado in ("idle", "bad")

    def poner_sel(self, on):
        if self.estado in ("run", "ok"):
            return
        self.sw.poner(on)
        self._borde()

    def _cambia(self):
        self._borde()
        self.page.actualiza_barra()

    def _borde(self):
        self.setProperty("sel", "true" if self.sw.isChecked() and self.estado in ("idle", "bad") else "false")
        self.setProperty("tone", "green" if self.estado == "ok" else "red" if self.estado == "bad" else "")
        repulir(self)

    def _largo(self):
        self.largo = not self.largo
        txt = self.a.desc + (("\n\n⚠  " + self.a.warning) if getattr(self.a, "warning", "") else "")
        self.d.setText(txt if self.largo else self.texto_corto)
        self.d.role(None if self.largo else "muted")
        if self.mas:
            self.mas.setText("Ver menos ▴" if self.largo else "Ver más ▾")

    # ---- estados ----
    def corriendo(self):
        self.estado = "run"
        self.sw.setEnabled(False)
        self.btn.setEnabled(False)
        self.msg.setText("Aplicando…")
        self.msg.tono("accent")

    def fin(self, r):
        if r.ok:
            self.estado = "ok"
            self.sw.poner(False, animar=False)
            self.sw.setEnabled(False)
            self.btn.hide()
            self.msg.setText("✓ Aplicado")
            self.msg.tono("green")
        else:
            self.estado = "bad"
            self.sw.setEnabled(True)
            self.btn.setEnabled(True)
            self.btn.setText("Reintentar")
            self.msg.setText("✗ " + r.msg[:80])
            self.msg.tono("red")
        self._borde()


class Paquete(Tarjeta):
    def __init__(self, page, datos, acts):
        pid, ico, nombre, tone, texto, sel = datos
        super().__init__(tone=tone, margen=14, espacio=6)
        n = len(paquete_acciones(sel, acts))
        cab = QHBoxLayout()
        cab.addWidget(_icono(ico, tone, 44))
        col = QVBoxLayout()
        col.setSpacing(0)
        col.addWidget(Etiqueta(nombre, "h3"))
        col.addWidget(Etiqueta(f"{n} ajuste{'s' if n != 1 else ''}", "small", tone if tone != "yellow" else "muted"))
        cab.addLayout(col, 1)
        self.lay.addLayout(cab)
        self.lay.addWidget(Etiqueta(texto, "muted"))
        self.lay.addStretch(1)
        pie = QHBoxLayout()
        pie.addWidget(Boton("Aplicar", lambda: page.aplica_paquete(sel), kind="primary", tone=tone if tone != "yellow" else None))
        pie.addWidget(Boton("Marcar", lambda: page.marca_paquete(sel), kind="ghost"))
        pie.addStretch(1)
        self.lay.addLayout(pie)


# ---------------------------------------------------------------------------------- la pantalla
class Optimizar(Pagina):
    perfiles = True          # Streaming y Mando lo ponen a False (tienen su propio perfil)
    perfil_fijo = None
    titulo_pagina = "Optimizar"
    sub_pagina = "Cada optimización en su cuadrado: márcala con el interruptor y aplica varias juntas, o pulsa «Aplicar» en una sola."

    def __init__(self, app):
        super().__init__(app, "", "")
        self.cuadros, self.acts = [], []
        self.applied, self.failed = [], []
        self.need_reboot = False
        self.busy = False
        self.profile = None
        self._restore_hecho = False
        self.v_restore = Casilla("Punto de restauración", True)
        self._barra_lista = False
        self._iniciada = False

    # ---- ciclo ----
    def al_mostrar(self):
        if not self._iniciada:
            self._iniciada = True
            self.show_intro()

    def reset_state(self):
        self.acts, self.cuadros = [], []
        self.applied, self.failed = [], []
        self.need_reboot = False
        self.busy = False
        self.profile = None

    def limpia(self):
        super().limpia()
        self.muestra_barra(False)

    def heading(self, titulo, sub=""):
        self.encabezado(titulo, sub)

    def aviso_admin(self, texto):
        if not is_admin():
            c = Tarjeta(tone="red")
            c.add(Etiqueta(texto, tone="yellow"))
            self.add(c)

    # ---- 1. entrada: directamente los cuadrados ----
    def show_intro(self):
        self.start(self.profile or self.perfil_fijo or "full")

    def _chips(self, actual):
        h = QHBoxLayout()
        h.setSpacing(6)
        h.addWidget(Etiqueta("Nivel:", "small", wrap=False))
        for key, _ic, nombre, _tn, _d in PROFILES:
            on = key == actual
            h.addWidget(Boton(nombre, (lambda k=key: self.start(k)) if not on else (lambda: None), kind="primary" if on else "ghost"))
        h.addStretch(1)
        w = QWidget()
        w.setLayout(h)
        self.add(w)

    def _esqueleto(self):
        rej = Rejilla(3)
        for _ in range(6):
            c = Tarjeta(margen=14)
            c.setMinimumHeight(190)
            for ancho in (40, 120, 220, 170):
                b = QWidget()
                b.setFixedSize(ancho, 12 if ancho != 40 else 40)
                b.setStyleSheet(f"background: {theme.C['track']}; border-radius: 5px;")
                c.lay.addWidget(b)
            rej.add(c)
        return rej

    # ---- 2. buscar ----
    def start(self, profile):
        self.reset_state()
        self.profile = profile
        self.limpia()
        self.heading(self.titulo_pagina, "Mirando tu PC… los cuadrados aparecen en un momento.")
        if self.perfiles:
            self._chips(profile)
        self.scan_msg = Etiqueta("Empezando…", "small", "accent")
        self.add(self.scan_msg)
        self.add(self._esqueleto())
        g = self.gen
        self.app.bg(lambda: actions.discover(profile, progress=lambda m: self.app.ui(self._scan_msg, g, m)), lambda acts: self.after_scan(g, acts))

    def _scan_msg(self, g, m):
        if g == self.gen:
            self.scan_msg.setText(m)

    def after_scan(self, g, acts):
        if g != self.gen:
            return
        if not acts:
            self.limpia()
            self.heading("Tu PC ya está muy bien", "No encontré nada que mejorar para este nivel.")
            if self.perfiles:
                self._chips(self.profile)
            return
        self.acts = acts
        self._restore_hecho = False
        self.show_grid()

    # ---- 3. cuadrícula ----
    def show_grid(self):
        self.limpia()
        g = self.gen
        acts = self.acts
        self.cuadros = []
        n = len(acts)
        self.heading(f"{n} optimizaciones para tu PC", "Marca con el interruptor y aplica juntas, o pulsa «Aplicar» en una sola. Solo sale lo que está sin hacer en tu PC.")
        self.resultado = QVBoxLayout()
        self.resultado.setSpacing(12)
        self.col.addLayout(self.resultado)
        self.hallazgos = QVBoxLayout()
        self.col.addLayout(self.hallazgos)
        if self.perfiles:
            self.app.bg(lambda: __import__("cuello").run()[1], lambda it: self._hallazgos(g, it), lambda e: None)
            self._chips(self.profile)
        self.aviso_admin("Estás sin permisos de administrador: lo que toca servicios, energía, red o el registro del sistema no se podrá aplicar. "
                         "Usa «Reabrir como administrador» (arriba) para aplicarlo.")
        packs = paquetes_utiles(acts)
        if packs:
            self.add(Etiqueta("Paquetes de un clic", "h2"))
            rej = Rejilla(min(4, len(packs)))
            for d in packs[:4]:
                rej.add(Paquete(self, d, acts))
            self.add(rej)
        herr = QHBoxLayout()
        herr.addWidget(Etiqueta("Todas las optimizaciones", "h2", wrap=False))
        herr.addStretch(1)
        herr.addWidget(Boton("Quitar marcas", self.quita_marcas, kind="ghost"))
        herr.addWidget(Boton("Marcar las seguras", self.marca_seguras, kind="soft"))
        w = QWidget()
        w.setLayout(herr)
        self.col.addSpacing(8)
        self.add(w)
        orden = []
        for a in acts:
            if a.group not in orden:
                orden.append(a.group)
        for gr in orden:
            lista = [a for a in acts if a.group == gr]
            cab = QHBoxLayout()
            cab.addWidget(Etiqueta(actions.GROUP_NAMES.get(gr, gr).upper(), "small", wrap=False))
            cab.addWidget(Etiqueta(str(len(lista)), "small", "accent", wrap=False))
            cab.addWidget(Boton("marcar grupo", lambda gr=gr: self.marca_grupo(gr), kind="link"))
            cab.addStretch(1)
            wc = QWidget()
            wc.setLayout(cab)
            self.col.addSpacing(6)
            self.add(wc)
            rej = Rejilla(3)
            for a in lista:
                c = Cuadro(self, a)
                self.cuadros.append(c)
                rej.add(c)
            self.add(rej)
        self.muestra_barra(True)
        self.actualiza_barra()

    # ---- selección ----
    def marca_seguras(self):
        for c in self.cuadros:
            c.poner_sel(c.a.risk == "bajo" and c.a.reversible and (not c.a.needs_admin or is_admin()))
        self.actualiza_barra()

    def quita_marcas(self):
        for c in self.cuadros:
            c.poner_sel(False)
        self.actualiza_barra()

    def marca_grupo(self, gr):
        for c in self.cuadros:
            if c.a.group == gr:
                c.poner_sel(True)
        self.actualiza_barra()

    def marca_paquete(self, sel):
        ids = {id(a) for a in paquete_acciones(sel, self.acts)}
        for c in self.cuadros:
            c.poner_sel(id(c.a) in ids)
        self.actualiza_barra()

    def aplica_paquete(self, sel):
        ids = {id(a) for a in paquete_acciones(sel, self.acts)}
        lista = [c for c in self.cuadros if id(c.a) in ids and c.estado in ("idle", "bad")]
        if lista and self.app.pregunta("Aplicar paquete", f"Voy a aplicar {len(lista)} ajustes (todos de riesgo bajo o medio y reversibles).\n\n¿Seguro?"):
            self.aplicar(lista, confirmado=True)

    # ---- barra de abajo ----
    def _crea_barra(self):
        h = self.barra_inferior()
        izq = QVBoxLayout()
        izq.setSpacing(0)
        self.lbl_sel = Etiqueta("", "h3", wrap=False)
        self.lbl_res = Etiqueta("", "small", "muted", wrap=True)
        izq.addWidget(self.lbl_sel)
        izq.addWidget(self.lbl_res)
        h.addLayout(izq, 1)
        h.addWidget(self.v_restore)
        self.b_fin = Boton("Terminar", self.show_summary, kind="ghost")
        self.b_reb = Boton("Reiniciar ahora", self.reboot_now, kind="soft", tone="yellow")
        self.b_apl = Boton("Aplicar seleccionadas", lambda: self.aplicar([c for c in self.cuadros if c.sel()]), kind="primary", tone="green")
        h.addWidget(self.b_reb)
        h.addWidget(self.b_fin)
        h.addWidget(self.b_apl)
        self.b_reb.hide()
        self._barra_lista = True

    def muestra_barra(self, si):
        if si and not self._barra_lista:
            self._crea_barra()
        if self.pie is not None:
            self.pie.setVisible(bool(si))

    def actualiza_barra(self):
        if not self._barra_lista:
            return
        n = sum(1 for c in self.cuadros if c.sel())
        self.lbl_sel.setText(f"{n} seleccionada{'s' if n != 1 else ''}" if n else "Ninguna seleccionada")
        self.b_apl.setText(f"Aplicar seleccionadas ({n})" if n else "Aplicar seleccionadas")
        self.b_apl.setEnabled(n > 0 and not self.busy)
        done = len(self.applied)
        if done and not self.busy:
            self.lbl_res.setText(f"✓ {done} aplicadas" + (f"  ·  ✗ {len(self.failed)} con error" if self.failed else "") +
                                 ("  ·  reinicia para notar todos los cambios" if self.need_reboot else ""))
            self.lbl_res.tono("green" if not self.failed else "yellow")
        if self.need_reboot and IS_WIN and not DEMO:
            self.b_reb.show()

    # ---- 4. aplicar ----
    def aplicar(self, lista, confirmado=False):
        lista = [c for c in lista if c.estado in ("idle", "bad")]
        if self.busy or not lista:
            return
        altos = [c for c in lista if c.a.risk == "alto"]
        if altos and not confirmado:
            txt = "\n\n".join(f"{c.a.title}\n{getattr(c.a, 'warning', '')}" for c in altos[:3])
            if not self.app.pregunta("Ajustes de riesgo ALTO", txt + "\n\nSe pueden deshacer desde «Historial / Deshacer», pero mientras estén aplicados "
                                                                      "tu PC estará menos protegido.\n\n¿Seguro que quieres aplicarlos?"):
                lista = [c for c in lista if c.a.risk != "alto"]
                if not lista:
                    return
        self.busy = True
        g = self.gen
        self.b_apl.setEnabled(False)
        quiere_restore = self.v_restore.isChecked() and not self._restore_hecho
        for c in lista:
            c.corriendo()

        def work():
            antes = _medir()
            self.app.ui(self._res, g, "Midiendo tu PC antes de cambiar nada…")
            if quiere_restore:
                self.app.ui(self._res, g, "Creando el punto de restauración de Windows (puede tardar un minuto)…")
                ok, _msg = actions.create_restore_point()
                self._restore_hecho = True
                if not ok:
                    self.app.ui(self._res, g, "No pude crear el punto de restauración; sigo igualmente (todo se puede deshacer desde el Historial).")
            res = []
            for i, c in enumerate(lista, 1):
                self.app.ui(self._res, g, f"Aplicando {i} de {len(lista)}: {c.a.title[:70]}…")
                r = actions.execute(c.a)
                res.append((c, r))
                self.app.ui(self._uno, g, c, r)
            despues = None
            if antes:
                self.app.ui(self._res, g, "Midiendo otra vez para comparar…")
                time.sleep(3)
                despues = _medir()
            return res, antes, despues

        self.app.bg(work, lambda out: self._fin_lote(g, out))

    def _res(self, g, texto):
        if g == self.gen:
            self.lbl_res.setText(texto)
            self.lbl_res.tono("accent")

    def _uno(self, g, c, r):
        if g != self.gen:
            return
        c.fin(r)
        if r.ok:
            self.applied.append(c.a)
            self.need_reboot = self.need_reboot or c.a.reboot
        else:
            self.failed.append((c.a, r.msg))

    def _fin_lote(self, g, out):
        self.busy = False
        if g != self.gen:
            return
        res, antes, despues = out
        self.actualiza_barra()
        if antes and despues:
            self.muestra_medidas(antes, despues, len(res), any(c.a.reboot for c, r in res if r.ok))

    def muestra_medidas(self, antes, despues, n, reinicio):
        import medir
        vacia(self.resultado)
        c = Tarjeta(tone="green")
        c.add(Etiqueta("Resultado medido en tu PC", "h2"))
        c.add(Etiqueta(f"Medí antes y después de aplicar {n} ajuste{'s' if n != 1 else ''}. Si una fila dice «igual», no cambió nada medible: "
                       "no te prometo más de lo que se ve aquí.", "muted"))
        col = {"mejor": ("green", "✓ mejor"), "igual": ("muted", "= igual"), "peor": ("red", "✗ peor")}
        for t, a, b, u, v in medir.comparar(antes, despues):
            f = QHBoxLayout()
            f.addWidget(Etiqueta(t, wrap=False), 3)
            f.addWidget(Etiqueta(f"{a} → {b} {u}", "h3", wrap=False), 2)
            f.addWidget(Etiqueta(col[v][1], "h3", col[v][0], wrap=False), 1)
            c.lay.addLayout(f)
        if reinicio:
            c.add(Etiqueta("Varios ajustes necesitan reiniciar el PC: esos no se pueden medir hasta entonces. Reinicia y pulsa «FPS reales» para comprobarlos con un juego.", tone="yellow"))
        c.add(Boton("Comprobarlo con tu juego (FPS reales)", lambda: self.app.ir("fps"), kind="soft"), 0, Qt.AlignmentFlag.AlignLeft)
        self.resultado.addWidget(c)
        self.scroll.verticalScrollBar().setValue(0)

    def _hallazgos(self, g, items):
        """Lo que de verdad más te frena (hardware/configuración que ningún tweak de registro arregla)."""
        if g != self.gen:
            return
        top = [i for i in items if i["prio"] <= 1][:3]
        c = Tarjeta(tone="yellow" if top else "green")
        if not top:
            c.add(Etiqueta("Lo que más te frena: nada importante", "h2", "green"))
            c.add(Etiqueta("Tu RAM, tus discos y tu configuración no tienen ningún problema grave. Lo que sale abajo son ajustes pequeños.", "muted"))
            self.hallazgos.addWidget(c)
            return
        c.add(Etiqueta("Lo que más te frena (esto sí se nota)", "h2"))
        c.add(Etiqueta("Estos son problemas reales de tu equipo; arreglarlos rinde más que casi todos los ajustes de abajo.", "muted"))
        for i in top:
            f = QHBoxLayout()
            f.addWidget(Etiqueta("●", "h3", "red" if i["prio"] == 0 else "yellow", wrap=False), 0, Qt.AlignmentFlag.AlignTop)
            col = QVBoxLayout()
            col.setSpacing(0)
            col.addWidget(Etiqueta(i["title"], "h3"))
            col.addWidget(Etiqueta(i["why"], "muted"))
            f.addLayout(col, 1)
            if {"xmp": "bios"}.get(i["key"]):
                f.addWidget(Boton("Ver guía", lambda: self.app.ir("bios"), kind="soft", tone="yellow"))
            c.lay.addLayout(f)
        self.hallazgos.addWidget(c)

    # ---- 5. resumen ----
    def show_summary(self):
        self.limpia()
        self.heading("¡Listo!", "Esto es lo que ha pasado.")
        c = Tarjeta(tone="green", titulo="Resumen")
        sin = max(0, len(self.acts) - len(self.applied) - len(self.failed))
        c.add(Etiqueta(f"✓ {len(self.applied)} aplicados     ·     {sin} sin aplicar     ·     ✗ {len(self.failed)} con error", "h3"))
        for a in self.applied[:25]:
            c.add(Etiqueta("✓  " + a.title, tone="green"))
        if len(self.applied) > 25:
            c.add(Etiqueta(f"… y {len(self.applied) - 25} más", "muted"))
        for a, msg in self.failed[:10]:
            c.add(Etiqueta(f"✗  {a.title}: {msg[:120]}", tone="red"))
        if self.need_reboot:
            c.add(Etiqueta("Algunos cambios (ratón, efectos visuales, GPU) se notan al cerrar sesión o reiniciar. El tiempo de arranque de Windows solo se actualiza tras reiniciar.", tone="yellow"))
        self.add(c)
        if self.profile == "mando":
            import mando
            t = Tarjeta(tone="teal", titulo="Para jugar con mando con el mínimo retraso (lo que de verdad funciona)")
            for tip in mando.CONSEJOS:
                t.add(Etiqueta("•  " + tip))
            self.add(t)
        if self.profile == "streaming":
            import streaming
            t = Tarjeta(tone="yellow", titulo="Para emitir sin perder FPS (lo que de verdad funciona)")
            for tip in streaming.CONSEJOS:
                t.add(Etiqueta("•  " + tip))
            if not any(a.id == "obs_profile" for a in self.applied):
                t.add(Etiqueta("No apareció el perfil de OBS: si no tienes OBS Studio instalado (o ya estaba creado), solo se aplicaron los ajustes de Windows.", "muted"))
            self.add(t)
        botones = [Boton("Ver historial / deshacer", lambda: self.app.ir("history"), kind="primary")]
        if self.need_reboot and IS_WIN and not DEMO:
            botones.append(Boton("Reiniciar ahora", self.reboot_now, kind="soft", tone="yellow"))
        botones.append(Boton("Volver al inicio", self.show_intro, kind="ghost"))
        botones.append(None)
        self.add(fila(*botones))

    def reboot_now(self):
        if self.app.pregunta("Reiniciar", "Guarda tu trabajo. ¿Reiniciar el PC dentro de 10 segundos?"):
            run_cmd(["shutdown", "/r", "/t", "10"])


# ---------------------------------------------------------------------------------- Streaming y Mando
class Streaming(Optimizar):
    perfiles = False
    perfil_fijo = "streaming"
    titulo_pagina = "Streaming"

    def show_intro(self):
        import streaming
        self.limpia()
        self.muestra_barra(False)
        self.heading("Streaming", "Emite en directo sin que tu juego pierda FPS. Verás cada ajuste en su cuadrado y decides cuáles aplicar.")
        self.aviso_admin("Estás sin permisos de administrador: el punto de restauración y algunos ajustes no se podrán aplicar. Usa «Reabrir como administrador» (arriba).")
        c = Tarjeta(tone="yellow", titulo="Qué hace")
        for t in ("Crea un perfil NUEVO en OBS Studio («HellOP Streaming») con el codificador de tu gráfica (NVENC, AMF o Quick Sync), que casi no resta FPS al juego, "
                  "a diferencia de codificar con la CPU. Tu perfil actual de OBS no se toca.",
                  "Elige resolución, FPS y bitrate acordes a tu pantalla y a tu codificador (los que recomiendan Twitch y YouTube).",
                  "Pone OBS (y Streamlabs, si lo tienes) en «Alto rendimiento» en la configuración de gráficos de Windows.",
                  "Añade los ajustes de Gaming que no molestan al directo y protege OBS/Discord para que nunca se cierren por error.",
                  "Todo se puede deshacer desde «Historial / Deshacer»; el perfil de OBS se borra solo si lo creó HellOP."):
            c.add(Etiqueta("•  " + t))
        self.add(c)
        det = Tarjeta(tone="accent", titulo="Lo que he encontrado en tu PC")
        lbl = Etiqueta("Mirando OBS y tu gráfica…", "muted")
        det.add(lbl)
        self.add(det)
        g = self.gen

        def detectar():
            obs, sl, names = streaming.find_obs(), streaming.find_streamlabs(), streaming.gpu_names()
            enc, nombre = streaming.pick_encoder(names)
            return obs, sl, names, nombre, streaming.plan(enc, streaming.pantalla())

        def listo(r):
            if g != self.gen:
                return
            obs, sl, names, nombre, (ow, oh, fps, kbps) = r
            lbl.hide()
            for t, tn in (("OBS Studio: " + ("encontrado" if obs else "no lo encuentro (instálalo y vuelve; sin él solo se aplican los ajustes de Windows)"), "green" if obs else "yellow"),
                          ("Streamlabs: " + ("encontrado" if sl else "no encontrado"), "green" if sl else "muted"),
                          ("Gráfica: " + (", ".join(names) if names else "no la he podido leer"), None),
                          (f"Codificador que usaré: {nombre}", None), (f"Calidad: {ow}×{oh} a {fps} FPS · {kbps} kbps", None)):
                det.add(Etiqueta(t, tone=tn))

        self.app.bg(detectar, listo, lambda e: lbl.setText(f"No pude mirar tu equipo: {e}"))
        opts = Tarjeta(tone="teal", titulo="Antes de empezar")
        opts.add(self.v_restore)
        self.add(opts)
        self.add(Boton("◉   Preparar mi PC para streaming", lambda: self.start("streaming"), kind="primary", tone="yellow"), 0, Qt.AlignmentFlag.AlignLeft)


class Mando(Optimizar):
    perfiles = False
    perfil_fijo = "mando"
    titulo_pagina = "Mando"

    def show_intro(self):
        import mando
        self.limpia()
        self.muestra_barra(False)
        self.heading("Mando", "Menos tirones y menos retraso al jugar con mando. Verás cada ajuste en su cuadrado y decides cuáles aplicar.")
        self.aviso_admin("Estás sin permisos de administrador: varios ajustes no se podrán aplicar. Usa «Reabrir como administrador» (arriba).")
        c = Tarjeta(tone="teal", titulo="Qué hace (y qué no)")
        for t in ("Evita que Windows apague los puertos USB, el Bluetooth y el propio mando para ahorrar energía: es la causa típica de que un mando «se duerma» y tarde "
                  "en responder. Incluye dos ajustes ocultos del plan de energía: el enlace USB 3 y el adaptador Bluetooth/Wi-Fi.",
                  "Revisa el Administrador de dispositivos y te ofrece, uno por uno, desactivar lo que sobra en TU PC (adaptadores virtuales sin uso, y la radio Bluetooth si juegas "
                  "por cable). Nada se desinstala: se reactiva con «Deshacer».",
                  "Quita las entradas fantasma de mandos que ya no usas.",
                  "Te da los consejos que sí cambian el retraso (cable, FPS, Reflex…).",
                  "Juegos en ventana o sin bordes: usa el modo rápido de Windows 11 (menos retraso), un ajuste que solo está aquí.",
                  "Aquí solo hay ajustes del mando: lo de FPS, Game Bar, temporizador, HPET, PCIe, plan de energía y suspensión USB está en «Modo Extremo» y no se mezcla.",
                  "Sé claro: retraso 0 no existe. Esto quita tirones y capas de más; no hace magia. Todo se deshace desde «Historial / Deshacer»."):
            c.add(Etiqueta("•  " + t))
        self.add(c)
        det = Tarjeta(tone="accent", titulo="Mandos que he encontrado")
        lbl = Etiqueta("Buscando mandos conectados…", "muted")
        det.add(lbl)
        self.add(det)
        g = self.gen

        def listo(lista):
            if g != self.gen:
                return
            lbl.hide()
            if not lista:
                det.add(Etiqueta("No veo ningún mando conectado ahora. Conéctalo y vuelve a entrar si quieres que lo compruebe; los ajustes valen igual.", tone="yellow"))
                return
            txt = {"cable": ("por cable", "green"), "bluetooth": ("por Bluetooth", "yellow"), "receptor": ("con receptor", None)}
            for n, con in lista:
                t, tn = txt.get(con, (con, None))
                det.add(Etiqueta(f"{n}  ·  {t}", tone=tn))
            if any(cn == "bluetooth" for _n, cn in lista):
                det.add(Etiqueta("Consejo: por cable tendrás menos retraso y menos saltos que por Bluetooth.", "small"))

        self.app.bg(mando.mandos, listo, lambda e: lbl.setText(f"No pude mirar tus mandos: {e}"))
        opts = Tarjeta(tone="teal", titulo="Antes de empezar")
        opts.add(self.v_restore)
        self.add(opts)
        self.add(Boton("✜   Optimizar mi PC para mando", lambda: self.start("mando"), kind="primary", tone="teal"), 0, Qt.AlignmentFlag.AlignLeft)
