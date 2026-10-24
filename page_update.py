"""Página «Actualizaciones»: buscar, ver novedades y actualizar con un clic."""
import tkinter as tk
import webbrowser
from tkinter import messagebox, ttk

import updater
import version
from util import DEMO
from widgets import BORDER
from widgets import (BG, CYAN, F, FG, GREEN, MUTED, PANEL, PANEL2, PINK, RED, VIOLET, YELLOW, Card, NeonButton,
                     ScrollFrame, WrapLabel, page_title)


class UpdatePage(tk.Frame):
    def __init__(self, parent, app):
        super().__init__(parent, bg=BG)
        self.app = app
        self.info = None
        self.busy = False
        top = tk.Frame(self, bg=BG)
        top.pack(fill="x", padx=26, pady=(22, 6))
        page_title(top, "Actualizaciones", "Pulsa un botón y la app se actualiza sola. No hace falta que te envíen ningún archivo.",
                   accent=GREEN).pack(anchor="w")
        self.scroll = ScrollFrame(self)
        self.scroll.pack(fill="both", expand=True, padx=(26, 10), pady=(8, 10))
        self.build(self.scroll.inner)

    # ------------------------------------------------------------------
    def build(self, root):
        c = Card(root, accent=GREEN, title="⟳  Versión", pad=16)
        c.pack(fill="x", pady=(0, 12))
        row = tk.Frame(c.body, bg=PANEL)
        row.pack(fill="x")
        tk.Label(row, text=f"v{version.__version__}", font=F(26, True), fg=GREEN, bg=PANEL).pack(side="left")
        info = tk.Frame(row, bg=PANEL)
        info.pack(side="left", padx=18)
        tk.Label(info, text="Versión instalada", font=F(10, True), fg=FG, bg=PANEL, anchor="w").pack(fill="x")
        tk.Label(info, text=f"Se ejecuta como: {updater.mode()}", font=F(9), fg=MUTED, bg=PANEL, anchor="w").pack(fill="x")
        btns = tk.Frame(c.body, bg=PANEL)
        btns.pack(fill="x", pady=(14, 0))
        self.b_check = NeonButton(btns, "↻  BUSCAR ACTUALIZACIONES", self.check, color=CYAN, filled=True, font=F(12, True), padx=24, pady=10)
        self.b_check.pack(side="left")
        self.b_update = NeonButton(btns, "⬇  ACTUALIZAR AHORA", self.update, color=GREEN, filled=True, font=F(12, True), padx=24, pady=10)
        self.b_update.pack(side="left", padx=10)
        self.b_update.set_enabled(False)
        self.msg = tk.Label(c.body, text="", font=F(11, True), fg=MUTED, bg=PANEL, anchor="w", justify="left", wraplength=760)
        self.msg.pack(fill="x", pady=(12, 0))
        self.pb = ttk.Progressbar(c.body, style="Green.Horizontal.TProgressbar", mode="determinate", maximum=100)

        self.notes_card = Card(root, accent=PINK, title="✦  Novedades de la versión")
        self.notes = tk.Label(self.notes_card.body, text="", font=F(10), fg=FG, bg=PANEL, anchor="w", justify="left", wraplength=760)
        self.notes.pack(fill="x")

        r = Card(root, accent=VIOLET, title="⚙  Dónde se publican las versiones")
        r.pack(fill="x", pady=(0, 12))
        WrapLabel(r.body, fg=MUTED, font=F(9),
                  text="Es el repositorio de GitHub donde se suben las versiones nuevas, con el formato usuario/nombre "
                       "(por ejemplo: mi-usuario/pc-optimizer). Solo hay que ponerlo una vez. Debe ser público.").pack(fill="x", pady=(0, 8))
        line = tk.Frame(r.body, bg=PANEL)
        line.pack(fill="x")
        self.var_repo = tk.StringVar(value=updater.get_repo())
        e = tk.Entry(line, textvariable=self.var_repo, font=("Consolas", 11), bg=PANEL2, fg=FG, insertbackground=FG, relief="flat",
                     highlightthickness=1, highlightbackground=BORDER, highlightcolor=VIOLET, width=34)
        e.pack(side="left", ipady=6, padx=(0, 10))
        NeonButton(line, "Guardar", self.save_repo, color=VIOLET, filled=True, padx=16, pady=7, font=F(10, True)).pack(side="left")
        self.repo_msg = tk.Label(r.body, text="", font=F(9), fg=MUTED, bg=PANEL, anchor="w")
        self.repo_msg.pack(fill="x", pady=(6, 0))

        s = Card(root, accent=YELLOW, title="⚠  Cómo funciona y qué tener en cuenta")
        s.pack(fill="x", pady=(0, 14))
        for t in ("Solo descarga archivos de GitHub y comprueba su huella SHA256 antes de instalar. Si no coincide, no instala nada.",
                  "Tus datos (historial, ajustes, pruebas) están en %APPDATA%\\HellOP y NO se tocan al actualizar.",
                  "En modo .exe se guarda una copia de la versión anterior (.exe.bak). En modo Python, en %APPDATA%\\HellOP\\copia_<versión>.",
                  "Tras actualizar, la app se cierra y se vuelve a abrir sola. Windows puede volver a pedirte permisos de administrador."):
            WrapLabel(s.body, text="•  " + t, font=F(9), fg=MUTED).pack(fill="x", pady=1)

    # ------------------------------------------------------------------
    def set_msg(self, text, color=MUTED):
        self.msg.config(text=text, fg=color)

    def save_repo(self):
        try:
            r = updater.set_repo(self.var_repo.get())
        except updater.UpdateError as e:
            self.repo_msg.config(text=str(e), fg=RED)
            return
        self.var_repo.set(r)
        self.repo_msg.config(text="✓ Guardado. Ahora pulsa «Buscar actualizaciones»." if r else "Repositorio borrado.", fg=GREEN)

    def check(self, silent=False):
        if self.busy:
            return
        self.busy = True
        self.b_check.set_enabled(False)
        self.b_update.set_enabled(False)
        self.set_msg("Buscando actualizaciones…", CYAN)
        self.app.bg(updater.check, self.checked, self.check_failed)

    def check_failed(self, e):
        self.busy = False
        self.b_check.set_enabled(True)
        self.set_msg(str(e) if isinstance(e, updater.UpdateError) else f"Error inesperado: {e}", RED)

    def checked(self, info):
        self.busy = False
        self.info = info
        self.b_check.set_enabled(True)
        self.notes_card.pack_forget()
        if info["newer"]:
            self.set_msg(f"✨ Hay una versión nueva: v{info['latest']}  (tienes la v{info['current']})"
                         + (f"  ·  publicada el {info['published']}" if info.get("published") else ""), GREEN)
            self.b_update.set_enabled(True)
            self.notes.config(text=info["notes"])
            self.notes_card.pack(fill="x", pady=(0, 12), after=self.scroll.inner.winfo_children()[0])
            self.app.mark_update_available(info["latest"])
        else:
            self.set_msg(f"✓ Estás al día: v{info['current']} es la última versión.", GREEN)

    # ------------------------------------------------------------------
    def update(self):
        if self.busy or not self.info or not self.info["newer"]:
            return
        if not DEMO and not messagebox.askyesno(
                "Actualizar", f"Se va a actualizar a la v{self.info['latest']}.\n\nLa app se cerrará y se volverá a abrir sola.\n"
                "Si tienes el Modo Extremo activo, se desactivará antes.\n\n¿Continuar?"):
            return
        self.busy = True
        self.b_check.set_enabled(False)
        self.b_update.set_enabled(False)
        self.pb["value"] = 0
        self.pb.pack(fill="x", pady=(8, 0))
        self.app.bg(lambda: updater.actualizar(self.info, lambda p, m: self.app.ui(self._prog, p, m)),
                    self.updated, self.update_failed)

    def _prog(self, pct, msg):
        self.pb["value"] = pct
        self.set_msg(msg, CYAN)

    def update_failed(self, e):
        self.busy = False
        self.pb.pack_forget()
        self.b_check.set_enabled(True)
        self.b_update.set_enabled(True)
        self.set_msg("✗ " + (str(e) if isinstance(e, updater.UpdateError) else f"Error inesperado: {e}"), RED)

    def updated(self, result):
        self.busy = False
        self.pb.pack_forget()
        if result == "demo":
            self.set_msg("✓ (Demo) En la app real aquí se reiniciaría con la versión nueva.", GREEN)
            self.b_check.set_enabled(True)
            return
        self.set_msg("✓ Actualización instalada. Reiniciando la app…", GREEN)
        self.after(1200, self._restart)

    def _restart(self):
        updater.restart_app()
        self.app.on_close()
