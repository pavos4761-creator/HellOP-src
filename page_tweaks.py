"""Página «Tweaks»: todos los ajustes de rendimiento y latencia, por nivel de riesgo, para que elijas cuáles aplicar."""
import tkinter as tk
from tkinter import messagebox

import actions
import tweaks
import tweaks_extra
import cuadros
from util import DEMO, is_admin
from widgets import (BG, CYAN, F, FG, GREEN, MUTED, PANEL, PINK, RED, YELLOW, Card, NeonButton, ScrollFrame, WrapLabel,
                     badge, checkbox, page_title)

COL = {"green": GREEN, "yellow": YELLOW, "red": RED}


class TweaksPage(tk.Frame):
    def __init__(self, parent, app):
        super().__init__(parent, bg=BG)
        self.app = app
        self.busy = False
        self.acts, self.vars, self.cuadros = [], {}, []
        self.v_restore = tk.BooleanVar(value=True)
        top = tk.Frame(self, bg=BG)
        top.pack(fill="x", padx=26, pady=(22, 6))
        page_title(top, "Tweaks", "Latencia y rendimiento en tres niveles de riesgo: tú eliges y cada uno explica qué hace.", accent=PINK).pack(anchor="w")
        self.scroll = ScrollFrame(self)
        self.scroll.pack(fill="both", expand=True, padx=(26, 10), pady=(8, 10))
        root = self.scroll.inner
        c = Card(root, accent=YELLOW, title="Cómo funciona")
        c.pack(fill="x", pady=(0, 12))
        for t in ("No se marca nada solo. Marca los cuadrados que quieras y pulsa «Aplicar los marcados», o aplica uno solo con su botón.",
                  "Todo queda en el Historial: puedes deshacer cualquier tweak uno a uno o todos a la vez.",
                  "«Efecto real» significa que se mide en la mayoría de equipos; «casi nulo» se ofrece por completitud. "
                  "Sé realista: estos ajustes dan mejoras pequeñas; los saltos grandes vienen de los gráficos del juego y del calor.",
                  "Muchos piden reiniciar y administrador; te lo indico en cada uno. Solo aparecen los que aplican a TU equipo."):
            WrapLabel(c.body, text="•  " + t, font=F(9), fg=MUTED).pack(fill="x", pady=1)
        bar = tk.Frame(root, bg=BG)
        bar.pack(fill="x", pady=(0, 8))
        self.b_scan = NeonButton(bar, "↻  BUSCAR TWEAKS PARA MI PC", self.scan, color=PINK, filled=True, font=F(11, True), padx=20, pady=8)
        self.b_scan.pack(side="left")
        self.msg = tk.Label(bar, text="", font=F(10), fg=MUTED, bg=BG)
        self.msg.pack(side="left", padx=14)
        self.body = tk.Frame(root, bg=BG)
        self.body.pack(fill="x")
        self.foot = tk.Frame(root, bg=BG)
        self.foot.pack(fill="x", pady=(4, 14))
        m = Card(root, accent=MUTED, title="Tweaks famosos que NO incluyo (y por qué)")
        m.pack(fill="x", pady=(0, 14))
        WrapLabel(m.body, text="Hay listas enormes de «tweaks de regedit» en vídeos y foros. Casi todos vienen de guías antiguas o se copian "
                               "sin probar. Según la documentación de Microsoft y pruebas públicas, estos no hacen lo que prometen, "
                               "así que HellOP no te los ofrece:", font=F(9), fg=MUTED).pack(fill="x", pady=(0, 6))
        for name, why in tweaks_extra.MITOS:
            r = tk.Frame(m.body, bg=PANEL)
            r.pack(fill="x", pady=2)
            tk.Label(r, text="✗", font=F(10, True), fg=RED, bg=PANEL).pack(side="left", anchor="n")
            WrapLabel(r, text=f"{name}: {why}", font=F(9), fg=MUTED).pack(side="left", fill="x", expand=True, padx=(8, 0))
        self._loaded = False

    def on_show(self):
        if not self._loaded:
            self._loaded = True
            self.scan()

    # ------------------------------------------------------------------
    def scan(self):
        if self.busy:
            return
        self.busy = True
        self.b_scan.set_enabled(False)
        self.msg.config(text="Revisando tu equipo (puede tardar unos segundos)…", fg=CYAN)
        self.app.bg(lambda: tweaks.collect(lambda m: self._say(m)), self._scanned, self._fail)

    def _say(self, text):
        self.app.ui(lambda: self.msg.config(text=text, fg=CYAN))

    def _fail(self, e):
        self.busy = False
        self.b_scan.set_enabled(True)
        self.msg.config(text=f"Error: {e}", fg=RED)

    def _scanned(self, acts):
        self.busy = False
        self.b_scan.set_enabled(True)
        self.acts = acts
        ya = f"  ·  otros {tweaks.SKIPPED} ya están aplicados o no aplican a tu equipo" if tweaks.SKIPPED else ""
        self.msg.config(text=(f"{len(acts)} tweaks disponibles en tu equipo" if acts else "No queda ningún tweak por aplicar. ¡Todo hecho!") + ya,
                        fg=GREEN)
        self.render()

    def render(self):
        for w in list(self.body.winfo_children()) + list(self.foot.winfo_children()):
            w.destroy()
        self.cuadros = []
        if not self.acts:
            return
        for risk, name, blurb, color in tweaks.LEVELS:
            items = [a for a in self.acts if a.risk == risk]
            if not items:
                continue
            col = COL[color]
            cab = tk.Frame(self.body, bg=BG)
            cab.pack(fill="x", pady=(12, 2))
            tk.Label(cab, text=name.upper(), font=F(10, True), fg=col, bg=BG).pack(side="left")
            tk.Label(cab, text=f"{len(items)}", font=F(10, True), fg=MUTED, bg=BG).pack(side="left", padx=8)
            lk = tk.Label(cab, text="marcar todos", font=F(9, True), fg=CYAN, bg=BG, cursor="hand2")
            lk.pack(side="left")
            lk.bind("<Button-1>", lambda e, it=items: self._mark(it, True))
            WrapLabel(self.body, text=blurb, font=F(9), fg=MUTED, bg=BG).pack(fill="x", pady=(0, 8))
            grid = tk.Frame(self.body, bg=BG)
            grid.pack(fill="x")
            for i in range(3):
                grid.columnconfigure(i, weight=1, uniform="c")
            for k, a in enumerate(items):
                c = cuadros.Cuadro(grid, self, a)
                c.grid(row=k // 3, column=k % 3, sticky="nsew", padx=(0, 12) if k % 3 < 2 else 0, pady=(0, 12))
                self.cuadros.append(c)
        f = self.foot
        checkbox(f, "Crear un punto de restauración de Windows antes de aplicar (recomendado)", self.v_restore, bg=BG,
                 font=F(10)).pack(anchor="w", pady=(0, 8))
        self.b_apply = NeonButton(f, "Aplicar los marcados", lambda: self.aplicar([c for c in self.cuadros if c.sel()]),
                                  color=PINK, filled=True, font=F(12, True), padx=26, pady=10)
        self.b_apply.pack(anchor="w")
        self.actualiza_barra()

    def actualiza_barra(self):
        n = sum(1 for c in self.cuadros if c.sel())
        if getattr(self, "b_apply", None) and self.b_apply.winfo_exists():
            self.b_apply.set_text(f"Aplicar los marcados ({n})" if n else "Aplicar los marcados")
            self.b_apply.set_enabled(n > 0 and not self.busy)

    def _mark(self, items, flag):
        ids = {id(a) for a in items}
        for c in self.cuadros:
            if id(c.a) in ids:
                c.poner_sel(flag)
        self.actualiza_barra()

    def aplicar(self, lista):
        lista = [c for c in lista if c.estado in ("idle", "bad")]
        if self.busy or not lista:
            return
        hard = [c for c in lista if c.a.risk == "alto"]
        if hard and not DEMO and not messagebox.askyesno(
                "Ajustes de nivel EXTREMO", f"{len(hard)} cambian seguridad o el arranque. Si juegas con anti-cheat estricto, revísalos antes.\n"
                                           "Se pueden deshacer desde el Historial.\n\n¿Continuar?"):
            return
        self.busy = True
        self.b_scan.set_enabled(False)
        self.b_apply.set_enabled(False)
        restore = self.v_restore.get() and not getattr(self, "_rest", False)
        for c in lista:
            c.corriendo()

        def work():
            if restore:
                self._say("Creando punto de restauración…")
                actions.create_restore_point()
                self._rest = True
            done = fail = 0
            reboot = False
            for i, c in enumerate(lista, 1):
                self._say(f"Aplicando {i}/{len(lista)}: {c.a.title[:60]}")
                r = actions.execute(c.a)
                self.app.ui(c.fin, r)
                if r.ok:
                    done += 1
                    reboot = reboot or c.a.reboot
                else:
                    fail += 1
            return done, fail, reboot, []

        self.app.bg(work, self._applied, self._fail)

    def _applied(self, res):
        done, fail, reboot, errors = res
        self.busy = False
        txt = f"✓ {done} aplicados" + (f"  ·  {fail} con error" if fail else "") + ("  ·  reinicia el PC para completar" if reboot else "")
        self.msg.config(text=txt, fg=GREEN if not fail else YELLOW)
        if errors:
            messagebox.showwarning("Algunos tweaks no se aplicaron", "\n".join(errors[:8]))
        self.b_scan.set_enabled(True)
        self.actualiza_barra()
