"""Pantalla que sustituye a una página PRO cuando no hay clave activa."""
import tkinter as tk

import licencia as lic
from widgets import BG, F, FG, MUTED, YELLOW, NeonButton, badge


class LockedPage(tk.Frame):
    def __init__(self, parent, app):
        super().__init__(parent, bg=BG)
        self.app = app
        box = tk.Frame(self, bg=BG)
        box.place(relx=0.5, rely=0.42, anchor="center")
        badge(box, "FUNCIÓN PRO", YELLOW).pack()
        self.title = tk.Label(box, text="", font=F(22, True), fg=FG, bg=BG)
        self.title.pack(pady=(14, 4))
        self.msg = tk.Label(box, text="", font=F(11), fg=MUTED, bg=BG, justify="center", wraplength=520)
        self.msg.pack(pady=(0, 18))
        row = tk.Frame(box, bg=BG)
        row.pack()
        NeonButton(row, "Activar mi clave", lambda: app.show("license"), color=YELLOW, filled=True, font=F(12, True), padx=26, pady=10).pack(side="left")
        NeonButton(row, "Volver al inicio", lambda: app.show("home"), color=MUTED, font=F(11, True), padx=22, pady=10).pack(side="left", padx=10)

    def set(self, name):
        st = lic.status()
        self.title.config(text=name)
        extra = {"expired": st["msg"] + " Pide una clave nueva a quien te dio la anterior.",
                 "invalid": st["msg"]}.get(st["level"], "Esta función es de la versión PRO. Necesitas una clave de activación.")
        self.msg.config(text=extra)
