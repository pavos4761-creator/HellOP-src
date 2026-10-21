"""Página «BIOS»: qué cambiar en la BIOS para el máximo rendimiento + tiempos de RAM."""
import tkinter as tk
from tkinter import messagebox, ttk

import bios
from util import DEMO
from widgets import (BG, CYAN, F, FG, GREEN, MUTED, PANEL, PANEL2, PINK, RED, VIOLET, YELLOW, Card, NeonButton,
                     ScrollFrame, WrapLabel, badge, checkbox, kv_rows, page_title)

EFFECT = {"real": ("EFECTO REAL", GREEN), "pequeño": ("EFECTO PEQUEÑO", YELLOW), "depende": ("DEPENDE DE TU EQUIPO", CYAN),
          "mínimo": ("EFECTO CASI NULO", MUTED)}
RISK = {"bajo": ("RIESGO BAJO", GREEN), "medio": ("RIESGO MEDIO", YELLOW), "alto": ("RIESGO ALTO", RED)}
TIER_COLOR = {1: GREEN, 2: YELLOW, 3: RED}


class BiosPage(tk.Frame):
    def __init__(self, parent, app):
        super().__init__(parent, bg=BG)
        self.app = app
        self.guide = None
        self.checks = bios.load_checks()
        self.vars = {}
        top = tk.Frame(self, bg=BG)
        top.pack(fill="x", padx=26, pady=(22, 6))
        page_title(top, "BIOS · máximo rendimiento",
                   "Lo que NO se puede cambiar desde Windows (tiempos de RAM, CPU, placa), explicado paso a paso para TU equipo.",
                   accent=VIOLET).pack(anchor="w")
        row = tk.Frame(top, bg=BG)
        row.pack(fill="x", pady=(14, 4))
        self.btn = NeonButton(row, "◉   GENERAR MI GUÍA DE BIOS", self.run, color=VIOLET, filled=True, font=F(14, True), padx=34, pady=12)
        self.btn.pack(side="left")
        self.msg = tk.Label(row, text="", font=F(10), fg=MUTED, bg=BG)
        self.msg.pack(side="left", padx=16)
        self.pb = ttk.Progressbar(top, style="Neon.Horizontal.TProgressbar", mode="indeterminate", length=320)
        self.scroll = ScrollFrame(self)
        self.scroll.pack(fill="both", expand=True, padx=(26, 10), pady=(8, 10))
        intro = Card(self.scroll.inner, accent=VIOLET)
        intro.pack(fill="x")
        WrapLabel(intro.body, fg=MUTED,
                  text="Pulsa el botón y leo tu procesador, placa, RAM y gráfica para darte: (1) los tiempos de RAM recomendados por niveles, "
                       "(2) una lista de ajustes de BIOS con la ruta de menú de TU placa, y (3) un botón para reiniciar directo a la BIOS. "
                       "Puedes guardar la guía en un archivo para mirarla en el móvil mientras estás dentro de la BIOS.").pack(fill="x")

    # ------------------------------------------------------------------
    def run(self):
        self.btn.set_enabled(False)
        self.msg.config(text="Leyendo tu equipo…", fg=VIOLET)
        self.pb.pack(anchor="w", pady=(6, 0))
        self.pb.start(12)
        self.app.bg(bios.build_guide, self.done, self.fail)

    def fail(self, e):
        self.pb.stop()
        self.pb.pack_forget()
        self.btn.set_enabled(True)
        self.msg.config(text=f"No pude generar la guía: {e}", fg=RED)

    def done(self, g):
        self.pb.stop()
        self.pb.pack_forget()
        self.btn.set_enabled(True)
        self.btn.set_text("◉   REGENERAR GUÍA")
        self.msg.config(text="Guía lista ✓", fg=GREEN)
        self.guide = g
        self.render(g)

    # ------------------------------------------------------------------
    def render(self, g):
        sf = self.scroll
        sf.clear()
        root = sf.inner

        c = Card(root, accent=CYAN, title="◎  Tu plataforma")
        c.pack(fill="x", pady=(0, 10))
        kv_rows(c.body, g["platform"])
        if g["laptop"]:
            WrapLabel(c.body, fg=YELLOW, font=F(9),
                      text="Parece un portátil: la mayoría de portátiles esconden estas opciones o no dejan cambiarlas. "
                           "Usa lo que tu BIOS te permita y no fuerces nada.").pack(fill="x", pady=(8, 0))

        self._enter_card(root, g)
        self._status_card(root, g)
        if g["ram"]:
            self._ram_card(root, g["ram"])
        self._items(root, g["items"])
        for title, tips in g["gpu_tips"]:
            cc = Card(root, accent=GREEN, title="▲  " + title)
            cc.pack(fill="x", pady=(0, 10))
            for t in tips:
                WrapLabel(cc.body, text="•  " + t).pack(fill="x", pady=1)

        end = Card(root, accent=PINK, title="⚠  Si algo sale mal")
        end.pack(fill="x", pady=(0, 14))
        WrapLabel(end.body, text="Si tras un cambio el PC no arranca o da pantalla negra: apaga, espera 10 s y reinicia 2–3 veces (la BIOS vuelve a valores seguros). "
                                 "Si no basta: botón o jumper «Clear CMOS» de la placa, o quita la pila plana 30 segundos con el PC desenchufado.").pack(fill="x")

    def _enter_card(self, root, g):
        c = Card(root, accent=PINK, title="⏻  Entrar a la BIOS")
        c.pack(fill="x", pady=(0, 10))
        WrapLabel(c.body, text=f"Al encender el PC pulsa repetidamente  {g['enter_key']}.  O desde aquí:").pack(fill="x")
        r = tk.Frame(c.body, bg=PANEL)
        r.pack(fill="x", pady=(10, 0))
        NeonButton(r, "↻  Reiniciar directamente a la BIOS", self.reboot_fw, color=PINK, filled=True, padx=16, pady=8).pack(side="left")
        NeonButton(r, "Guardar esta guía en un archivo (para el móvil)", self.export, color=CYAN, padx=14, pady=8).pack(side="left", padx=10)
        WrapLabel(c.body, fg=MUTED, font=F(9),
                  text="Mientras estás dentro de la BIOS no puedes mirar esta app: guarda el archivo y ábrelo en el móvil, o hazle una foto al paso que toque.").pack(fill="x", pady=(8, 0))

    def _status_card(self, root, g):
        fw = g["fw"]
        c = Card(root, accent=YELLOW, title="✔  Comprobaciones en tu equipo (ahora mismo)")
        c.pack(fill="x", pady=(0, 10))

        def line(ok, text_ok, text_bad, text_unknown):
            col, ico, txt = (GREEN, "✓", text_ok) if ok else (YELLOW, "✗", text_bad) if ok is False else (MUTED, "?", text_unknown)
            r = tk.Frame(c.body, bg=PANEL)
            r.pack(fill="x", pady=2)
            tk.Label(r, text=ico, font=F(13, True), fg=col, bg=PANEL, width=3).pack(side="left")
            WrapLabel(r, text=txt, fg=FG if ok else col).pack(side="left", fill="x", expand=True)
        line(fw["uefi"], "Windows arranca en modo UEFI (puedes desactivar CSM sin problema)",
             "Windows arranca en modo Legacy/MBR: NO desactives CSM o no arrancará", "No pude comprobar si usas UEFI o Legacy")
        line(fw["secure_boot"], "Secure Boot activado (necesario para Windows 11 y algunos anti-cheat)",
             "Secure Boot desactivado", "No pude leer el estado de Secure Boot")
        line(fw["rebar"], "Resizable BAR ACTIVADO en tu gráfica NVIDIA", "Resizable BAR desactivado (mira el punto correspondiente más abajo)",
             "No puedo comprobar Resizable BAR en esta gráfica (solo lo leo en NVIDIA)")

    def _ram_card(self, root, p):
        c = Card(root, accent=PINK, title="▥  Tiempos de RAM recomendados para tu equipo")
        c.pack(fill="x", pady=(0, 10))
        for t in p["tiers"]:
            col = TIER_COLOR[t["level"]]
            box = tk.Frame(c.body, bg=PANEL2)
            box.pack(fill="x", pady=5)
            head = tk.Frame(box, bg=PANEL2)
            head.pack(fill="x", padx=12, pady=(10, 4))
            tk.Label(head, text=f"NIVEL {t['level']}", font=F(10, True), fg=BG, bg=col, padx=8).pack(side="left")
            tk.Label(head, text="  " + t["name"], font=F(10, True), fg=col, bg=PANEL2, anchor="w", justify="left", wraplength=620).pack(side="left", fill="x")
            body = tk.Frame(box, bg=PANEL2)
            body.pack(fill="x", padx=12, pady=(0, 10))
            body.columnconfigure(1, weight=1)
            for i, (k, v) in enumerate(t["rows"]):
                tk.Label(body, text=k, font=F(9, True), fg=MUTED, bg=PANEL2, anchor="nw", justify="left", wraplength=190).grid(
                    row=i, column=0, sticky="nw", padx=(0, 12), pady=2)
                WrapLabel(body, text=v, bg=PANEL2, font=("Consolas", 10)).grid(row=i, column=1, sticky="ew", pady=2)
        tk.Label(c.body, text="IMPORTANTE", font=F(10, True), fg=YELLOW, bg=PANEL, anchor="w").pack(fill="x", pady=(10, 2))
        for n in p["notes"]:
            WrapLabel(c.body, text="•  " + n, fg=FG).pack(fill="x", pady=1)

    def _items(self, root, items):
        head = tk.Frame(root, bg=BG)
        head.pack(fill="x", pady=(8, 6))
        tk.Label(head, text="Ajustes de BIOS para el máximo rendimiento", font=F(14, True), fg=FG, bg=BG).pack(side="left")
        self.prog = tk.Label(head, text="", font=F(10, True), fg=GREEN, bg=BG)
        self.prog.pack(side="right", padx=6)
        self.vars = {}
        area = None
        for it in items:
            if it["area"] != area:
                area = it["area"]
                tk.Label(root, text=area.upper(), font=F(9, True), fg=VIOLET, bg=BG, anchor="w").pack(fill="x", pady=(10, 4))
            v = tk.BooleanVar(value=bool(self.checks.get(it["id"])))
            self.vars[it["id"]] = v
            v.trace_add("write", lambda *a: self._save())
            c = Card(root, accent=VIOLET if not v.get() else GREEN, pad=12)
            c.pack(fill="x", pady=(0, 8))
            top = tk.Frame(c.body, bg=PANEL)
            top.pack(fill="x")
            checkbox(top, "", v).pack(side="left", anchor="n", padx=(0, 4))
            t = tk.Frame(top, bg=PANEL)
            t.pack(side="left", fill="x", expand=True)
            tk.Label(t, text=it["title"], font=F(11, True), fg=FG, bg=PANEL, anchor="w", justify="left", wraplength=640).pack(fill="x")
            tags = tk.Frame(t, bg=PANEL)
            tags.pack(fill="x", pady=(4, 6))
            badge(tags, *EFFECT[it["effect"]]).pack(side="left", padx=(0, 6))
            badge(tags, *RISK[it["risk"]]).pack(side="left", padx=(0, 6))
            for k, label in (("where", "DÓNDE"), ("set_to", "PONER"), ("why", "POR QUÉ")):
                r = tk.Frame(t, bg=PANEL)
                r.pack(fill="x", pady=1)
                tk.Label(r, text=label, font=F(8, True), fg=MUTED, bg=PANEL, width=8, anchor="nw").pack(side="left", anchor="n")
                WrapLabel(r, text=it[k], fg=CYAN if k == "set_to" else FG if k == "where" else MUTED,
                          font=("Consolas", 9) if k != "why" else F(9)).pack(side="left", fill="x", expand=True)
            if it["note"]:
                r = tk.Frame(t, bg=PANEL)
                r.pack(fill="x", pady=(3, 0))
                tk.Label(r, text="OJO", font=F(8, True), fg=YELLOW, bg=PANEL, width=8, anchor="nw").pack(side="left", anchor="n")
                WrapLabel(r, text=it["note"], fg=YELLOW, font=F(9)).pack(side="left", fill="x", expand=True)
        self._save()

    def _save(self):
        d = {k: bool(v.get()) for k, v in self.vars.items()}
        self.checks.update(d)
        bios.save_checks(self.checks)
        if self.vars:
            n = sum(d.values())
            self.prog.config(text=f"{n} de {len(d)} hechos")

    # ------------------------------------------------------------------
    def reboot_fw(self):
        if not messagebox.askyesno("Reiniciar a la BIOS",
                                   "Guarda tu trabajo y cierra los programas.\n\nEl PC se reiniciará en 10 segundos y entrará directo a la BIOS.\n\n¿Continuar?"):
            return
        ok, msg = bios.reboot_to_firmware()
        if not ok:
            messagebox.showwarning("No se pudo", f"No pude reiniciar a la BIOS ({msg}).\nUsa la tecla {self.guide['enter_key'] if self.guide else 'Supr/F2'} al encender.")
        else:
            self.app.status("Reiniciando a la BIOS…" if not DEMO else msg)

    def export(self):
        if not self.guide:
            return
        try:
            p = bios.export_to_desktop(self.guide)
            messagebox.showinfo("Guía guardada", f"Guardada en:\n{p}\n\nÁbrela en tu móvil o imprímela para tenerla delante en la BIOS.")
        except OSError as e:
            messagebox.showerror("Error", f"No pude guardar el archivo: {e}")
