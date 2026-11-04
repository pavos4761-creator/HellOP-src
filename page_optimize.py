"""Página «Optimizar»: elige perfil → punto de restauración → te pregunta
cada cambio uno por uno → resumen."""
import tkinter as tk
from tkinter import messagebox, ttk

import actions
import cuadros
from util import IS_WIN, DEMO, is_admin, run_cmd
from widgets import (BG, BORDER, CYAN, F, FG, GREEN, MUTED, PANEL, PINK, RED, VIOLET, YELLOW, Card, NeonButton,
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
     "Todo lo anterior junto. Revisaré todo lo que se puede mejorar en tu PC y te lo enseño en cuadrados para que marques lo que quieras."),
]


def _medir():
    """RAM en uso y número de procesos (para enseñar el antes y el después de una limpieza)."""
    try:
        import psutil
        return {"ram": psutil.virtual_memory().used / 1024 ** 3, "procs": len(psutil.pids())}
    except Exception:  # noqa: BLE001
        return None


class OptimizePage(tk.Frame):
    def __init__(self, parent, app):
        super().__init__(parent, bg=BG)
        self.app = app
        self.gen = 0
        self.v_restore = tk.BooleanVar(value=True)
        self.scroll = ScrollFrame(self)              # si la ventana es pequeña, sale una barra para subir y bajar
        self.scroll.pack(fill="both", expand=True, padx=(26, 10), pady=(20, 10))
        self.stage = self.scroll.inner
        self.barra = None
        self.cuadros = []
        self._restore_hecho = False
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
        self.mostrar_barra(False)
        for w in self.stage.winfo_children():
            w.destroy()
        self.scroll.canvas.yview_moveto(0)

    def heading(self, title, sub=None):
        page_title(self.stage, title, sub, accent=PINK).pack(anchor="w", pady=(0, 12))

    # ---- 1. entrada: directamente los cuadrados -------------------------------
    perfiles = True      # MandoPage y StreamingPage lo ponen a False (tienen su propio perfil)

    def show_intro(self):
        self.start(self.profile or "full")

    def _chips(self, actual):
        fila = tk.Frame(self.stage, bg=BG)
        fila.pack(fill="x", pady=(0, 12))
        tk.Label(fila, text="Nivel:", font=F(9, True), fg=MUTED, bg=BG).pack(side="left", padx=(0, 8))
        for key, icon, name, color, desc in PROFILES:
            on = key == actual
            b = NeonButton(fila, name.title(), (lambda k=key: self.start(k)) if not on else (lambda: None), color=color if on else MUTED,
                           filled=on, font=F(9, True), padx=12, pady=5)
            b.pack(side="left", padx=(0, 6))

    def _esqueleto(self):
        """Cuadrados vacíos mientras se mira tu PC: así la pantalla ya tiene su forma y solo se rellenan."""
        self._sk = tk.Frame(self.stage, bg=BG)
        self._sk.pack(fill="x")
        for i in range(3):
            self._sk.columnconfigure(i, weight=1, uniform="c")
        for k in range(6):
            c = tk.Frame(self._sk, bg=PANEL, highlightthickness=2, highlightbackground=BORDER, height=190)
            c.grid(row=k // 3, column=k % 3, sticky="nsew", padx=(0, 12) if k % 3 < 2 else 0, pady=(0, 12))
            c.grid_propagate(False)
            tk.Frame(c, bg=BORDER, width=40, height=40).place(x=14, y=14)
            tk.Frame(c, bg=BORDER, width=120, height=12).place(x=14, y=72)
            tk.Frame(c, bg=BORDER, width=200, height=9).place(x=14, y=100)
            tk.Frame(c, bg=BORDER, width=160, height=9).place(x=14, y=118)

    # ---- 2. buscar ----------------------------------------------------------
    def start(self, profile):
        self.reset_state()
        self.profile = profile
        self.clear()
        self.heading("Optimizar" if self.perfiles else "Optimizaciones", "Mirando tu PC… los cuadrados aparecen en un momento.")
        if self.perfiles:
            self._chips(profile)
        self.scan_msg = tk.Label(self.stage, text="Empezando…", font=F(9), fg=CYAN, bg=BG, anchor="w")
        self.scan_msg.pack(anchor="w", pady=(0, 10))
        self._esqueleto()
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
            self.heading("Tu PC ya está muy bien", "No encontré nada que mejorar para este nivel.")
            if self.perfiles:
                self._chips(self.profile)
            return
        self.acts = acts
        self._restore_hecho = False
        self.show_grid()

    # ---- 3. cuadrícula: cada optimización en su cuadrado --------------------
    def show_grid(self):
        self.clear()
        g = self.gen
        acts = self.acts
        self.cuadros = []
        n = len(acts)
        self.heading(f"{n} optimizaciones para tu PC", "Marca con el interruptor y aplica juntas, o pulsa «Aplicar» en una sola. Solo sale lo que está sin hacer en tu PC.")
        if self.perfiles:
            self._chips(self.profile)
        if not is_admin():
            c = Card(self.stage, accent=RED)
            c.pack(fill="x", pady=(0, 12))
            WrapLabel(c.body, fg=YELLOW, text="Estás sin permisos de administrador: lo que toca servicios, energía, red o el registro del sistema no se podrá aplicar. "
                                              "Usa «Reabrir como administrador» arriba a la derecha.").pack(fill="x")
        # paquetes de un clic
        packs = cuadros.paquetes_utiles(acts)
        if packs:
            tk.Label(self.stage, text="Paquetes de un clic", font=F(13, True), fg=FG, bg=BG, anchor="w").pack(fill="x", pady=(2, 8))
            fila = tk.Frame(self.stage, bg=BG)
            fila.pack(fill="x", pady=(0, 6))
            cols = min(4, len(packs))
            for i in range(cols):
                fila.columnconfigure(i, weight=1, uniform="pk")
            for i, d in enumerate(packs[:4]):
                cuadros.Paquete(fila, self, d, acts).grid(row=0, column=i, sticky="nsew", padx=(0, 12) if i < cols - 1 else 0)
        # herramientas
        tools = tk.Frame(self.stage, bg=BG)
        tools.pack(fill="x", pady=(14, 6))
        tk.Label(tools, text="Todas las optimizaciones", font=F(13, True), fg=FG, bg=BG).pack(side="left")
        NeonButton(tools, "Marcar las seguras", self.marca_seguras, color=CYAN, font=F(9, True), padx=12, pady=5).pack(side="right")
        NeonButton(tools, "Quitar marcas", self.quita_marcas, color=MUTED, font=F(9, True), padx=12, pady=5).pack(side="right", padx=(0, 8))
        self.zona = tk.Frame(self.stage, bg=BG)
        self.zona.pack(fill="x")
        # grupos en orden; los cuadros se crean por tandas para que la pantalla no se quede congelada
        orden = []
        for a in acts:
            if a.group not in orden:
                orden.append(a.group)
        self._cola = [(gr, [a for a in acts if a.group == gr]) for gr in orden]
        self._tanda(g)
        self.mostrar_barra(True)
        self.actualiza_barra()

    def _tanda(self, g, hechos=0):
        if g != self.gen:
            return
        creados = 0
        while self._cola and creados < 6:
            gr, lista = self._cola[0]
            if not getattr(self, "_grid_actual", None) or self._grid_actual[0] != gr:
                cab = tk.Frame(self.zona, bg=BG)
                cab.pack(fill="x", pady=(10, 6))
                tk.Label(cab, text=actions.GROUP_NAMES.get(gr, gr).upper(), font=F(9, True), fg=MUTED, bg=BG).pack(side="left")
                tk.Label(cab, text=f"{len(lista)}", font=F(9, True), fg=cuadros.VISUAL.get(gr, ("", CYAN))[1], bg=BG).pack(side="left", padx=8)
                lk = tk.Label(cab, text="marcar grupo", font=F(9, True), fg=CYAN, bg=BG, cursor="hand2")
                lk.pack(side="left")
                lk.bind("<Button-1>", lambda e, gr=gr: self.marca_grupo(gr))
                grid = tk.Frame(self.zona, bg=BG)
                grid.pack(fill="x")
                for i in range(3):
                    grid.columnconfigure(i, weight=1, uniform="c")
                self._grid_actual = (gr, grid, 0)
            _g, grid, k = self._grid_actual
            a = lista.pop(0)
            c = cuadros.Cuadro(grid, self, a)
            c.grid(row=k // 3, column=k % 3, sticky="nsew", padx=(0, 12) if k % 3 < 2 else 0, pady=(0, 12))
            self.cuadros.append(c)
            self._grid_actual = (gr, grid, k + 1)
            creados += 1
            if not lista:
                self._cola.pop(0)
                self._grid_actual = None
        if self._cola:
            self.after(1, lambda: self._tanda(g))

    # ---- selección ----
    def marca_seguras(self):
        for c in self.cuadros:
            c.poner_sel(c.a.risk == "bajo" and c.a.reversible and (not c.a.needs_admin or is_admin()))
        self.actualiza_barra()

    def quita_marcas(self):
        for c in self.cuadros:
            c.poner_sel(False)
        self.actualiza_barra()

    def marca_grupo(self, gr):
        for c in self.cuadros:
            if c.a.group == gr:
                c.poner_sel(True)
        self.actualiza_barra()

    def marca_paquete(self, sel):
        ids = {id(a) for a in cuadros.paquete_acciones(sel, self.acts)}
        for c in self.cuadros:
            c.poner_sel(id(c.a) in ids)
        self.actualiza_barra()

    def aplica_paquete(self, sel):
        ids = {id(a) for a in cuadros.paquete_acciones(sel, self.acts)}
        lista = [c for c in self.cuadros if id(c.a) in ids and c.estado in ("idle", "bad")]
        if lista and messagebox.askyesno("Aplicar paquete", f"Voy a aplicar {len(lista)} ajustes (todos de riesgo bajo o medio y reversibles).\n\n¿Seguro?"):
            self.aplicar(lista, confirmado=True)

    # ---- barra de abajo ----
    def _crea_barra(self):
        self.barra = tk.Frame(self, bg=PANEL, highlightthickness=1, highlightbackground=BORDER)
        izq = tk.Frame(self.barra, bg=PANEL)
        izq.pack(side="left", padx=(18, 0), pady=10)
        self.lbl_sel = tk.Label(izq, text="", font=F(11, True), fg=FG, bg=PANEL, anchor="w")
        self.lbl_sel.pack(anchor="w")
        self.lbl_res = tk.Label(izq, text="", font=F(9), fg=MUTED, bg=PANEL, anchor="w", justify="left")
        self.lbl_res.pack(anchor="w")
        der = tk.Frame(self.barra, bg=PANEL)
        der.pack(side="right", padx=(0, 18), pady=10)
        self.b_apl = NeonButton(der, "Aplicar seleccionadas", lambda: self.aplicar([c for c in self.cuadros if c.sel()]), color=GREEN, filled=True,
                                font=F(11, True), padx=22, pady=9)
        self.b_apl.pack(side="right")
        self.b_fin = NeonButton(der, "Terminar", self.show_summary, color=MUTED, font=F(10, True), padx=16, pady=8)
        self.b_fin.pack(side="right", padx=(0, 10))
        self.b_reb = NeonButton(der, "Reiniciar ahora", self.reboot_now, color=YELLOW, font=F(10, True), padx=16, pady=8)
        mid = tk.Frame(self.barra, bg=PANEL)
        mid.pack(side="right", padx=20)
        checkbox(mid, "Punto de restauración", self.v_restore, bg=PANEL).pack()

    def mostrar_barra(self, si):
        if si:
            if not getattr(self, "barra", None):
                self._crea_barra()
            self.barra.pack(side="bottom", fill="x", before=self.scroll)
        elif getattr(self, "barra", None):
            self.barra.pack_forget()

    def actualiza_barra(self):
        n = sum(1 for c in self.cuadros if c.sel())
        self.lbl_sel.config(text=f"{n} seleccionada{'s' if n != 1 else ''}" if n else "Ninguna seleccionada")
        self.b_apl.set_text(f"Aplicar seleccionadas ({n})" if n else "Aplicar seleccionadas")
        self.b_apl.set_enabled(n > 0 and not self.busy)
        done = len(self.applied)
        if done and not self.busy:
            self.lbl_res.config(text=f"✓ {done} aplicadas" + (f"  ·  ✗ {len(self.failed)} con error" if self.failed else "") +
                                ("  ·  reinicia para notar todos los cambios" if self.need_reboot else ""), fg=GREEN if not self.failed else YELLOW)
        if self.need_reboot and IS_WIN and not DEMO:
            self.b_reb.pack(side="right", padx=(0, 10))

    # ---- 4. aplicar -------------------------------------------------------------
    def aplicar(self, lista, confirmado=False):
        lista = [c for c in lista if c.estado in ("idle", "bad")]
        if self.busy or not lista:
            return
        altos = [c for c in lista if c.a.risk == "alto"]
        if altos and not confirmado:
            txt = "\n\n".join(f"{c.a.title}\n{getattr(c.a, 'warning', '')}" for c in altos[:3])
            if not messagebox.askyesno("Ajustes de riesgo ALTO", txt + "\n\nSe pueden deshacer desde «Historial / Deshacer», pero mientras estén aplicados "
                                       "tu PC estará menos protegido.\n\n¿Seguro que quieres aplicarlos?"):
                lista = [c for c in lista if c.a.risk != "alto"]
                if not lista:
                    return
        self.busy = True
        g = self.gen
        self.b_apl.set_enabled(False)
        quiere_restore = self.v_restore.get() and not self._restore_hecho
        limpia = any(c.a.group in ("startup", "services", "bloat", "procs", "deep") for c in lista)
        for c in lista:
            c.corriendo()

        def work():
            antes = _medir() if limpia else None
            if quiere_restore:
                self.app.ui(self._res, g, "Creando el punto de restauración de Windows (puede tardar un minuto)…")
                ok, msg = actions.create_restore_point()
                self._restore_hecho = True
                if not ok:
                    self.app.ui(self._res, g, "No pude crear el punto de restauración; sigo igualmente (todo se puede deshacer desde el Historial).")
            res = []
            for i, c in enumerate(lista, 1):
                self.app.ui(self._res, g, f"Aplicando {i} de {len(lista)}: {c.a.title[:70]}…")
                r = actions.execute(c.a)
                res.append((c, r))
                self.app.ui(self._uno, g, c, r)
            despues = None
            if antes:
                import time
                time.sleep(2.5)
                despues = _medir()
            return res, antes, despues

        self.app.bg(work, lambda out: self._fin_lote(g, out))

    def _res(self, g, texto):
        if g == self.gen:
            self.lbl_res.config(text=texto, fg=CYAN)

    def _uno(self, g, c, r):
        if g != self.gen:
            return
        c.fin(r)
        if r.ok:
            self.applied.append(c.a)
            self.need_reboot = self.need_reboot or c.a.reboot
        else:
            self.failed.append((c.a, r.msg))

    def _fin_lote(self, g, out):
        self.busy = False
        if g != self.gen:
            return
        _res, antes, despues = out
        self.actualiza_barra()
        extra = ""
        if antes and despues:
            extra = (f"   ·   RAM en uso: {antes['ram']:.1f} → {despues['ram']:.1f} GB   ·   procesos: {antes['procs']} → {despues['procs']}")
        self.lbl_res.config(text=self.lbl_res.cget("text") + extra, fg=GREEN if not self.failed else YELLOW)
        self.app.toast(f"{len(_res)} ajustes procesados", GREEN if not self.failed else YELLOW) if hasattr(self.app, "toast") else None

    # ---- 5. resumen ----------------------------------------------------------
    def show_summary(self):
        self.clear()
        self.heading("¡Listo!", "Esto es lo que ha pasado.")
        c = Card(self.stage, accent=GREEN, title="Resumen")
        c.pack(fill="x")
        sin = max(0, len(self.acts) - len(self.applied) - len(self.failed))      # los que dejó sin marcar
        tk.Label(c.body, text=f"✓ {len(self.applied)} aplicados     ·     {sin} sin aplicar"
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
