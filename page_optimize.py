"""Página «Optimizar»: elige perfil → punto de restauración → te pregunta
cada cambio uno por uno → resumen."""
import tkinter as tk
from tkinter import messagebox, ttk

import actions
from util import IS_WIN, DEMO, is_admin, run_cmd
from widgets import (BG, CYAN, F, FG, GREEN, MUTED, PANEL, PINK, RED, VIOLET, YELLOW, Card, NeonButton,
                     ScrollFrame, WrapLabel, badge, checkbox, page_title)

PROFILES = [   # ordenados de menos a más cambios
    ("work", "✎", "TRABAJO", CYAN,
     "Un PC ágil y silencioso para el día a día: menos programas de inicio, sin telemetría ni apps basura, "
     "menús instantáneos y mejor DNS. No toca el plan de energía."),
    ("gaming", "☄", "GAMING", PINK,
     "Máxima respuesta y mínima latencia: energía al máximo, Modo Juego, prioridad de GPU/CPU, ratón sin aceleración, "
     "red sin límites, además de limpiar inicio y servicios."),
    ("deep", "✧", "LIMPIEZA PROFUNDA", VIOLET,
     "Quita lo que Windows hace sin que lo pidas: telemetría, tareas programadas, publicidad, Copilot/Recall, Edge en segundo plano, "
     "reparto P2P de actualizaciones y servicios sobrantes. Más privacidad y menos ruido de fondo."),
    ("extreme", "☢", "EXTREMO", RED,
     "Todo lo de Gaming MÁS ajustes profundos: arranque (HPET, tick), energía de CPU/PCIe/USB, registro, red, modo MSI de la GPU "
     "y opciones que cambian seguridad por FPS. Cada uno te dice su efecto REAL y su riesgo."),
    ("full", "⚙", "COMPLETO", GREEN,
     "Todo lo anterior junto. Revisaré todo lo que se puede mejorar en tu PC y te lo preguntaré cambio por cambio."),
]


