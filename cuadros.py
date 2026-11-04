"""Cuadrados de optimización (cada ajuste en su propio cuadro, con interruptor y botón «Aplicar») y paquetes de un clic."""
import tkinter as tk

import actions
import anim
from util import is_admin
from widgets import (BORDER, CYAN, F, FG, GREEN, MUTED, PANEL, PINK, RED, TRACK, VIOLET, YELLOW, Card, NeonButton, WrapLabel, badge, mix,
                     round_rect)

# icono y color de cada grupo
VISUAL = {
    "power": ("⚡", YELLOW), "speed": ("▶", CYAN), "gaming": ("▣", PINK), "latency": ("◎", CYAN), "advanced": ("✦", VIOLET),
    "gpu": ("▤", PINK), "deep": ("✧", VIOLET), "tradeoff": ("☢", RED), "startup": ("⏻", YELLOW), "services": ("⚙", CYAN),
    "bloat": ("✖", RED), "procs": ("▦", YELLOW), "network": ("≈", GREEN), "mando": ("✜", PINK), "streaming": ("◉", YELLOW),
}

# paquetes de un clic: (id, icono, nombre, color, texto, qué ajustes entran)
PAQUETES = [
    ("seguro", "✔", "Todo lo seguro", GREEN, "Solo ajustes de riesgo bajo que se pueden deshacer. Lo que haría yo sin pensarlo.",
     lambda a: a.risk == "bajo" and a.reversible),
    ("latencia", "◎", "Menos latencia", CYAN, "Reloj del sistema, red, energía y arranque: que todo responda al instante.",
     lambda a: a.group in ("latency", "advanced", "power", "network") and a.risk != "alto" and a.reversible),
    ("fps", "▣", "Más FPS", PINK, "Prioridades de juego, gráfica y energía para subir los mínimos y quitar tirones.",
     lambda a: a.group in ("gaming", "gpu", "power") and a.risk != "alto" and a.reversible),
    ("limpieza", "✦", "Limpieza de fondo", YELLOW, "Programas de inicio, servicios y basura de Windows que consumen sin que lo sepas.",
     lambda a: a.group in ("startup", "services", "bloat", "deep") and a.risk != "alto" and a.reversible),
]


def paquete_acciones(sel, acts):
    ok_admin = is_admin()
    return [a for a in acts if sel(a) and (ok_admin or not a.needs_admin)]


def paquetes_utiles(acts):
    """Paquetes con algo que aplicar, sin repetir dos que traen exactamente lo mismo."""
    vistos, out = [], []
    for pid, ico, nombre, color, texto, sel in PAQUETES:
        ids = tuple(sorted(id(a) for a in paquete_acciones(sel, acts)))
        if not ids or ids in vistos:
            continue
        vistos.append(ids)
        out.append((pid, ico, nombre, color, texto, sel))
    return out


# ---------------------------------------------------------------------------------- interruptor
class Interruptor(tk.Canvas):
    W, H = 44, 24

    def __init__(self, parent, on_change, bg=PANEL):
        super().__init__(parent, width=self.W, height=self.H, bg=bg, highlightthickness=0, bd=0, cursor="hand2")
        self.on, self.t, self.cmd, self.enabled, self._cancel = False, 0.0, on_change, True, None
        self.bind("<Button-1>", lambda e: self.alterna())
        self._dibuja()

    def alterna(self):
        if self.enabled:
            self.poner(not self.on)
            self.cmd(self.on)

    def poner(self, on, anima=True):
        if on == self.on:
            return
        self.on = on
        if self._cancel:
            self._cancel()
        if anima and anim.ENABLED:
            t0 = self.t
            self._cancel = anim.tween(self, 150, lambda p: self._set(t0 + ((1.0 if on else 0.0) - t0) * p))
        else:
            self._set(1.0 if on else 0.0)

    def bloquea(self, si):
        self.enabled = not si
        self.config(cursor="arrow" if si else "hand2")

    def _set(self, t):
        self.t = t
        self._dibuja()

    def _dibuja(self):
        try:
            self.delete("all")
            col = mix(TRACK, CYAN, self.t)
            round_rect(self, 1, 3, self.W - 1, self.H - 3, 10, fill=col if self.enabled else mix(col, PANEL, 0.5), outline="")
            x = 4 + self.t * (self.W - 8 - 16)
            self.create_oval(x, self.H / 2 - 8, x + 16, self.H / 2 + 8, fill="#ffffff", outline=mix(col, "#000000", 0.1))
        except tk.TclError:
            pass


