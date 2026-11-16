"""Pantalla «Actualizaciones»: buscar, ver novedades y actualizar con un clic."""
from PySide6.QtWidgets import QLineEdit

import updater
import version
from util import DEMO

from ..widgets import Barra, Boton, Etiqueta, Pagina, Tarjeta, columna, fila


class Actualizar(Pagina):
    titulo_texto = "Actualizaciones"
    sub_texto = "Pulsa un botón y la app se actualiza sola. No hace falta que te envíen ningún archivo."

    def __init__(self, app):
        super().__init__(app)
        self.info = None
        self.busy = False

        # ---- versión
        c = Tarjeta(tone="green", titulo="⟳  Versión")
        self.add(c)
        self.lbl_ver = Etiqueta(f"v{version.__version__}", "big", "green", wrap=False)
        txt = Etiqueta("Versión instalada", "h3")
        modo = Etiqueta(f"Se ejecuta como: {updater.mode()}", "muted")
        c.add(fila(self.lbl_ver, columna(txt, modo, espacio=2), None, espacio=18))
        self.b_check = Boton("↻  BUSCAR ACTUALIZACIONES", self.check, kind="primary")
        self.b_update = Boton("⬇  ACTUALIZAR AHORA", self.update, kind="primary", tone="green")
        self.b_update.set_enabled(False)
        c.add(fila(self.b_check, self.b_update, None, espacio=10))
        self.msg = Etiqueta("", "h3", "muted")
        c.add(self.msg)
        self.pb = Barra(0, "green")
        self.pb.setVisible(False)
        c.add(self.pb)

        # ---- novedades (oculta hasta que haya versión nueva)
        self.notes_card = Tarjeta(tone="teal", titulo="✦  Novedades de la versión")
        self.notes = Etiqueta("")
        self.notes_card.add(self.notes)
        self.notes_card.setVisible(False)
        self.add(self.notes_card)

        # ---- repositorio
        r = Tarjeta(tone="accent", titulo="⚙  Dónde se publican las versiones")
        self.add(r)
        r.add(Etiqueta("Es el repositorio de GitHub donde se suben las versiones nuevas, con el formato usuario/nombre "
                       "(por ejemplo: mi-usuario/pc-optimizer). Solo hay que ponerlo una vez. Debe ser público.", "muted"))
        self.var_repo = QLineEdit(updater.get_repo())
        self.var_repo.setMinimumWidth(320)
        self.var_repo.returnPressed.connect(self.save_repo)
        r.add(fila(self.var_repo, Boton("Guardar", self.save_repo, kind="primary"), None, espacio=10))
        self.repo_msg = Etiqueta("", "small", "muted")
        r.add(self.repo_msg)

        # ---- aviso
        s = Tarjeta(tone="yellow", titulo="⚠  Cómo funciona y qué tener en cuenta")
        self.add(s)
        for t in ("Solo descarga archivos de GitHub y comprueba su huella SHA256 antes de instalar. Si no coincide, no instala nada.",
                  "Tus datos (historial, ajustes, pruebas) están en %APPDATA%\\HellOP y NO se tocan al actualizar.",
                  "En modo .exe se guarda una copia de la versión anterior (.exe.bak). En modo Python, en %APPDATA%\\HellOP\\copia_<versión>.",
                  "Tras actualizar, la app se cierra y se vuelve a abrir sola. Windows puede volver a pedirte permisos de administrador."):
            s.add(Etiqueta("•  " + t, "muted"))

    # ------------------------------------------------------------------
    def set_msg(self, text, tone="muted"):
        self.msg.setText(text)
        self.msg.tono(tone)

    def save_repo(self):
        try:
            r = updater.set_repo(self.var_repo.text())
        except updater.UpdateError as e:
            self.repo_msg.setText(str(e))
            self.repo_msg.tono("red")
            return
        self.var_repo.setText(r)
        self.repo_msg.setText("✓ Guardado. Ahora pulsa «Buscar actualizaciones»." if r else "Repositorio borrado.")
        self.repo_msg.tono("green")

    def check(self, silent=False):
        if self.busy:
            return
        self.busy = True
        self.b_check.set_enabled(False)
        self.b_update.set_enabled(False)
        self.set_msg("Buscando actualizaciones…", "accent")
        self.app.bg(updater.check, self.checked, self.check_failed)

    def check_failed(self, e):
        self.busy = False
        self.b_check.set_enabled(True)
        self.set_msg(str(e) if isinstance(e, updater.UpdateError) else f"Error inesperado: {e}", "red")

    def recibe(self, info):
        """La ventana lo llama cuando el comprobador automático halla una versión nueva."""
        self.checked(info)

    def checked(self, info):
        self.busy = False
        self.info = info
        self.b_check.set_enabled(True)
        self.notes_card.setVisible(False)
        if info["newer"]:
            self.set_msg(f"✨ Hay una versión nueva: v{info['latest']}  (tienes la v{info['current']})"
                         + (f"  ·  publicada el {info['published']}" if info.get("published") else ""), "green")
            self.b_update.set_enabled(True)
            self.notes.setText(info["notes"])
            self.notes_card.setVisible(True)
            self.app.mark_update_available(info["latest"])
        else:
            self.set_msg(f"✓ Estás al día: v{info['current']} es la última versión.", "green")

    # ------------------------------------------------------------------
    def update(self):
        if self.busy or not self.info or not self.info["newer"]:
            return
        if not DEMO and not self.app.pregunta(
                "Actualizar", f"Se va a actualizar a la v{self.info['latest']}.\n\nLa app se cerrará y se volverá a abrir sola.\n"
                "Si tienes el Modo Extremo activo, se desactivará antes.\n\n¿Continuar?"):
            return
        self.busy = True
        self.b_check.set_enabled(False)
        self.b_update.set_enabled(False)
        self.pb.pon(0)
        self.pb.setVisible(True)
        info = self.info
        self.app.bg(lambda: updater.actualizar(info, lambda p, m: self.app.ui(self._prog, p, m)),
                    self.updated, self.update_failed)

    def _prog(self, pct, msg):
        self.pb.pon(pct)
        self.set_msg(msg, "accent")

    def update_failed(self, e):
        self.busy = False
        self.pb.setVisible(False)
        self.b_check.set_enabled(True)
        self.b_update.set_enabled(True)
        self.set_msg("✗ " + (str(e) if isinstance(e, updater.UpdateError) else f"Error inesperado: {e}"), "red")

    def updated(self, result):
        self.busy = False
        self.pb.setVisible(False)
        if result == "demo":
            self.set_msg("✓ (Demo) En la app real aquí se reiniciaría con la versión nueva.", "green")
            self.b_check.set_enabled(True)
            return
        self.set_msg("✓ Actualización instalada. Reiniciando la app…", "green")
        self.app.after(1200, self._restart)

    def _restart(self):
        updater.restart_app()
        self.app.close()