class OptimizePage(tk.Frame):
    def __init__(self, parent, app):
        super().__init__(parent, bg=BG)
        self.app = app
        self.gen = 0
        self.v_restore = tk.BooleanVar(value=True)
        self.scroll = ScrollFrame(self)              # si la ventana es pequeña, sale una barra para subir y bajar
        self.scroll.pack(fill="both", expand=True, padx=(26, 10), pady=(20, 10))
        self.stage = self.scroll.inner
        self.reset_state()
        self.show_intro()

    # ------------------------------------------------------------------
    def reset_state(self):
        self.acts, self.idx = [], 0
        self.applied, self.failed, self.skipped = [], [], 0
        self.need_reboot = False
        self.busy = False
        self.profile = None

    def clear(self):
        self.gen += 1
        for w in self.stage.winfo_children():
            w.destroy()
        self.scroll.canvas.yview_moveto(0)

    def heading(self, title, sub=None):
        page_title(self.stage, title, sub, accent=PINK).pack(anchor="w", pady=(0, 12))

    # ---- 1. elegir perfil -------------------------------------------------
    def show_intro(self):
        self.clear()
        self.heading("Optimizar", "Elige para qué quieres tu PC. Yo no cambio nada sin preguntarte: verás cada ajuste y decides.")
        if not is_admin():
            c = Card(self.stage, accent=RED)
            c.pack(fill="x", pady=(0, 12))
            WrapLabel(c.body, fg=YELLOW,
                      text="Estás sin permisos de administrador: los ajustes de servicios, energía, red y el punto de restauración "
                           "no se podrán aplicar. Usa «Reabrir como administrador» arriba a la derecha.").pack(fill="x")
        row = tk.Frame(self.stage, bg=BG)
        row.pack(fill="x")
        for i in range(3):
            row.columnconfigure(i, weight=1, uniform="p")
        for i, (key, icon, name, color, desc) in enumerate(PROFILES):
            c = Card(row, accent=color)
            c.grid(row=i // 3, column=i % 3, sticky="nsew", padx=(0, 12) if i % 3 < 2 else 0, pady=(0, 12))
            tk.Label(c.body, text=icon, font=F(30, True), fg=color, bg=PANEL).pack(anchor="w")
            tk.Label(c.body, text=f"NIVEL {i + 1} DE {len(PROFILES)}", font=F(8, True), fg=MUTED, bg=PANEL).pack(anchor="w")
            tk.Label(c.body, text=name, font=F(16, True), fg=color, bg=PANEL).pack(anchor="w", pady=(0, 6))
            WrapLabel(c.body, text=desc, fg=FG).pack(fill="x")
            NeonButton(c.body, "Elegir  →", lambda k=key: self.start(k), color=color, filled=True).pack(anchor="w", pady=(14, 0))

        opts = Card(self.stage, accent=VIOLET, title="Antes de empezar")
        opts.pack(fill="x", pady=(14, 0))
        checkbox(opts.body, "Crear un punto de restauración de Windows (recomendado)", self.v_restore).pack(fill="x", pady=2)
        WrapLabel(opts.body, fg=MUTED, font=F(9),
                  text="Además, todo lo que apliques queda registrado en «Historial / Deshacer» para volver atrás con un clic.").pack(fill="x", pady=(6, 0))

    # ---- 2. buscar ----------------------------------------------------------
    def start(self, profile):
        self.reset_state()
        self.profile = profile
        self.clear()
        self.heading("Buscando qué se puede mejorar…", "Esto tarda unos segundos (mido tu DNS y reviso inicio, servicios y procesos).")
        self.scan_msg = tk.Label(self.stage, text="Empezando…", font=F(11), fg=CYAN, bg=BG, anchor="w")
        self.scan_msg.pack(anchor="w", pady=(10, 6))
        pb = ttk.Progressbar(self.stage, style="Neon.Horizontal.TProgressbar", mode="indeterminate", length=380)
        pb.pack(anchor="w")
        pb.start(12)
        g = self.gen
        self.app.bg(lambda: actions.discover(profile, progress=lambda m: self.app.ui(self._scan_msg, g, m)),
                    lambda acts: self.after_scan(g, acts))

    def _scan_msg(self, g, m):
        if g == self.gen:
            self.scan_msg.config(text=m)

    def after_scan(self, g, acts):
        if g != self.gen:
            return
        if not acts:
            self.clear()
            self.heading("Tu PC ya está muy bien", "No encontré nada que mejorar para este perfil.")
            NeonButton(self.stage, "Volver", self.show_intro, color=CYAN).pack(anchor="w", pady=10)
            return
        self.acts = acts
        self.prepare()

    # ---- 3. preparación: test antes + restauración --------------------------
    def prepare(self):
        self.clear()
        g = self.gen
        self.heading(f"Encontré {len(self.acts)} cosas que se pueden mejorar", "Primero me preparo para que puedas volver atrás si algo no te gusta.")
        card = Card(self.stage, accent=CYAN, title="Preparación")
        card.pack(fill="x")
        self.prep_rows = {}
        for key, text in (("restore", "Punto de restauración de Windows"),):
            enabled = self.v_restore.get()
            r = tk.Frame(card.body, bg=PANEL)
            r.pack(fill="x", pady=4)
            ico = tk.Label(r, text="•" if enabled else "—", font=F(14, True), fg=MUTED, bg=PANEL, width=3)
            ico.pack(side="left")
            tk.Label(r, text=text + ("" if enabled else "  (omitido)"), font=F(11), fg=FG if enabled else MUTED, bg=PANEL).pack(side="left")
            det = tk.Label(r, text="", font=F(9), fg=MUTED, bg=PANEL)
            det.pack(side="left", padx=10)
            self.prep_rows[key] = (ico, det)
        self.prep_pb = ttk.Progressbar(card.body, style="Neon.Horizontal.TProgressbar", mode="determinate", maximum=100, length=380)
        self.prep_pb.pack(anchor="w", pady=(10, 0))
        do_restore = self.v_restore.get()

        def work():
            out = {}
            if do_restore:
                self.app.ui(self._prep_state, g, "restore", "run", "creándolo (puede tardar un minuto)…")
                ok, msg = actions.create_restore_point()
                out["restore"] = (ok, msg)
                self.app.ui(self._prep_state, g, "restore", "ok" if ok else "bad", msg)
            return out

        self.app.bg(work, lambda out: self.after_prep(g, out))

    def _prep_state(self, g, key, state, text):
        if g != self.gen:
            return
        ico, det = self.prep_rows[key]
        sym, col = {"run": ("…", CYAN), "ok": ("✓", GREEN), "bad": ("✗", RED)}[state]
        ico.config(text=sym, fg=col)
        det.config(text=text, fg=col if state != "run" else MUTED)

    def after_prep(self, g, out):
        if g != self.gen:
            return
        r = out.get("restore")
        if r and not r[0]:
            if not messagebox.askyesno("Punto de restauración",
                                       f"No pude crear el punto de restauración:\n\n{r[1]}\n\n"
                                       "¿Continuar igualmente? Los cambios se podrán deshacer desde «Historial / Deshacer»."):
                self.show_intro()
                return
        self.idx = 0
        self.show_wizard()

    # ---- 4. preguntar uno por uno ------------------------------------------
    def show_wizard(self):
        self.clear()
        n = len(self.acts)
        if self.idx >= n:
            self.show_summary()
            return
        a = self.acts[self.idx]
        g = self.gen
        top = tk.Frame(self.stage, bg=BG)
        top.pack(fill="x")
        tk.Label(top, text=f"Cambio {self.idx + 1} de {n}", font=F(11, True), fg=MUTED, bg=BG).pack(side="left")
        badge(top, actions.GROUP_NAMES.get(a.group, a.group).upper(), VIOLET).pack(side="left", padx=10)
        pb = ttk.Progressbar(self.stage, style="Neon.Horizontal.TProgressbar", mode="determinate", maximum=n, value=self.idx)
        pb.pack(fill="x", pady=(8, 14))

        card = Card(self.stage, accent=PINK, pad=20)
        card.pack(fill="x")
        tk.Label(card.body, text=a.title, font=F(17, True), fg=FG, bg=PANEL, anchor="w", justify="left", wraplength=760).pack(fill="x")
        if getattr(a, "status", ""):
            tk.Label(card.body, text=a.status, font=("Consolas", 9), fg=CYAN, bg=PANEL, anchor="w", justify="left",
                     wraplength=760).pack(fill="x", pady=(6, 0))
        WrapLabel(card.body, text=a.desc, font=F(11)).pack(fill="x", pady=(10, 10))
        tags = tk.Frame(card.body, bg=PANEL)
        tags.pack(fill="x")
        risk_txt, risk_col = {"bajo": ("RIESGO BAJO", GREEN), "medio": ("RIESGO MEDIO: LEE BIEN", YELLOW),
                              "alto": ("RIESGO ALTO: REDUCE SEGURIDAD", RED)}.get(a.risk, ("RIESGO MEDIO", YELLOW))
        badge(tags, risk_txt, risk_col).pack(side="left", padx=(0, 6))
        eff = {"real": ("EFECTO REAL", GREEN), "pequeño": ("EFECTO PEQUEÑO", YELLOW), "depende": ("DEPENDE DE TU EQUIPO", CYAN),
               "mínimo": ("EFECTO CASI NULO", MUTED)}.get(getattr(a, "effect", ""))
        if eff:
            badge(tags, *eff).pack(side="left", padx=(0, 6))
        badge(tags, "SE PUEDE DESHACER" if a.reversible else "NO SE PUEDE DESHACER", GREEN if a.reversible else YELLOW).pack(side="left", padx=(0, 6))
        if a.needs_admin:
            badge(tags, "NECESITA ADMINISTRADOR", MUTED if is_admin() else RED).pack(side="left", padx=(0, 6))
        if a.reboot:
            badge(tags, "SE NOTA AL REINICIAR / CERRAR SESIÓN", VIOLET).pack(side="left", padx=(0, 6))

        if getattr(a, "warning", ""):
            wc = Card(self.stage, accent=RED, pad=12)
            wc.pack(fill="x", pady=(10, 0))
            WrapLabel(wc.body, text="⚠  " + a.warning, fg=RED, font=F(10, True)).pack(fill="x")
        btns = tk.Frame(self.stage, bg=BG)
        btns.pack(fill="x", pady=(16, 6))
        self.b_apply = NeonButton(btns, "✓   APLICAR", lambda: self.do_apply(a), color=GREEN, filled=True, font=F(13, True), padx=30, pady=11)
        self.b_apply.pack(side="left")
        self.b_skip = NeonButton(btns, "Omitir", lambda: self.do_skip(), color=MUTED, font=F(12, True), padx=24, pady=10)
        self.b_skip.pack(side="left", padx=12)
        self.flash = tk.Label(btns, text="", font=F(11, True), bg=BG, fg=GREEN, anchor="w")
        self.flash.pack(side="left", padx=10)

        more = tk.Frame(self.stage, bg=BG)
        more.pack(fill="x", pady=(10, 0))
        same_group = sum(1 for x in self.acts[self.idx:] if x.group == a.group)
        if same_group > 1:
            NeonButton(more, f"Omitir los {same_group} de «{actions.GROUP_NAMES.get(a.group, a.group)}»", lambda: self.skip_group(a.group),
                       color=MUTED, font=F(9, True), padx=10, pady=5).pack(side="left", padx=(0, 8))
        safe = [x for x in self.acts[self.idx:] if x.risk == "bajo" and x.reversible and (not x.needs_admin or is_admin())]
        if len(safe) > 1:
            NeonButton(more, f"Aplicar sin preguntar los {len(safe)} seguros que quedan", self.apply_safe_rest, color=CYAN,
                       font=F(9, True), padx=10, pady=5).pack(side="left", padx=(0, 8))
        NeonButton(more, "Terminar aquí", self.show_summary, color=MUTED, font=F(9, True), padx=10, pady=5).pack(side="left")
        WrapLabel(self.stage, bg=BG, fg=MUTED, font=F(9),
                  text="«Seguros» = riesgo bajo y reversibles. Los de riesgo medio o irreversibles (cerrar procesos, quitar apps) siempre te los pregunto uno a uno.").pack(fill="x", pady=(10, 0))

    def _set_buttons(self, on):
        self.b_apply.set_enabled(on)
        self.b_skip.set_enabled(on)

    def do_apply(self, a):
        if self.busy:
            return
        if a.risk == "alto" and not messagebox.askyesno(
                "Ajuste de riesgo ALTO", f"{a.title}\n\n{getattr(a, 'warning', '')}\n\n"
                "Se puede deshacer desde «Historial / Deshacer», pero mientras esté aplicado tu PC estará menos protegido.\n\n"
                "¿Seguro que quieres aplicarlo?"):
            return
        self.busy = True
        g = self.gen
        self._set_buttons(False)
        self.flash.config(text="Aplicando…", fg=CYAN)
        self.app.bg(lambda: actions.execute(a), lambda r: self.after_apply(g, a, r))

    def after_apply(self, g, a, r):
        self.busy = False
        if g != self.gen:
            return
        if r.ok:
            self.applied.append(a)
            self.need_reboot = self.need_reboot or a.reboot
            self.flash.config(text="✓ " + r.msg, fg=GREEN)
            self.after(650, lambda: self._advance(g))
        else:
            self.failed.append((a, r.msg))
            self.flash.config(text="✗ " + r.msg[:140], fg=RED)
            self._set_buttons(True)
            self.b_apply.set_text("Reintentar")

    def _advance(self, g):
        if g == self.gen:
            self.idx += 1
            self.show_wizard()

    def do_skip(self):
        if self.busy:
            return
        self.skipped += 1
        self.idx += 1
        self.show_wizard()

    def skip_group(self, group):
        while self.idx < len(self.acts) and self.acts[self.idx].group == group:
            self.skipped += 1
            self.idx += 1
        self.show_wizard()

    def apply_safe_rest(self):
        safe = [x for x in self.acts[self.idx:] if x.risk == "bajo" and x.reversible and (not x.needs_admin or is_admin())]
        if not safe or not messagebox.askyesno(
                "Aplicar los seguros", f"Voy a aplicar {len(safe)} cambios de riesgo bajo y reversibles sin preguntar uno a uno.\n"
                "Los demás te los seguiré preguntando.\n\n¿Seguro?"):
            return
        self.busy = True
        g = self.gen
        self._set_buttons(False)

        def work():
            res = []
            for i, a in enumerate(safe, 1):
                self.app.ui(self._flash, g, f"Aplicando {i}/{len(safe)}: {a.title[:60]}…")
                res.append((a, actions.execute(a)))
            return res

        self.app.bg(work, lambda res: self.after_safe(g, safe, res))

    def _flash(self, g, text):
        if g == self.gen:
            self.flash.config(text=text, fg=CYAN)

    def after_safe(self, g, safe, res):
        self.busy = False
        if g != self.gen:
            return
        for a, r in res:
            if r.ok:
                self.applied.append(a)
                self.need_reboot = self.need_reboot or a.reboot
            else:
                self.failed.append((a, r.msg))
        done = {id(a) for a, _ in res}
        self.acts = self.acts[:self.idx] + [x for x in self.acts[self.idx:] if id(x) not in done]
        self.show_wizard()

    # ---- 5. resumen ----------------------------------------------------------
    def show_summary(self):
        self.clear()
        self.heading("¡Listo!", "Esto es lo que ha pasado.")
        c = Card(self.stage, accent=GREEN, title="Resumen")
        c.pack(fill="x")
        left = max(0, len(self.acts) - self.idx)     # pendientes si pulsó «Terminar aquí»
        tk.Label(c.body, text=f"✓ {len(self.applied)} aplicados     ·     {self.skipped + left} omitidos"
                 f"     ·     ✗ {len(self.failed)} con error", font=F(12, True), fg=FG, bg=PANEL, anchor="w").pack(fill="x", pady=(0, 8))
        for a in self.applied[:25]:
            tk.Label(c.body, text="✓  " + a.title, font=F(10), fg=GREEN, bg=PANEL, anchor="w", justify="left", wraplength=800).pack(fill="x")
        if len(self.applied) > 25:
            tk.Label(c.body, text=f"… y {len(self.applied) - 25} más", fg=MUTED, bg=PANEL, font=F(10)).pack(anchor="w")
        for a, msg in self.failed[:10]:
            tk.Label(c.body, text=f"✗  {a.title}: {msg[:120]}", font=F(10), fg=RED, bg=PANEL, anchor="w", justify="left", wraplength=800).pack(fill="x")
        if self.need_reboot:
            WrapLabel(c.body, fg=YELLOW, text="Algunos cambios (ratón, efectos visuales, GPU) se notan al cerrar sesión o reiniciar. "
                                               "El tiempo de arranque de Windows solo se actualiza tras reiniciar.").pack(fill="x", pady=(10, 0))
        if self.profile == "mando":
            import mando
            t = Card(self.stage, accent=PINK, title="Para jugar con mando con el mínimo retraso (lo que de verdad funciona)")
            t.pack(fill="x", pady=(12, 0))
            for tip in mando.CONSEJOS:
                WrapLabel(t.body, text="•  " + tip, fg=FG, font=F(10)).pack(fill="x", pady=2)
        if self.profile == "streaming":
            import streaming
            t = Card(self.stage, accent=YELLOW, title="Para emitir sin perder FPS (lo que de verdad funciona)")
            t.pack(fill="x", pady=(12, 0))
            for tip in streaming.CONSEJOS:
                WrapLabel(t.body, text="•  " + tip, fg=FG, font=F(10)).pack(fill="x", pady=2)
            if not any(a.id == "obs_profile" for a in self.applied):
                WrapLabel(t.body, fg=MUTED, font=F(9),
                          text="No apareció el perfil de OBS: si no tienes OBS Studio instalado (o ya estaba creado), solo se aplicaron los ajustes de Windows.").pack(fill="x", pady=(6, 0))
        row = tk.Frame(self.stage, bg=BG)
        row.pack(fill="x", pady=16)
        NeonButton(row, "Ver historial / deshacer", lambda: self.app.show("history"), color=CYAN, filled=True, padx=16, pady=10).pack(side="left")
        if self.need_reboot and IS_WIN and not DEMO:
            NeonButton(row, "Reiniciar ahora", self.reboot_now, color=YELLOW, padx=16, pady=10).pack(side="left")
        NeonButton(row, "Volver al inicio", self.show_intro, color=MUTED, padx=16, pady=10).pack(side="left", padx=10)

    def reboot_now(self):
        if messagebox.askyesno("Reiniciar", "Guarda tu trabajo. ¿Reiniciar el PC dentro de 10 segundos?"):
            run_cmd(["shutdown", "/r", "/t", "10"])