# ---------------------------------------------------------------------------------- cuadro
class Cuadro(tk.Frame):
    def __init__(self, parent, page, a):
        super().__init__(parent, bg=PANEL, highlightthickness=2, highlightbackground=BORDER, highlightcolor=BORDER)
        self.page, self.a, self.estado, self.largo = page, a, "idle", False
        glifo, color = VISUAL.get(a.group, ("•", CYAN))
        self.color = color
        cab = tk.Frame(self, bg=PANEL)
        cab.pack(fill="x", padx=14, pady=(14, 0))
        ic = tk.Canvas(cab, width=40, height=40, bg=PANEL, highlightthickness=0, bd=0)
        round_rect(ic, 1, 1, 39, 39, 13, fill=mix(PANEL, color, 0.14), outline="")
        ic.create_text(20, 20, text=glifo, fill=color, font=F(15, True))
        ic.pack(side="left")
        self.sw = Interruptor(cab, lambda on: self._cambia())
        self.sw.pack(side="right")
        WrapLabel(self, text=a.title, font=F(11, True)).pack(fill="x", padx=14, pady=(10, 0))
        if getattr(a, "status", ""):
            WrapLabel(self, text=a.status, font=("Consolas", 8), fg=color if color != YELLOW else MUTED).pack(fill="x", padx=14, pady=(4, 0))
        self.texto_corto = a.desc if len(a.desc) <= 125 else a.desc[:122].rsplit(" ", 1)[0] + "…"
        self.d = WrapLabel(self, text=self.texto_corto, fg=MUTED, font=F(9))
        self.d.pack(fill="x", padx=14, pady=(6, 0))
        if len(a.desc) > 125 or getattr(a, "warning", ""):
            self.mas = tk.Label(self, text="Ver más ▾", font=F(8, True), fg=CYAN, bg=PANEL, cursor="hand2", anchor="w")
            self.mas.pack(fill="x", padx=14, pady=(2, 0))
            self.mas.bind("<Button-1>", lambda e: self._largo())
        else:
            self.mas = None
        tags = tk.Frame(self, bg=PANEL)
        tags.pack(fill="x", padx=14, pady=(10, 0))
        t2 = tk.Frame(self, bg=PANEL)
        t2.pack(fill="x", padx=14, pady=(4, 0))
        rt, rc = {"bajo": ("RIESGO BAJO", GREEN), "medio": ("RIESGO MEDIO", YELLOW), "alto": ("RIESGO ALTO", RED)}.get(a.risk, ("RIESGO MEDIO", YELLOW))
        badge(tags, rt, rc, bg=PANEL).pack(side="left", padx=(0, 5))
        ef = {"real": ("EFECTO REAL", GREEN), "pequeño": ("EFECTO PEQUEÑO", YELLOW), "depende": ("DEPENDE DE TU PC", CYAN),
              "mínimo": ("CASI NULO", MUTED)}.get(getattr(a, "effect", ""))
        if ef:
            badge(tags, *ef, bg=PANEL).pack(side="left", padx=(0, 5))
        if a.reboot:
            badge(t2, "↻ REINICIO", VIOLET, bg=PANEL).pack(side="left", padx=(0, 5))
        if not a.reversible:
            badge(t2, "NO SE DESHACE", YELLOW, bg=PANEL).pack(side="left", padx=(0, 5))
        if a.needs_admin and not is_admin():
            badge(t2, "NECESITA ADMIN", RED, bg=PANEL).pack(side="left", padx=(0, 5))
        tk.Frame(self, bg=PANEL).pack(fill="both", expand=True)
        pie = tk.Frame(self, bg=PANEL)
        pie.pack(fill="x", padx=14, pady=(12, 14), side="bottom")
        self.btn = NeonButton(pie, "Aplicar", lambda: self.page.aplicar([self]), color=color if color != YELLOW else CYAN, font=F(9, True), padx=14, pady=5)
        self.btn.pack(side="left")
        self.msg = tk.Label(pie, text="", font=F(9, True), bg=PANEL, fg=MUTED, anchor="w", justify="left")
        self.msg.pack(side="left", padx=(10, 0), fill="x", expand=True)

    # ---- selección ----
    def sel(self):
        return self.sw.on and self.estado in ("idle", "bad")

    def poner_sel(self, on):
        if self.estado in ("run", "ok"):
            return
        self.sw.poner(on)
        self._borde()

    def _cambia(self):
        self._borde()
        self.page.actualiza_barra()

    def _borde(self):
        col = CYAN if self.sw.on and self.estado in ("idle", "bad") else GREEN if self.estado == "ok" else RED if self.estado == "bad" else BORDER
        self.config(highlightbackground=col, highlightcolor=col)

    def _largo(self):
        self.largo = not self.largo
        txt = self.a.desc + (("\n\n⚠  " + self.a.warning) if getattr(self.a, "warning", "") else "")
        self.d.config(text=txt if self.largo else self.texto_corto, fg=FG if self.largo else MUTED)
        if self.mas:
            self.mas.config(text="Ver menos ▴" if self.largo else "Ver más ▾")

    # ---- estados ----
    def corriendo(self):
        self.estado = "run"
        self.sw.bloquea(True)
        self.btn.set_enabled(False)
        self.msg.config(text="Aplicando…", fg=CYAN)
        self.config(highlightbackground=CYAN, highlightcolor=CYAN)

    def fin(self, r):
        if r.ok:
            self.estado = "ok"
            self.sw.poner(False, anima=False)
            self.sw.bloquea(True)
            self.btn.pack_forget()
            self.msg.config(text="✓ Aplicado", fg=GREEN)
        else:
            self.estado = "bad"
            self.sw.bloquea(False)
            self.btn.set_enabled(True)
            self.btn.set_text("Reintentar")
            self.msg.config(text="✗ " + r.msg[:60], fg=RED)
        self._borde()


