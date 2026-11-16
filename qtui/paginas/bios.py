"""Pantalla «BIOS»: qué cambiar en la BIOS para el máximo rendimiento + tiempos de RAM (versión Qt)."""
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QGridLayout, QHBoxLayout, QVBoxLayout, QWidget

import bios
from util import DEMO

from ..widgets import Barra, Boton, Casilla, Etiqueta, Insignia, Pagina, Tarjeta, fila, vacia

EFFECT = {"real": ("EFECTO REAL", "green"), "pequeño": ("EFECTO PEQUEÑO", "yellow"),
          "depende": ("DEPENDE DE TU EQUIPO", "teal"), "mínimo": ("EFECTO CASI NULO", "muted")}
RISK = {"bajo": ("RIESGO BAJO", "green"), "medio": ("RIESGO MEDIO", "yellow"), "alto": ("RIESGO ALTO", "red")}
TIER_TONE = {1: "green", 2: "yellow", 3: "red"}


def _kv(rows):
    """Filas «etiqueta · valor» en dos columnas."""
    w = QWidget()
    g = QGridLayout(w)
    g.setContentsMargins(0, 0, 0, 0)
    g.setHorizontalSpacing(14)
    g.setVerticalSpacing(6)
    g.setColumnStretch(1, 1)
    for i, (k, v) in enumerate(rows):
        g.addWidget(Etiqueta(str(k), "small"), i, 0, Qt.AlignmentFlag.AlignTop)
        g.addWidget(Etiqueta(str(v)), i, 1, Qt.AlignmentFlag.AlignTop)
    g.setColumnMinimumWidth(0, 150)
    return w


