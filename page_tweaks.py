"""Página «Tweaks»: todos los ajustes de rendimiento y latencia, por nivel de riesgo, para que elijas cuáles aplicar."""
import tkinter as tk
from tkinter import messagebox

import actions
import tweaks
import tweaks_extra
from util import DEMO, is_admin
from widgets import (BG, CYAN, F, FG, GREEN, MUTED, PANEL, PINK, RED, YELLOW, Card, NeonButton, ScrollFrame, WrapLabel,
                     badge, checkbox, page_title)

COL = {"green": GREEN, "yellow": YELLOW, "red": RED}


class TweaksPage(tk.Frame):
    def __init__(self, parent, app):
        super().__init__(parent, bg=BG)
        self.app = app
        self.busy = False
        self.acts, self.vars = [], {}
        self.v_restore = tk.BooleanVar(value=True)
        top = tk.Frame(self, bg=BG)
        top.pack(fill="x", padx=26, pady=(22, 6))
        page_title(top, "Tweaks", "Latencia y rendimiento en tres niveles de riesgo: tú eliges y cada uno explica qué hace.", accent=PINK).pack(anchor="w")
        self.scroll = ScrollFrame(self)
        self.scroll.pack(fill="both", expand=True, padx=(26, 10), pady=(8, 10))
        root = self.scroll.inner
        c = Card(root, accent=YELLOW, title="Cómo funciona")
        c.pack(fill="x", pady=(0, 12))
        for t in ("No se marca nada solo. Marca los que quieras y pulsa «Aplicar los marcados».",
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
        self.vars = {}
        if not self.acts:
            return
        for risk, name, blurb, color in tweaks.LEVELS:
            items = [a for a in self.acts if a.risk == risk]
            if not items:
                continue
            col = COL[color]
            c = Card(self.body, accent=col, title=f"{name}  ·  {len(items)}")
            c.pack(fill="x", pady=(0, 12))
            WrapLabel(c.body, text=blurb, font=F(9), fg=MUTED).pack(fill="x", pady=(0, 6))
            row = tk.Frame(c.body, bg=PANEL)
            row.pack(fill="x", pady=(0, 6))
            NeonButton(row, "Marcar todos", lambda it=items: self._mark(it, True), color=col, padx=12, pady=5,
                       font=F(9, True)).pack(side="left")
            NeonButton(row, "Desmarcar", lambda it=items: self._mark(it, False), color=MUTED, padx=12, pady=5,
                       font=F(9, True)).pack(side="left", padx=8)
            for a in items:
                self._row(c.body, a, col)
        # ----- pie
        f = self.foot
        checkbox(f, "Crear un punto de restauración de Windows antes de aplicar (recomendado)", self.v_restore, bg=BG,
                 font=F(10)).pack(anchor="w", pady=(0, 8))
        self.b_apply = NeonButton(f, "⚡  APLICAR LOS MARCADOS", self.apply, color=PINK, filled=True, font=F(12, True), padx=26, pady=10)
        self.b_apply.pack(anchor="w")

    def _row(self, parent, a, col):
        v = tk.BooleanVar(value=False)
        self.vars[a.id] = v
        box = tk.Frame(parent, bg=PANEL)
        box.pack(fill="x", pady=5)
        head = tk.Frame(box, bg=PANEL)
        head.pack(fill="x")
        checkbox(head, a.title, v, bg=PANEL, font=F(10, True)).pack(side="left", fill="x", expand=True)
        tags = tk.Frame(head, bg=PANEL)
        tags.pack(side="right")
        eff = tweaks.EFFECTS.get(getattr(a, "effect", ""), "")
        if eff:
            badge(tags, eff, GREEN if a.effect == "real" else CYAN if a.effect in ("pequeño", "depende") else MUTED).pack(side="left", padx=3)
        if a.reboot:
            badge(tags, "reinicio", YELLOW).pack(side="left", padx=3)
        if a.needs_admin and not (is_admin() or DEMO):
            badge(tags, "admin", RED).pack(side="left", padx=3)
        WrapLabel(box, text=a.desc, font=F(9), fg=MUTED).pack(fill="x", padx=(28, 0), pady=(2, 0))
        if getattr(a, "warning", ""):
            WrapLabel(box, text="⚠ " + a.warning, font=F(9, True), fg=RED).pack(fill="x", padx=(28, 0), pady=(2, 0))
        if getattr(a, "status", ""):
            tk.Label(box, text=str(a.status), font=("Consolas", 8), fg=MUTED, bg=PANEL, anchor="w").pack(fill="x", padx=(28, 0), pady=(2, 0))

    def _mark(self, items, flag):
        for a in items:
            if a.id in self.vars:
                self.vars[a.id].set(flag)

    # ------------------------------------------------------------------
    def apply(self):
        chosen = [a for a in self.acts if self.vars.get(a.id) and self.vars[a.id].get()]
        if self.busy:
            return
        if not chosen:
            self.msg.config(text="Marca primero algún tweak.", fg=YELLOW)
            return
        hard = [a for a in chosen if a.risk == "alto"]
        text = f"Se van a aplicar {len(chosen)} tweaks."
        if hard:
            text += f"\n\n{len(hard)} son de nivel EXTREMO (cambian seguridad o el arranque). Si juegas con anti-cheat estricto, revísalos antes."
        text += "\n\nPodrás deshacerlos desde el Historial.\n¿Continuar?"
        if not DEMO and not messagebox.askyesno("Aplicar tweaks", text):
            return
        self.busy = True
        self.b_apply.set_enabled(False)
        self.b_scan.set_enabled(False)
        self.msg.config(text="Aplicando…", fg=CYAN)
        restore = self.v_restore.get()

        def work():
            if restore:
                self._say("Creando punto de restauración…")
                ok, m = actions.create_restore_point()
                if not ok:
                    self._say(f"Sin punto de restauración ({m[:80]}). Sigo…")
            done = fail = 0
            reboot = False
            errors = []
            for i, a in enumerate(chosen, 1):
                self._say(f"Aplicando {i}/{len(chosen)}: {a.title[:60]}")
                r = actions.execute(a)
                if r.ok:
                    done += 1
                    reboot = reboot or a.reboot
                else:
                    fail += 1
                    errors.append(f"{a.title[:40]}: {r.msg[:60]}")
            return done, fail, reboot, errors

        self.app.bg(work, self._applied, self._fail)

    def _applied(self, res):
        done, fail, reboot, errors = res
        self.busy = False
        txt = f"✓ {done} aplicados" + (f"  ·  {fail} con error" if fail else "") + ("  ·  reinicia el PC para completar" if reboot else "")
        self.msg.config(text=txt, fg=GREEN if not fail else YELLOW)
        if errors:
            messagebox.showwarning("Algunos tweaks no se aplicaron", "\n".join(errors[:8]))
        self.scan()
