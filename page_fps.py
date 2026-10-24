"""Página «FPS reales»: mide los FPS, el 1 % low y la latencia de fotogramas de tu juego, y compara antes/después."""
import threading
import tkinter as tk
from tkinter import messagebox, ttk

import fps
from util import DEMO
from widgets import (BG, CYAN, F, FG, GREEN, MUTED, PANEL, PANEL2, PINK, RED, YELLOW, Card, NeonButton, ScrollFrame, WrapLabel,
                     kv_rows, page_title)

COL = {"green": GREEN, "yellow": YELLOW, "red": RED}


class FpsPage(tk.Frame):
    def __init__(self, parent, app):
        super().__init__(parent, bg=BG)
        self.app = app
        self.busy = False
        self.stop = None
        self.mode = "now"
        self.run_a = self.run_b = None
        self.seconds = 30
        top = tk.Frame(self, bg=BG)
        top.pack(fill="x", padx=26, pady=(22, 6))
        page_title(top, "FPS reales", "Mide los FPS de tu juego y comprueba con números si un cambio ayudó de verdad.",
                   accent=CYAN).pack(anchor="w")
        self.scroll = ScrollFrame(self)
        self.scroll.pack(fill="both", expand=True, padx=(26, 10), pady=(8, 10))
        root = self.scroll.inner

        c = Card(root, accent=YELLOW, title="Cómo se usa (importante para que la medición valga)")
        for t in ("Abre tu juego y ponte en una situación que puedas REPETIR: en VALORANT, el Campo de tiro caminando por la misma ruta; "
                  "en otros juegos, el mismo mapa y el mismo recorrido.",
                  "Elige el juego, pulsa medir y tendrás 5 s para volver al juego (Alt+Tab). Juega con normalidad mientras mide.",
                  "Para comparar, mide dos veces en la MISMA situación. Entre dos mediciones iguales hay ≈3-4 % de variación normal: "
                  "diferencias menores que eso no cuentan.",
                  "Usa PresentMon (gratis, de Intel). Lee los eventos de Windows y no se mete dentro del juego. "
                  "Se descarga una sola vez y se verifica su huella. HellOP debe estar como administrador."):
            WrapLabel(c.body, text="•  " + t, font=F(9), fg=MUTED).pack(fill="x", pady=1)

        sel = Card(root, accent=CYAN, title="¿Qué juego?")
        sel.pack(fill="x", pady=(0, 12))
        row = tk.Frame(sel.body, bg=PANEL)
        row.pack(fill="x")
        self.var = tk.StringVar(value=fps.KNOWN_GAMES[0])
        tk.Entry(row, textvariable=self.var, font=("Consolas", 11), bg=PANEL2, fg=FG, insertbackground=FG, relief="flat",
                 highlightthickness=1, highlightbackground="#1f4a32", highlightcolor=CYAN, width=38).pack(side="left", ipady=6, padx=(0, 10))
        NeonButton(row, "↻  Juegos abiertos", self.refresh_candidates, color=CYAN, padx=14, pady=6, font=F(10, True)).pack(side="left")
        self.chips = tk.Frame(sel.body, bg=PANEL)
        self.chips.pack(fill="x", pady=(8, 0))
        drow = tk.Frame(sel.body, bg=PANEL)
        drow.pack(fill="x", pady=(10, 0))
        tk.Label(drow, text="Duración:", font=F(10), fg=MUTED, bg=PANEL).pack(side="left", padx=(0, 10))
        self.dur_btns = {}
        for s in (30, 60, 90):
            b = NeonButton(drow, f"{s} s", lambda s_=s: self.set_dur(s_), color=MUTED, padx=14, pady=5, font=F(10, True))
            b.pack(side="left", padx=4)
            self.dur_btns[s] = b
        self.set_dur(30)

        modes = tk.Frame(root, bg=BG)
        modes.pack(fill="x", pady=(0, 8))
        self.m_now = NeonButton(modes, "▶  MEDIR AHORA", lambda: self.set_mode("now"), color=PINK, filled=True, font=F(11, True), padx=22, pady=8)
        self.m_now.pack(side="left")
        self.m_ab = NeonButton(modes, "⇄  ASISTENTE ANTES / DESPUÉS", lambda: self.set_mode("ab"), color=MUTED, font=F(11, True), padx=22, pady=8)
        self.m_ab.pack(side="left", padx=10)
        self.msg = tk.Label(modes, text="", font=F(10), fg=MUTED, bg=BG, anchor="w")
        self.msg.pack(side="left", padx=10, fill="x", expand=True)
        self.pb = ttk.Progressbar(root, style="Neon.Horizontal.TProgressbar", mode="determinate", maximum=100, length=420)

        self.f_now = tk.Frame(root, bg=BG)
        self.f_ab = tk.Frame(root, bg=BG)
        # --- modo medir ahora
        self.b_go = NeonButton(self.f_now, "▶  EMPEZAR MEDICIÓN", lambda: self.measure("now"), color=PINK, filled=True, font=F(12, True), padx=28, pady=10)
        self.b_go.pack(anchor="w", pady=(0, 8))
        self.now_res = tk.Frame(self.f_now, bg=BG)
        self.now_res.pack(fill="x")
        # --- modo asistente
        WrapLabel(self.f_ab, bg=BG, fg=MUTED, font=F(10),
                  text="1) Mide ANTES (A).   2) Haz el cambio que quieras probar: un tweak, un ajuste del juego, un driver…   "
                       "3) Mide DESPUÉS (B) en la misma situación.   4) Te digo si de verdad ayudó.").pack(fill="x", pady=(0, 8))
        ab = tk.Frame(self.f_ab, bg=BG)
        ab.pack(fill="x")
        self.b_a = NeonButton(ab, "1 · MEDIR ANTES (A)", lambda: self.measure("a"), color=CYAN, filled=True, font=F(11, True), padx=20, pady=8)
        self.b_a.pack(side="left")
        self.b_b = NeonButton(ab, "3 · MEDIR DESPUÉS (B)", lambda: self.measure("b"), color=GREEN, filled=True, font=F(11, True), padx=20, pady=8)
        self.b_b.pack(side="left", padx=10)
        self.b_b.set_enabled(False)
        NeonButton(ab, "Empezar de nuevo", self.reset_ab, color=MUTED, padx=14, pady=8, font=F(10, True)).pack(side="left")
        go = tk.Frame(self.f_ab, bg=BG)
        go.pack(fill="x", pady=(8, 0))
        tk.Label(go, text="2) Cambiar algo:", font=F(10), fg=MUTED, bg=BG).pack(side="left", padx=(0, 8))
        for k, label in (("tweaks", "Tweaks"), ("gameprof", "Ajustes de juego"), ("hidden", "Rendimiento oculto")):
            NeonButton(go, label, lambda k_=k: self.app.show(k_), color=CYAN, padx=12, pady=5, font=F(9, True)).pack(side="left", padx=3)
        self.ab_res = tk.Frame(self.f_ab, bg=BG)
        self.ab_res.pack(fill="x", pady=(8, 0))

        self.hist = tk.Frame(root, bg=BG)
        self.hist.pack(fill="x", pady=(14, 14))
        self.set_mode("now")
        self.render_history()
        c.pack(fill="x", pady=(0, 14))          # la explicación va al final para que los resultados se vean arriba

    # ------------------------------------------------------------------
    def on_show(self):
        self.refresh_candidates()

    def set_dur(self, s):
        self.seconds = s
        for k, b in self.dur_btns.items():
            b.set_color(PINK if k == s else MUTED)

    def set_mode(self, mode):
        self.mode = mode
        self.f_now.pack_forget()
        self.f_ab.pack_forget()
        (self.f_now if mode == "now" else self.f_ab).pack(fill="x", before=self.hist)
        self.m_now.set_color(PINK if mode == "now" else MUTED)
        self.m_ab.set_color(PINK if mode == "ab" else MUTED)

    def refresh_candidates(self):
        for w in self.chips.winfo_children():
            w.destroy()
        names = fps.running_candidates()
        if names and names[0] in fps.KNOWN_GAMES:
            self.var.set(names[0])
        for n in names[:6]:
            NeonButton(self.chips, n, lambda n_=n: self.var.set(n_), color=GREEN if n in fps.KNOWN_GAMES else MUTED, padx=10, pady=4,
                       font=F(9, True)).pack(side="left", padx=(0, 6), pady=2)

    def reset_ab(self):
        self.run_a = self.run_b = None
        self.b_b.set_enabled(False)
        for w in self.ab_res.winfo_children():
            w.destroy()

    # ------------------------------------------------------------------
    def measure(self, slot):
        if self.busy:
            if self.stop:
                self.stop.set()
            return
        proc = self.var.get().strip()
        if not proc.lower().endswith(".exe"):
            self.msg.config(text="Escribe el nombre del programa del juego, por ejemplo VALORANT-Win64-Shipping.exe", fg=YELLOW)
            return
        if not DEMO and not fps.have_presentmon() and not messagebox.askyesno(
                "Descargar PresentMon", "Para medir FPS hace falta PresentMon, una herramienta gratuita de Intel (≈1 MB).\n\n"
                "Se descarga una sola vez de GitHub y se comprueba su huella SHA256 antes de usarla.\n\n¿Descargarla ahora?"):
            return
        self.busy, self.stop = True, threading.Event()
        for b in (self.b_go, self.b_a, self.b_b):
            b.set_text("■  Cancelar") if b is {"now": self.b_go, "a": self.b_a, "b": self.b_b}[slot] else b.set_enabled(False)
        self.pb["value"] = 0
        self.pb.pack(anchor="w", pady=(0, 6), before=self.f_now if self.mode == "now" else self.f_ab)
        variant = 1 if slot == "b" else 0
        sec, stop = self.seconds, self.stop

        def work():
            fps.ensure_presentmon(lambda p, m: self.app.ui(self._prog, p * 0.0, m))
            for i in range(5, 0, -1):
                if stop.is_set():
                    raise fps.FpsError("Medición cancelada")
                self.app.ui(self._prog, 0, f"Vuelve al juego (Alt+Tab): empiezo en {i}…")
                import time
                time.sleep(1)
            ft, g, c = fps.capture(proc, sec, lambda p, m: self.app.ui(self._prog, p, m), stop, variant)
            return fps.analyze(ft, g, c)

        self.app.bg(work, lambda m: self._done(slot, proc, m), self._fail)

    def _prog(self, p, m):
        self.pb["value"] = int(p * 100)
        self.msg.config(text=m, fg=CYAN)

    def _restore_buttons(self):
        self.busy, self.stop = False, None
        self.pb.pack_forget()
        self.b_go.set_text("▶  EMPEZAR MEDICIÓN")
        self.b_a.set_text("1 · MEDIR ANTES (A)")
        self.b_b.set_text("3 · MEDIR DESPUÉS (B)")
        self.b_go.set_enabled(True)
        self.b_a.set_enabled(True)
        self.b_b.set_enabled(self.run_a is not None)

    def _fail(self, e):
        self._restore_buttons()
        self.msg.config(text=("✗ " + str(e)) if isinstance(e, fps.FpsError) else f"✗ Error: {type(e).__name__}: {e}", fg=RED)

    def _done(self, slot, proc, m):
        self._restore_buttons()
        self.msg.config(text="✓ Medición terminada", fg=GREEN)
        fps.save_run(proc, m, {"now": "", "a": "A (antes)", "b": "B (después)"}[slot])
        if slot == "now":
            self._show(self.now_res, m, "Resultado")
        elif slot == "a":
            self.run_a = m
            self.b_b.set_enabled(True)
            self._show(self.ab_res, m, "A · ANTES")
            tk.Label(self.ab_res, text="Ahora cambia lo que quieras probar y mide DESPUÉS (B) en la misma situación.", font=F(10, True),
                     fg=YELLOW, bg=BG).pack(anchor="w", pady=(4, 0))
        else:
            self.run_b = m
            self._show(self.ab_res, self.run_a, "A · ANTES")
            self._show(self.ab_res, m, "B · DESPUÉS", keep=True)
            self._compare()
        self.render_history()

    # ------------------------------------------------------------------
    def _show(self, parent, m, title, keep=False):
        if not keep:
            for w in parent.winfo_children():
                w.destroy()
        c = Card(parent, accent=PINK, title=title)
        c.pack(fill="x", pady=(0, 8))
        big = tk.Frame(c.body, bg=PANEL)
        big.pack(fill="x", pady=(0, 6))
        for label, val, unit, col in (("FPS medios", m["avg"], "", CYAN), ("1 % low", m["low1"], "", YELLOW), ("0,1 % low", m["low01"], "", RED)):
            b = tk.Frame(big, bg=PANEL)
            b.pack(side="left", padx=(0, 30))
            tk.Label(b, text=f"{val:.0f}", font=F(28, True), fg=col, bg=PANEL).pack(anchor="w")
            tk.Label(b, text=label, font=F(9), fg=MUTED, bg=PANEL).pack(anchor="w")
        kv_rows(c.body, [("Fotograma típico", f"{m['ft_med']} ms"),
                         ("El 1 % más lento tarda", f"{m['ft_p99']} ms o más"),
                         ("El peor fotograma", f"{m['ft_max']} ms"),
                         ("Tirones fuertes", f"{m['stutters']} en {m['seconds']:.0f} s  ({m['stutter_per_min']}/min)")], key_width=20)
        if m.get("verdict"):
            WrapLabel(c.body, text="→ " + m["verdict"], font=F(10, True), fg=FG).pack(fill="x", pady=(8, 0))

    def _compare(self):
        txt, col, d = fps.compare(self.run_a, self.run_b)
        c = Card(self.ab_res, accent=COL[col], title="Comparación A → B")
        c.pack(fill="x", pady=(0, 8))
        WrapLabel(c.body, text=txt, font=F(11, True), fg=COL[col]).pack(fill="x", pady=(0, 6))
        sg = lambda v: f"{v:+.1f} %"  # noqa: E731
        kv_rows(c.body, [("FPS medios", sg(d["avg"])), ("1 % low", sg(d["low1"])), ("0,1 % low", sg(d["low01"])),
                         ("Tirones fuertes", f"{d['stutters']:+d}")], key_width=20)

    def render_history(self):
        for w in self.hist.winfo_children():
            w.destroy()
        h = fps.load_history()[-8:][::-1]
        if not h:
            return
        c = Card(self.hist, accent=MUTED, title="Últimas mediciones")
        c.pack(fill="x")
        for r in h:
            line = f"{r['ts']}   {r['process'][:26]:<26}  {r['avg']:>6.0f} FPS   1 % low {r['low1']:>5.0f}   0,1 % low {r['low01']:>5.0f}   {r.get('label', '')}"
            tk.Label(c.body, text=line, font=("Consolas", 9), fg=MUTED, bg=PANEL, anchor="w").pack(fill="x")