class Bios(Pagina):
    titulo_texto = "BIOS · máximo rendimiento"
    sub_texto = "Lo que NO se puede cambiar desde Windows (tiempos de RAM, CPU, placa), explicado paso a paso para TU equipo."

    def __init__(self, app):
        super().__init__(app)
        self.guide = None
        self.checks = bios.load_checks()
        self.cajas = {}
        self.prog = None

        self.btn = Boton("◉   GENERAR MI GUÍA DE BIOS", self.run, kind="primary")
        self.msg = Etiqueta("", "muted", wrap=True)
        self.add(fila(self.btn, self.msg, None, espacio=16))
        self.pb = Barra(0, "accent")
        self.pb.setRange(0, 0)
        self.pb.hide()
        self.add(self.pb)

        intro = Tarjeta(tone="accent")
        intro.add(Etiqueta(
            "Pulsa el botón y leo tu procesador, placa, RAM y gráfica para darte: (1) los tiempos de RAM recomendados por niveles, "
            "(2) una lista de ajustes de BIOS con la ruta de menú de TU placa, y (3) un botón para reiniciar directo a la BIOS. "
            "Puedes guardar la guía en un archivo para mirarla en el móvil mientras estás dentro de la BIOS.", "muted"))
        self.add(intro)

        self.body = QWidget()
        self.body_lay = QVBoxLayout(self.body)
        self.body_lay.setContentsMargins(0, 0, 0, 0)
        self.body_lay.setSpacing(12)
        self.add(self.body)

    # ------------------------------------------------------------------
    def run(self):
        self.btn.set_enabled(False)
        self.msg.setText("Leyendo tu equipo…")
        self.msg.tono("accent")
        self.pb.show()
        self.app.bg(bios.build_guide, self.done, self.fail)

    def fail(self, e):
        self.pb.hide()
        self.btn.set_enabled(True)
        self.msg.setText(f"No pude generar la guía: {e}")
        self.msg.tono("red")

    def done(self, g):
        self.pb.hide()
        self.btn.set_enabled(True)
        self.btn.set_text("◉   REGENERAR GUÍA")
        self.msg.setText("Guía lista ✓")
        self.msg.tono("green")
        self.guide = g
        self.render(g)

    # ------------------------------------------------------------------
    def render(self, g):
        vacia(self.body_lay)
        add = self.body_lay.addWidget

        c = Tarjeta(tone="teal", titulo="◎  Tu plataforma")
        c.add(_kv(g["platform"]))
        if g["laptop"]:
            c.add(Etiqueta("Parece un portátil: la mayoría de portátiles esconden estas opciones o no dejan cambiarlas. "
                           "Usa lo que tu BIOS te permita y no fuerces nada.", "small", "yellow"))
        add(c)

        add(self._enter_card(g))
        add(self._status_card(g))
        if g["ram"]:
            add(self._ram_card(g["ram"]))
        self._items(g["items"])
        for title, tips in g["gpu_tips"]:
            cc = Tarjeta(tone="green", titulo="▲  " + title)
            for t in tips:
                cc.add(Etiqueta("•  " + t))
            add(cc)

        end = Tarjeta(tone="red", titulo="⚠  Si algo sale mal")
        end.add(Etiqueta("Si tras un cambio el PC no arranca o da pantalla negra: apaga, espera 10 s y reinicia 2–3 veces (la BIOS vuelve a valores seguros). "
                         "Si no basta: botón o jumper «Clear CMOS» de la placa, o quita la pila plana 30 segundos con el PC desenchufado."))
        add(end)

    def _enter_card(self, g):
        c = Tarjeta(tone="red", titulo="⏻  Entrar a la BIOS")
        c.add(Etiqueta(f"Al encender el PC pulsa repetidamente  {g['enter_key']}.  O desde aquí:"))
        c.add(fila(Boton("↻  Reiniciar directamente a la BIOS", self.reboot_fw, kind="primary"),
                   Boton("Guardar esta guía en un archivo (para el móvil)", self.export, kind="soft"), None))
        c.add(Etiqueta("Mientras estás dentro de la BIOS no puedes mirar esta app: guarda el archivo y ábrelo en el móvil, "
                       "o hazle una foto al paso que toque.", "small"))
        return c

    def _status_card(self, g):
        fw = g["fw"]
        c = Tarjeta(tone="yellow", titulo="✔  Comprobaciones en tu equipo (ahora mismo)")

        def line(ok, text_ok, text_bad, text_unknown):
            if ok:
                tone, ico, txt = "green", "✓", text_ok
            elif ok is False:
                tone, ico, txt = "yellow", "✗", text_bad
            else:
                tone, ico, txt = "muted", "?", text_unknown
            ic = Etiqueta(ico, "h2", tone, wrap=False)
            ic.setFixedWidth(26)
            tx = Etiqueta(txt, None, None if ok else tone)
            h = QHBoxLayout()
            h.setSpacing(8)
            h.addWidget(ic, 0, Qt.AlignmentFlag.AlignTop)
            h.addWidget(tx, 1)
            c.lay.addLayout(h)

        line(fw["uefi"], "Windows arranca en modo UEFI (puedes desactivar CSM sin problema)",
             "Windows arranca en modo Legacy/MBR: NO desactives CSM o no arrancará", "No pude comprobar si usas UEFI o Legacy")
        line(fw["secure_boot"], "Secure Boot activado (necesario para Windows 11 y algunos anti-cheat)",
             "Secure Boot desactivado", "No pude leer el estado de Secure Boot")
        line(fw["rebar"], "Resizable BAR ACTIVADO en tu gráfica NVIDIA", "Resizable BAR desactivado (mira el punto correspondiente más abajo)",
             "No puedo comprobar Resizable BAR en esta gráfica (solo lo leo en NVIDIA)")
        return c

    def _ram_card(self, p):
        c = Tarjeta(tone="red", titulo="▥  Tiempos de RAM recomendados para tu equipo")
        for t in p["tiers"]:
            tone = TIER_TONE.get(t["level"], "accent")
            box = Tarjeta(soft=True, margen=12, espacio=6)
            head = QHBoxLayout()
            head.setSpacing(8)
            head.addWidget(Insignia(f"NIVEL {t['level']}", tone), 0, Qt.AlignmentFlag.AlignTop)
            head.addWidget(Etiqueta(t["name"], "h3", tone), 1)
            box.lay.addLayout(head)
            box.add(_kv(t["rows"]))
            c.add(box)
        c.add(Etiqueta("IMPORTANTE", "h3", "yellow"))
        for n in p["notes"]:
            c.add(Etiqueta("•  " + n))
        return c

    def _items(self, items):
        head = QHBoxLayout()
        head.addWidget(Etiqueta("Ajustes de BIOS para el máximo rendimiento", "h2"), 1)
        self.prog = Etiqueta("", "h3", "green", wrap=False)
        head.addWidget(self.prog, 0, Qt.AlignmentFlag.AlignRight)
        self.body_lay.addSpacing(6)
        self.body_lay.addLayout(head)
        self.cajas = {}
        area = None
        for it in items:
            if it["area"] != area:
                area = it["area"]
                self.body_lay.addWidget(Etiqueta(area.upper(), "small", "accent"))
            marcada = bool(self.checks.get(it["id"]))
            c = Tarjeta(tone="green" if marcada else "accent", margen=14, espacio=6)
            cb = Casilla(it["title"], marcada)
            cb.toggled.connect(lambda on, i=it["id"], card=c: self._toggle(i, card, on))
            self.cajas[it["id"]] = cb
            c.add(cb)
            tags = QHBoxLayout()
            tags.setSpacing(6)
            tags.addWidget(Insignia(*EFFECT.get(it["effect"], (str(it["effect"]).upper(), "muted"))))
            tags.addWidget(Insignia(*RISK.get(it["risk"], (str(it["risk"]).upper(), "muted"))))
            tags.addStretch(1)
            c.lay.addLayout(tags)
            g = QGridLayout()
            g.setHorizontalSpacing(12)
            g.setVerticalSpacing(4)
            g.setColumnStretch(1, 1)
            r = 0
            for k, label, role, tone in (("where", "DÓNDE", "mono", None), ("set_to", "PONER", "mono", None), ("why", "POR QUÉ", "small", None)):
                g.addWidget(Etiqueta(label, "small", wrap=False), r, 0, Qt.AlignmentFlag.AlignTop)
                g.addWidget(Etiqueta(it[k], role, tone), r, 1)
                r += 1
            if it["note"]:
                g.addWidget(Etiqueta("OJO", "small", "yellow", wrap=False), r, 0, Qt.AlignmentFlag.AlignTop)
                g.addWidget(Etiqueta(it["note"], "small", "yellow"), r, 1)
            g.setColumnMinimumWidth(0, 70)
            c.lay.addLayout(g)
            self.body_lay.addWidget(c)
        self._save()

    def _toggle(self, item_id, card, on):
        card.tono("green" if on else "accent")
        self._save()

    def _save(self):
        d = {k: bool(cb.isChecked()) for k, cb in self.cajas.items()}
        self.checks.update(d)
        bios.save_checks(self.checks)
        if self.cajas and self.prog is not None:
            self.prog.setText(f"{sum(d.values())} de {len(d)} hechos")

    # ------------------------------------------------------------------
    def reboot_fw(self):
        if not self.app.pregunta("Reiniciar a la BIOS",
                                 "Guarda tu trabajo y cierra los programas.\n\nEl PC se reiniciará en 10 segundos y entrará directo a la BIOS.\n\n¿Continuar?"):
            return
        ok, msg = bios.reboot_to_firmware()
        if not ok:
            self.app.aviso_modal("No se pudo", f"No pude reiniciar a la BIOS ({msg}).\nUsa la tecla {self.guide['enter_key'] if self.guide else 'Supr/F2'} al encender.")
        else:
            self.app.status("Reiniciando a la BIOS…" if not DEMO else msg)

    def export(self):
        if not self.guide:
            return
        try:
            p = bios.export_to_desktop(self.guide)
            self.app.info("Guía guardada", f"Guardada en:\n{p}\n\nÁbrela en tu móvil o imprímela para tenerla delante en la BIOS.")
        except OSError as e:
            self.app.aviso_modal("Error", f"No pude guardar el archivo: {e}")
