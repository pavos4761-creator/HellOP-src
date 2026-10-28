"""Página «Streaming»: prepara el PC y OBS para emitir en directo sin que el juego pierda FPS.
Usa el mismo asistente de Optimizar (cambio por cambio, con punto de restauración y deshacer), pero solo con lo de streaming."""
import tkinter as tk

import streaming
from page_optimize import OptimizePage
from util import DEMO, is_admin
from widgets import (CYAN, F, FG, GREEN, MUTED, PANEL, PINK, RED, YELLOW, Card, NeonButton, WrapLabel, checkbox)


class StreamingPage(OptimizePage):
    def heading(self, title, sub=None):
        from widgets import page_title
        page_title(self.stage, title, sub, accent=YELLOW).pack(anchor="w", pady=(0, 12))

    def show_intro(self):
        self.clear()
        self.heading("Streaming", "Emite en directo sin que tu juego pierda FPS. Yo no cambio nada sin preguntarte: verás cada ajuste y decides.")
        if not is_admin():
            c = Card(self.stage, accent=RED)
            c.pack(fill="x", pady=(0, 12))
            WrapLabel(c.body, fg=YELLOW, text="Estás sin permisos de administrador: el punto de restauración y algunos ajustes no se podrán aplicar. "
                                              "Usa «Reabrir como administrador» arriba a la derecha.").pack(fill="x")

        c = Card(self.stage, accent=YELLOW, title="Qué hace")
        c.pack(fill="x", pady=(0, 12))
        for t in ("Crea un perfil NUEVO en OBS Studio («HellOP Streaming») con el codificador de tu gráfica (NVENC, AMF o Quick Sync), "
                  "que casi no resta FPS al juego, a diferencia de codificar con la CPU. Tu perfil actual de OBS no se toca.",
                  "Elige resolución, FPS y bitrate acordes a tu pantalla y a tu codificador (los que recomiendan Twitch y YouTube).",
                  "Pone OBS (y Streamlabs, si lo tienes) en «Alto rendimiento» en la configuración de gráficos de Windows.",
                  "Añade los ajustes de Gaming que no molestan al directo y protege OBS/Discord para que nunca se cierren por error.",
                  "Todo se puede deshacer desde «Historial / Deshacer»; el perfil de OBS se borra solo si lo creó HellOP."):
            WrapLabel(c.body, text="•  " + t, fg=FG, font=F(10)).pack(fill="x", pady=2)

        self.det = Card(self.stage, accent=CYAN, title="Lo que he encontrado en tu PC")
        self.det.pack(fill="x", pady=(0, 12))
        self.det_lbl = tk.Label(self.det.body, text="Mirando OBS y tu gráfica…", font=F(10), fg=MUTED, bg=PANEL, anchor="w", justify="left")
        self.det_lbl.pack(fill="x")
        g = self.gen

        def detectar():
            obs, sl, names = streaming.find_obs(), streaming.find_streamlabs(), streaming.gpu_names()
            enc, nombre = streaming.pick_encoder(names)
            return obs, sl, names, nombre, streaming.plan(enc, streaming.pantalla())

        def listo(r):
            if g != self.gen or not self.det_lbl.winfo_exists():
                return
            obs, sl, names, nombre, (ow, oh, fps, kbps) = r
            lineas = [("OBS Studio: " + ("encontrado" if obs else "no lo encuentro (instálalo y vuelve; sin él solo se aplican los ajustes de Windows)"), GREEN if obs else YELLOW),
                      ("Streamlabs: " + ("encontrado" if sl else "no encontrado"), GREEN if sl else MUTED),
                      ("Gráfica: " + (", ".join(names) if names else "no la he podido leer"), FG),
                      (f"Codificador que usaré: {nombre}", FG),
                      (f"Calidad: {ow}×{oh} a {fps} FPS · {kbps} kbps", FG)]
            self.det_lbl.destroy()
            for t, col in lineas:
                tk.Label(self.det.body, text=t, font=F(10), fg=col, bg=PANEL, anchor="w").pack(fill="x", pady=1)

        self.app.bg(detectar, listo, lambda e: self.det_lbl.config(text=f"No pude mirar tu equipo: {e}", fg=RED))

        opts = Card(self.stage, accent=PINK, title="Antes de empezar")
        opts.pack(fill="x", pady=(0, 12))
        checkbox(opts.body, "Crear un punto de restauración de Windows (recomendado)", self.v_restore).pack(fill="x", pady=2)
        NeonButton(self.stage, "◉   PREPARAR MI PC PARA STREAMING", lambda: self.start("streaming"), color=YELLOW, filled=True,
                   font=F(12, True), padx=26, pady=10).pack(anchor="w", pady=(4, 10))
