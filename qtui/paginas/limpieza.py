"""Pantalla «Limpieza»: temporales, cachés, papelera, duplicados."""
import time

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QHBoxLayout, QVBoxLayout, QWidget

import cleanup
from util import fmt_bytes

from ..widgets import Pagina, Tarjeta, Etiqueta, Boton, Casilla, Barra, vacia


def _contenedor():
    """Widget transparente con un QVBoxLayout sin márgenes."""
    w = QWidget()
    v = QVBoxLayout(w)
    v.setContentsMargins(0, 0, 0, 0)
    v.setSpacing(6)
    return w, v


class Limpieza(Pagina):
    titulo_texto = "Limpieza"
    sub_texto = "Libera espacio y quita lo que ralentiza. Primero escaneo y tú eliges qué borrar."

    def __init__(self, app):
        super().__init__(app)
        self.items = []
        self.vars = {}          # id -> Casilla
        self.dups = []
        self.dup_vars = {}      # (grupo, archivo) -> Casilla
        self.busy = False
        self.scanned = False
        self._resultado = ""

        # ---- tarjeta 1: temporales y cachés
        self.card1 = Tarjeta(tone="teal", titulo="Archivos temporales y cachés")
        self.add(self.card1)
        self.list_box, self.list_lay = _contenedor()
        self.card1.add(self.list_box)

        barra = QHBoxLayout()
        barra.setSpacing(10)
        self.b_scan = Boton("Escanear de nuevo", self.scan, kind="soft")
        self.b_clean = Boton("✦  LIMPIAR SELECCIONADO", self.clean, kind="primary", tone="green")
        self.total = Etiqueta("", "h3", "green", wrap=False)
        barra.addWidget(self.b_scan)
        barra.addWidget(self.b_clean)
        barra.addWidget(self.total)
        barra.addStretch(1)
        self.card1.lay.addLayout(barra)

        self.pb = Barra(0, "green")
        self.pb.setVisible(False)
        self.card1.add(self.pb)
        self.msg = Etiqueta("", "muted")
        self.card1.add(self.msg)
        self.extra, self.extra_lay = _contenedor()
        self.card1.add(self.extra)

        # ---- tarjeta 2: duplicados
        self.card2 = Tarjeta(tone="accent", titulo="Archivos duplicados")
        self.add(self.card2)
        self.card2.add(Etiqueta(
            "Busca copias idénticas en Descargas, Documentos, Escritorio, Imágenes, Vídeos y Música. "
            "Los que elijas van a la Papelera (se pueden recuperar). Siempre se conserva una copia.", "muted"))
        fb = QHBoxLayout()
        self.b_dup = Boton("Buscar duplicados", self.find_dups, kind="soft")
        fb.addWidget(self.b_dup)
        fb.addStretch(1)
        self.card2.lay.addLayout(fb)
        self.dup_msg = Etiqueta("", "muted")
        self.card2.add(self.dup_msg)
        self.dup_box, self.dup_lay = _contenedor()
        self.card2.add(self.dup_box)

    def al_mostrar(self):
        if not self.scanned and not self.busy:
            self.scan()

    # ---- escaneo ---------------------------------------------------------------------
    def _msg(self, texto, tone="muted"):
        self.msg.setText(texto)
        self.msg.tono(tone)

    def _dup_msg(self, texto, tone="muted"):
        self.dup_msg.setText(texto)
        self.dup_msg.tono(tone)

    def scan(self):
        if self.busy:
            return
        self.busy = True
        self.b_scan.set_enabled(False)
        self.b_clean.set_enabled(False)
        self._msg("Escaneando…", "teal")
        self.app.status("Escaneando archivos basura…")

        def work():
            items = cleanup.build_items()
            for it in items:
                it.scan()
            return items
        self.app.bg(work, self.scan_done, self.scan_fail)

    def scan_fail(self, e):
        self.busy = False
        self.pb.setVisible(False)
        self.b_scan.set_enabled(True)
        self.b_clean.set_enabled(True)
        self._msg(f"Error al escanear: {e}", "red")

    def scan_done(self, items):
        self.busy = False
        self.scanned = True
        self.items = items
        self.b_scan.set_enabled(True)
        self.b_clean.set_enabled(True)
        vacia(self.list_lay)
        self.vars = {}
        for it in items:
            ok = it.available()
            cb = Casilla("", bool(ok and it.default and it.size > 0))
            cb.setEnabled(bool(ok))
            cb.toggled.connect(lambda _=False: self.update_total())
            self.vars[it.id] = cb

            fila_w = QWidget()
            h = QHBoxLayout(fila_w)
            h.setContentsMargins(0, 3, 0, 3)
            h.setSpacing(8)
            h.addWidget(cb, 0, Qt.AlignmentFlag.AlignTop)
            col = QVBoxLayout()
            col.setSpacing(2)
            col.addWidget(Etiqueta(it.title, "h3", None if ok else "muted"))
            d = it.desc + (f"  ·  {it.warn}" if it.warn else "") + ("" if ok else "  ·  (necesita administrador)")
            col.addWidget(Etiqueta(d, "small", "muted"))
            h.addLayout(col, 1)
            grande = it.size > 200 * 1024 ** 2
            tam = Etiqueta(fmt_bytes(it.size), "h3", "yellow" if grande else None, wrap=False)
            tam.setMinimumWidth(80)
            tam.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignTop)
            h.addWidget(tam, 0, Qt.AlignmentFlag.AlignTop)
            self.list_lay.addWidget(fila_w)

        vacia(self.extra_lay)
        if cleanup.windows_old_size_hint():
            f = QWidget()
            h = QHBoxLayout(f)
            h.setContentsMargins(0, 10, 0, 0)
            h.setSpacing(10)
            h.addWidget(Etiqueta("Hay una carpeta Windows.old (restos de una versión anterior de Windows) que puede ocupar "
                                 "muchos GB. Se borra con la herramienta oficial de Windows:", None, "yellow"), 1)
            h.addWidget(Boton("Abrir Liberador de espacio", cleanup.open_disk_cleanup, kind="soft", tone="yellow"))
            self.extra_lay.addWidget(f)
        self.update_total()
        if self._resultado:
            self._msg(self._resultado + "  ·  Escaneo actualizado.", "green")
            self._resultado = ""
        else:
            self._msg("Escaneo completado. Marca lo que quieras limpiar.", "muted")
        self.app.status("Escaneo completado")

    def update_total(self):
        sel = sum(it.size for it in self.items if self.vars.get(it.id) is not None and self.vars[it.id].isChecked())
        self.total.setText(f"Se liberarán ≈ {fmt_bytes(sel)}")

    # ---- limpieza --------------------------------------------------------------------
    def clean(self):
        if self.busy:
            return
        chosen = [it for it in self.items if self.vars.get(it.id) is not None and self.vars[it.id].isChecked()]
        if not chosen:
            self.app.info("Limpieza", "No hay nada seleccionado.")
            return
        size = sum(it.size for it in chosen)
        if not self.app.pregunta("Confirmar limpieza", f"Se van a borrar {len(chosen)} categorías (≈ {fmt_bytes(size)}).\n"
                                 "Son archivos que se pueden regenerar. Esta acción no se puede deshacer.\n\n¿Continuar?"):
            return
        self.busy = True
        self.b_scan.set_enabled(False)
        self.b_clean.set_enabled(False)
        self.pb.pon(0)
        self.pb.setVisible(True)

        def work():
            freed = failed = 0
            for i, it in enumerate(chosen):
                self.app.ui(self._clean_prog, int(i / len(chosen) * 100), f"Limpiando: {it.title}…")
                f, x = it.clean()
                freed += f
                failed += x
            return freed, failed
        self.app.bg(work, self.clean_done, self.scan_fail)

    def _clean_prog(self, pct, texto):
        self.pb.pon(pct)
        self._msg(texto, "teal")

    def clean_done(self, res):
        freed, failed = res
        self.pb.pon(100)
        self.pb.setVisible(False)
        self.busy = False
        extra = f" ({failed} archivos estaban en uso y se omitieron)" if failed else ""
        self._msg(f"✓ Liberados {fmt_bytes(freed)}{extra}", "green")
        self.app.status(f"Limpieza completada: {fmt_bytes(freed)} liberados")
        self._resultado = f"✓ Liberados {fmt_bytes(freed)}{extra}"
        self.scan()
        # scan() reemplaza el mensaje; lo restituimos para que el resultado siga visible
        self._msg(self._resultado, "green")

    # ---- duplicados ------------------------------------------------------------------
    def find_dups(self):
        if self.busy:
            return
        self.busy = True
        self.b_dup.set_enabled(False)
        self._dup_msg("Buscando… puede tardar varios minutos si tienes muchos archivos.", "teal")
        roots = cleanup.default_scan_roots()
        self.app.bg(lambda: cleanup.find_duplicates(roots, progress=lambda m: self.app.ui(self._dup_msg, m, "teal")),
                    self.dups_done, self.dups_fail)

    def dups_fail(self, e):
        self.busy = False
        self.b_dup.set_enabled(True)
        self._dup_msg(f"Error: {e}", "red")

    def dups_done(self, groups):
        self.busy = False
        self.b_dup.set_enabled(True)
        self.dups = groups
        vacia(self.dup_lay)
        self.dup_vars = {}
        if not groups:
            self._dup_msg("No encontré archivos duplicados grandes ✓", "green")
            return
        waste = sum(g["size"] * (len(g["files"]) - 1) for g in groups)
        self._dup_msg(f"{len(groups)} grupos de duplicados · {fmt_bytes(waste)} recuperables. "
                      "Marcado = irá a la Papelera (se conserva siempre el más antiguo).", "yellow")
        for gi, g in enumerate(groups[:60]):
            t = Tarjeta(soft=True, margen=10, espacio=4)
            t.add(Etiqueta(f"{fmt_bytes(g['size'])} × {len(g['files'])} copias", "h3", "accent"))
            for fi, (path, mtime) in enumerate(g["files"]):
                cb = Casilla("", fi > 0)
                self.dup_vars[(gi, fi)] = cb
                texto = f"{path}   ·   {time.strftime('%d/%m/%Y', time.localtime(mtime))}" + ("   ← se conserva" if fi == 0 else "")
                f = QWidget()
                h = QHBoxLayout(f)
                h.setContentsMargins(0, 0, 0, 0)
                h.setSpacing(6)
                h.addWidget(cb, 0, Qt.AlignmentFlag.AlignTop)
                h.addWidget(Etiqueta(texto, "mono"), 1)
                t.add(f)
            self.dup_lay.addWidget(t)
        barra = QWidget()
        hb = QHBoxLayout(barra)
        hb.setContentsMargins(0, 8, 0, 0)
        hb.addWidget(Boton("Enviar marcados a la Papelera", self.trash_dups, kind="primary"))
        hb.addStretch(1)
        self.dup_lay.addWidget(barra)

    def trash_dups(self):
        paths = []
        for gi, g in enumerate(self.dups[:60]):
            marked = [g["files"][fi][0] for fi in range(len(g["files"]))
                      if self.dup_vars.get((gi, fi)) is not None and self.dup_vars[(gi, fi)].isChecked()]
            if len(marked) >= len(g["files"]):          # protección: nunca borrar todas las copias
                marked = marked[1:]
            paths += marked
        if not paths:
            self.app.info("Duplicados", "No hay nada marcado.")
            return
        if not self.app.pregunta("Enviar a la Papelera", f"Se enviarán {len(paths)} archivos a la Papelera de reciclaje.\n"
                                 "Podrás recuperarlos desde allí.\n\n¿Continuar?"):
            return
        self.b_dup.set_enabled(False)
        self.app.bg(lambda: cleanup.send_to_recycle_bin(paths), self.trash_done, self.dups_fail)

    def trash_done(self, res):
        ok, fail = res
        self.b_dup.set_enabled(True)
        self._dup_msg(f"✓ {ok} archivos enviados a la Papelera" + (f" · {fail} no se pudieron mover" if fail else ""), "green")
        vacia(self.dup_lay)
        self.dup_vars = {}
