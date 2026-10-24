"""Página «Licencia»: activar tu clave y, si eres el creador, generar claves para otras personas."""
import sys
import tkinter as tk

import licencia as lic
from util import DEMO
from widgets import (BG, CYAN, F, FG, GREEN, MUTED, PANEL, PANEL2, PINK, RED, YELLOW, Card, NeonButton, ScrollFrame, WrapLabel,
                     badge, page_title)

LEVEL_COL = {"owner": PINK, "pro": GREEN, "free": MUTED, "expired": YELLOW, "invalid": RED}
LEVEL_TXT = {"owner": "CREADOR", "pro": "PRO", "free": "GRATIS", "expired": "CADUCADA", "invalid": "NO VÁLIDA"}


def _entry(parent, var, width=60, readonly=False):
    return tk.Entry(parent, textvariable=var, font=("Consolas", 10), bg=PANEL2, fg=FG, insertbackground=FG, relief="flat",
                    highlightthickness=1, highlightbackground="#1f4a32", highlightcolor=CYAN, width=width,
                    readonlybackground=PANEL2, state="readonly" if readonly else "normal")


class LicensePage(tk.Frame):
    def __init__(self, parent, app):
        super().__init__(parent, bg=BG)
        self.app = app
        top = tk.Frame(self, bg=BG)
        top.pack(fill="x", padx=26, pady=(22, 6))
        page_title(top, "Licencia", "Activa tu clave para desbloquear las funciones PRO.", accent=YELLOW).pack(anchor="w")
        self.scroll = ScrollFrame(self)
        self.scroll.pack(fill="both", expand=True, padx=(26, 10), pady=(8, 10))
        self.root = self.scroll.inner
        self.build()

    def on_show(self):
        self.build()

    def build(self):
        for w in self.root.winfo_children():
            w.destroy()
        root = self.root
        st = lic.status()
        col = LEVEL_COL[st["level"]]
        c = Card(root, accent=col, title="Tu licencia")
        c.pack(fill="x", pady=(0, 12))
        row = tk.Frame(c.body, bg=PANEL)
        row.pack(fill="x")
        badge(row, LEVEL_TXT[st["level"]], col).pack(side="left")
        tk.Label(row, text="   " + st["msg"], font=F(11, True), fg=FG, bg=PANEL).pack(side="left")
        line = tk.Frame(c.body, bg=PANEL)
        line.pack(fill="x", pady=(10, 0))
        tk.Label(line, text="ID de este PC:", font=F(10), fg=MUTED, bg=PANEL).pack(side="left", padx=(0, 8))
        self.v_pc = tk.StringVar(value=lic.pc_id())
        _entry(line, self.v_pc, 24, readonly=True).pack(side="left", ipady=4, padx=(0, 8))
        NeonButton(line, "Copiar", lambda: self.copy(self.v_pc.get(), "ID copiado"), color=CYAN, padx=12, pady=5, font=F(9, True)).pack(side="left")
        WrapLabel(c.body, text="Si quien te dio la clave la quiere atada a tu PC, mándale este ID.", font=F(9), fg=MUTED).pack(fill="x", pady=(6, 0))

        a = Card(root, accent=CYAN, title="Activar una clave")
        a.pack(fill="x", pady=(0, 12))
        self.v_key = tk.StringVar()
        _entry(a.body, self.v_key, 70).pack(fill="x", ipady=6)
        r2 = tk.Frame(a.body, bg=PANEL)
        r2.pack(fill="x", pady=(8, 0))
        NeonButton(r2, "Pegar", self.paste, color=CYAN, padx=14, pady=6, font=F(10, True)).pack(side="left")
        NeonButton(r2, "ACTIVAR", self.activate, color=GREEN, filled=True, padx=22, pady=6, font=F(10, True)).pack(side="left", padx=8)
        self.msg = tk.Label(a.body, text="", font=F(10, True), fg=MUTED, bg=PANEL, anchor="w", justify="left")
        self.msg.pack(fill="x", pady=(8, 0))

        inc = Card(root, accent=PINK, title="Qué incluye PRO")
        inc.pack(fill="x", pady=(0, 12))
        names = {k: t for _s, items in sys.modules[type(self.app).__module__].SECTIONS for k, _i, t in items}
        WrapLabel(inc.body, text=", ".join(names[k] for k in names if k in lic.PRO_PAGES) + ".",
                  font=F(10), fg=FG).pack(fill="x")
        WrapLabel(inc.body, text="GRATIS incluye solo: análisis de tu PC, limpieza, monitor, historial y actualizaciones.", font=F(9), fg=MUTED).pack(fill="x", pady=(6, 0))

        if lic.owner_secret() or DEMO:
            self.build_generator(root)

    # ------------------------------------------------------------------
    def build_generator(self, root):
        g = Card(root, accent=PINK, title="Generador de claves (solo tú lo ves)")
        g.pack(fill="x", pady=(0, 12))
        WrapLabel(g.body, text="Crea una clave con caducidad. Si pegas el ID del PC de la otra persona, la clave solo funcionará en su PC; "
                               "si lo dejas vacío, valdrá en cualquier PC.", font=F(9), fg=MUTED).pack(fill="x")
        r = tk.Frame(g.body, bg=PANEL)
        r.pack(fill="x", pady=(8, 0))
        tk.Label(r, text="ID del PC:", font=F(10), fg=MUTED, bg=PANEL).pack(side="left", padx=(0, 8))
        self.v_gpc = tk.StringVar()
        _entry(r, self.v_gpc, 26).pack(side="left", ipady=4)
        d = tk.Frame(g.body, bg=PANEL)
        d.pack(fill="x", pady=(8, 0))
        tk.Label(d, text="Caduca en:", font=F(10), fg=MUTED, bg=PANEL).pack(side="left", padx=(0, 8))
        self.days = 30
        self.dbtn = {}
        for n, label in ((7, "7 días"), (30, "30 días"), (90, "90 días"), (180, "6 meses"), (365, "1 año")):
            b = NeonButton(d, label, lambda n_=n: self.set_days(n_), color=MUTED, padx=12, pady=5, font=F(9, True))
            b.pack(side="left", padx=3)
            self.dbtn[n] = b
        self.set_days(30)
        NeonButton(g.body, "✦  GENERAR CLAVE", self.generate, color=PINK, filled=True, padx=22, pady=7, font=F(10, True)).pack(anchor="w", pady=(10, 0))
        self.v_out = tk.StringVar()
        _entry(g.body, self.v_out, 70, readonly=True).pack(fill="x", ipady=6, pady=(10, 0))
        r3 = tk.Frame(g.body, bg=PANEL)
        r3.pack(fill="x", pady=(8, 0))
        NeonButton(r3, "Copiar clave", lambda: self.copy(self.v_out.get(), "Clave copiada"), color=CYAN, padx=14, pady=6, font=F(10, True)).pack(side="left")
        self.gmsg = tk.Label(r3, text="", font=F(10, True), fg=MUTED, bg=PANEL)
        self.gmsg.pack(side="left", padx=12)

    def set_days(self, n):
        self.days = n
        for k, b in self.dbtn.items():
            b.set_color(PINK if k == n else MUTED)

    def generate(self):
        sec = lic.owner_secret()
        if not sec:
            self.gmsg.config(text="(Demo) aquí saldría la clave: falta tu llave privada." if DEMO else "Falta tu llave privada.", fg=YELLOW)
            return
        try:
            key, exp = lic.make_key(sec, self.v_gpc.get(), self.days)
        except ValueError as e:
            self.gmsg.config(text=str(e), fg=RED)
            return
        self.v_out.set(key)
        self.gmsg.config(text=f"Lista · caduca el {exp.strftime('%d/%m/%Y')}", fg=GREEN)

    # ------------------------------------------------------------------
    def copy(self, text, ok):
        try:
            self.clipboard_clear()
            self.clipboard_append(text)
            self.app.status(ok)
        except tk.TclError:
            pass

    def paste(self):
        try:
            self.v_key.set(self.clipboard_get().strip())
        except tk.TclError:
            pass

    def activate(self):
        ok, m = lic.activate(self.v_key.get())
        self.msg.config(text=("✓ " if ok else "✗ ") + m, fg=GREEN if ok else RED)
        if ok:
            self.app.refresh_license()
            self.after(900, self.build)
