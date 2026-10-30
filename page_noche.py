"""Página «Modo noche»."""
import tkinter as tk

import noche
from widgets import (BG, CYAN, F, FG, GREEN, MUTED, PANEL, PANEL2, VIOLET, YELLOW, Card, NeonButton, WrapLabel, checkbox, page_title)


class NochePage(tk.Frame):
    def __init__(self, parent, app):
        super().__init__(parent, bg=BG)
        self.app = app
        wrap = tk.Frame(self, bg=BG)
        wrap.pack(fill="both", expand=True, padx=26, pady=(22, 10))
        page_title(wrap, "Modo noche", "Menos ruido y menos calor de madrugada. Al acabar el horario, todo vuelve a como estaba.", accent=VIOLET).pack(anchor="w", pady=(0, 12))

        c = Card(wrap, accent=VIOLET, title="Qué hace (y qué no)")
        c.pack(fill="x", pady=(0, 12))
        for t in ("Limita el máximo del procesador en tu plan de energía: menos calor, ventiladores más lentos. Es lo que más se nota.",
                  "En gráficas NVIDIA baja también el límite de potencia (necesita ejecutar HellOP como administrador).",
                  "No cambia tus ajustes de juego ni tu plan: guarda los valores de antes y los devuelve solos.",
                  "Solo funciona mientras HellOP está abierto (puede estar minimizado). Al cerrar HellOP se restaura todo.",
                  "Honesto: a menos potencia, menos FPS. Está pensado para jugar tranquilo o dejar el PC descargando de noche."):
            WrapLabel(c.body, text="•  " + t, fg=FG, font=F(10)).pack(fill="x", pady=2)

        self.cfg = noche.cargar()
        h = Card(wrap, accent=CYAN, title="Horario")
        h.pack(fill="x", pady=(0, 12))
        self.v_on = tk.BooleanVar(value=self.cfg["activo_horario"])
        checkbox(h.body, "Activar automáticamente en este horario", self.v_on).pack(anchor="w", pady=(0, 8))
        fila = tk.Frame(h.body, bg=PANEL)
        fila.pack(anchor="w")
        self.e_ini, self.e_fin = self._hora(fila, "Desde", self.cfg["ini"]), self._hora(fila, "Hasta", self.cfg["fin"])
        niv = tk.Frame(h.body, bg=PANEL)
        niv.pack(anchor="w", pady=(12, 0))
        tk.Label(niv, text="Intensidad", font=F(10, True), fg=MUTED, bg=PANEL).pack(side="left", padx=(0, 10))
        self.v_niv = tk.StringVar(value=self.cfg["nivel"])
        self.btns = {}
        for k, txt in (("suave", "Suave · 90 %"), ("medio", "Media · 80 %"), ("fuerte", "Fuerte · 70 %")):
            b = NeonButton(niv, txt, lambda k=k: self._nivel(k), color=CYAN, filled=(k == self.cfg["nivel"]), padx=12, pady=5, font=F(9, True))
            b.pack(side="left", padx=4)
            self.btns[k] = b

        self.msg = tk.Label(wrap, text="", font=F(10), fg=MUTED, bg=BG, anchor="w", justify="left", wraplength=760)
        self.msg.pack(fill="x", pady=(0, 8))
        fila = tk.Frame(wrap, bg=BG)
        fila.pack(anchor="w")
        NeonButton(fila, "Guardar horario", self.guarda, color=CYAN, filled=True, padx=18, pady=9).pack(side="left")
        NeonButton(fila, "Probar ahora", self.probar, color=YELLOW, padx=16, pady=9).pack(side="left", padx=10)
        NeonButton(fila, "Restaurar ya", self.restaura, color=GREEN, padx=16, pady=9).pack(side="left")

    def _hora(self, parent, texto, valor):
        tk.Label(parent, text=texto, font=F(10, True), fg=MUTED, bg=PANEL).pack(side="left", padx=(0, 6))
        e = tk.Entry(parent, width=6, font=F(11, True), bg=PANEL2, fg=FG, insertbackground=CYAN, relief="flat", justify="center")
        e.insert(0, valor)
        e.pack(side="left", padx=(0, 18), ipady=4)
        return e

    def _nivel(self, k):
        self.v_niv.set(k)
        for kk, b in self.btns.items():
            b.filled = kk == k
            b._draw() if hasattr(b, "_draw") else None

    def on_show(self):
        self.estado()

    def estado(self):
        d = noche.cargar()
        if d["aplicado"]:
            self.msg.config(text="● Modo noche ACTIVO ahora mismo.", fg=GREEN)
        elif d["activo_horario"]:
            self.msg.config(text=f"Programado de {d['ini']} a {d['fin']}. Ahora está apagado.", fg=MUTED)
        else:
            self.msg.config(text="Apagado.", fg=MUTED)

    def guarda(self):
        ini, fin = self.e_ini.get().strip(), self.e_fin.get().strip()
        if not (noche.hora_valida(ini) and noche.hora_valida(fin)):
            self.msg.config(text="Escribe las horas como 23:00 y 08:00.", fg=YELLOW)
            return
        d = noche.cargar()
        d.update({"activo_horario": bool(self.v_on.get()), "ini": ini, "fin": fin, "nivel": self.v_niv.get()})
        noche.guardar(d)
        self.app.toast("Horario guardado", GREEN)
        r = noche.revisa()
        if r:
            self.app.toast(r, CYAN)
        self.estado()

    def probar(self):
        txt, avisos = noche.aplicar(self.v_niv.get())
        self.msg.config(text="Probando: " + txt + ("  ·  " + avisos[0] if avisos else ""), fg=GREEN if not avisos else YELLOW)

    def restaura(self):
        ok = noche.restaurar()
        self.msg.config(text="Todo vuelve a como estaba." if ok else "No había nada que restaurar.", fg=GREEN)
