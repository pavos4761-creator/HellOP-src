"""Página «Mando»: quita tirones y retraso evitable al jugar con mando. Usa el asistente de Optimizar (cambio por cambio, con deshacer)."""
import tkinter as tk

import mando
from page_optimize import OptimizePage
from util import is_admin
from widgets import CYAN, F, FG, GREEN, MUTED, PANEL, PINK, RED, YELLOW, Card, NeonButton, WrapLabel, checkbox


class MandoPage(OptimizePage):
    def heading(self, title, sub=None):
        from widgets import page_title
        page_title(self.stage, title, sub, accent=PINK).pack(anchor="w", pady=(0, 12))

    def show_intro(self):
        self.clear()
        self.heading("Mando", "Menos tirones y menos retraso al jugar con mando. Yo no cambio nada sin preguntarte: verás cada ajuste y decides.")
        if not is_admin():
            c = Card(self.stage, accent=RED)
            c.pack(fill="x", pady=(0, 12))
            WrapLabel(c.body, fg=YELLOW, text="Estás sin permisos de administrador: varios ajustes no se podrán aplicar. "
                                              "Usa «Reabrir como administrador» arriba a la derecha.").pack(fill="x")

        c = Card(self.stage, accent=PINK, title="Qué hace (y qué no)")
        c.pack(fill="x", pady=(0, 12))
        for t in ("Evita que Windows apague los puertos USB, el Bluetooth y el propio mando para ahorrar energía: es la causa típica de que un mando "
                  "«se duerma» y tarde en responder.",
                  "Hace que el botón Xbox no abra la Game Bar a mitad de partida y apaga la captura en segundo plano de Windows.",
                  "Hace que el temporizador rápido de Windows 11 valga para todos los programas (lecturas del mando más regulares).",
                  "Te da los consejos que sí cambian el retraso (cable, FPS, Reflex…).",
                  "Sé claro: retraso 0 no existe. Esto quita tirones y capas de más; no hace magia. Todo se deshace desde «Historial / Deshacer»."):
            WrapLabel(c.body, text="•  " + t, fg=FG, font=F(10)).pack(fill="x", pady=2)

        self.det = Card(self.stage, accent=CYAN, title="Mandos que he encontrado")
        self.det.pack(fill="x", pady=(0, 12))
        self.det_lbl = tk.Label(self.det.body, text="Buscando mandos conectados…", font=F(10), fg=MUTED, bg=PANEL, anchor="w", justify="left")
        self.det_lbl.pack(fill="x")
        g = self.gen

        def listo(lista):
            if g != self.gen or not self.det_lbl.winfo_exists():
                return
            self.det_lbl.destroy()
            if not lista:
                tk.Label(self.det.body, text="No veo ningún mando conectado ahora. Conéctalo y vuelve a entrar si quieres que lo compruebe; los ajustes valen igual.",
                         font=F(10), fg=YELLOW, bg=PANEL, anchor="w", justify="left", wraplength=700).pack(fill="x")
                return
            txt = {"cable": ("por cable", GREEN), "bluetooth": ("por Bluetooth", YELLOW), "receptor": ("con receptor", FG)}
            for n, con in lista:
                t, col = txt.get(con, (con, FG))
                tk.Label(self.det.body, text=f"{n}  ·  {t}", font=F(10), fg=col, bg=PANEL, anchor="w").pack(fill="x", pady=1)
            if any(c == "bluetooth" for _n, c in lista):
                tk.Label(self.det.body, text="Consejo: por cable tendrás menos retraso y menos saltos que por Bluetooth.", font=F(9), fg=MUTED,
                         bg=PANEL, anchor="w").pack(fill="x", pady=(6, 0))

        self.app.bg(mando.mandos, listo, lambda e: self.det_lbl.config(text=f"No pude mirar tus mandos: {e}", fg=RED))

        opts = Card(self.stage, accent=PINK, title="Antes de empezar")
        opts.pack(fill="x", pady=(0, 12))
        checkbox(opts.body, "Crear un punto de restauración de Windows (recomendado)", self.v_restore).pack(fill="x", pady=2)
        NeonButton(self.stage, "◈   OPTIMIZAR MI PC PARA MANDO", lambda: self.start("mando"), color=PINK, filled=True,
                   font=F(12, True), padx=26, pady=10).pack(anchor="w", pady=(4, 10))