# ---------------------------------------------------------------------------------- paquete grande
class Paquete(Card):
    def __init__(self, parent, page, datos, acts):
        pid, ico, nombre, color, texto, sel = datos
        super().__init__(parent, accent=color)
        self.page, self.sel_fn = page, sel
        n = len(paquete_acciones(sel, acts))
        fila = tk.Frame(self.body, bg=PANEL)
        fila.pack(fill="x")
        ic = tk.Canvas(fila, width=44, height=44, bg=PANEL, highlightthickness=0, bd=0)
        round_rect(ic, 1, 1, 43, 43, 14, fill=color, outline="")
        ic.create_text(22, 22, text=ico, fill="#ffffff", font=F(17, True))
        ic.pack(side="left")
        col = tk.Frame(fila, bg=PANEL)
        col.pack(side="left", padx=(10, 0))
        tk.Label(col, text=nombre, font=F(12, True), fg=FG, bg=PANEL, anchor="w").pack(anchor="w")
        tk.Label(col, text=f"{n} ajuste{'s' if n != 1 else ''}", font=F(9, True), fg=color if color != YELLOW else MUTED, bg=PANEL, anchor="w").pack(anchor="w")
        WrapLabel(self.body, text=texto, fg=MUTED, font=F(9)).pack(fill="x", pady=(8, 0))
        pie = tk.Frame(self.body, bg=PANEL)
        pie.pack(fill="x", pady=(10, 0))
        NeonButton(pie, "Aplicar", lambda: page.aplica_paquete(sel), color=color if color != YELLOW else CYAN, filled=True, font=F(9, True),
                   padx=12, pady=6).pack(side="left")
        NeonButton(pie, "Marcar", lambda: page.marca_paquete(sel), color=MUTED, font=F(9, True), padx=10, pady=6).pack(side="left", padx=(8, 0))
