"""Página «Quitar bloatware»: apps de Windows y programas de fabricante que sobran."""
import tkinter as tk
from tkinter import messagebox

import actions
import debloat
from util import DEMO
from widgets import (BG, CYAN, F, FG, GREEN, MUTED, PANEL, PINK, RED, YELLOW, Card, NeonButton, ScrollFrame, WrapLabel,
                     checkbox, page_title)


class DebloatPage(tk.Frame):
    def __init__(self, parent, app):
        super().__init__(parent, bg=BG)
        self.app = app
        self.busy = False
        self.appx, self.win32, self.vars = [], [], {}
        top = tk.Frame(self, bg=BG)
        top.pack(fill="x", padx=26, pady=(22, 6))
        page_title(top, "Quitar bloatware",
                   "Apps preinstaladas y programas de fabricante que gastan RAM y procesador sin que los uses.",
                   accent=YELLOW).pack(anchor="w")
        self.scroll = ScrollFrame(self)
        self.scroll.pack(fill="both", expand=True, padx=(26, 10), pady=(8, 10))
        root = self.scroll.inner
        c = Card(root, accent=YELLOW, title="Antes de empezar")
        c.pack(fill="x", pady=(0, 12))
        for t in ("No se marca nada solo: tú eliges. Las apps de Windows se pueden volver a instalar desde la Microsoft Store.",
                  "Los programas se desinstalan con su propio desinstalador: verás sus pantallas y tendrás que confirmar.",
                  "No se muestran componentes de Windows, drivers ni lanzadores de juegos para que no rompas nada.",
                  "Honestidad: quitar esto libera espacio y algo de RAM, pero no sube los FPS de forma notable. Lo que más "
                  "pesa es un antivirus de prueba (McAfee, Norton) o un asistente del fabricante que corre siempre."):
            WrapLabel(c.body, text="•  " + t, font=F(9), fg=MUTED).pack(fill="x", pady=1)
        bar = tk.Frame(root, bg=BG)
        bar.pack(fill="x", pady=(0, 8))
        self.b_scan = NeonButton(bar, "↻  BUSCAR MIS APPS", self.scan, color=YELLOW, filled=True, font=F(11, True), padx=20, pady=8)
        self.b_scan.pack(side="left")
        self.msg = tk.Label(bar, text="", font=F(10), fg=MUTED, bg=BG)
        self.msg.pack(side="left", padx=14)
        self.body = tk.Frame(root, bg=BG)
        self.body.pack(fill="x")
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
        self.msg.config(text="Buscando (puede tardar unos segundos)…", fg=CYAN)
        self.app.bg(debloat.scan, self._scanned, self._scan_fail)

    def _scan_fail(self, e):
        self.busy = False
        self.b_scan.set_enabled(True)
        self.msg.config(text=f"Error: {e}", fg=RED)

    def _scanned(self, res):
        self.busy = False
        self.b_scan.set_enabled(True)
        self.appx, self.win32 = res
        self.msg.config(text=f"{len(self.appx)} apps de Windows y {len(self.win32)} programas", fg=GREEN)
        self.render()

    def render(self):
        for w in self.body.winfo_children():
            w.destroy()
        self.vars = {}
        # ---- apps de Windows
        c = Card(self.body, accent=PINK, title="Apps de Windows")
        c.pack(fill="x", pady=(0, 12))
        if not self.appx:
            WrapLabel(c.body, text="No he encontrado apps que sobren.", font=F(10), fg=GREEN).pack(fill="x")
        else:
            row = tk.Frame(c.body, bg=PANEL)
            row.pack(fill="x", pady=(0, 6))
            NeonButton(row, "Marcar las recomendadas", self.mark_rec, color=CYAN, padx=14, pady=6, font=F(10, True)).pack(side="left")
            NeonButton(row, "Desmarcar todo", self.unmark, color=MUTED, padx=14, pady=6, font=F(10, True)).pack(side="left", padx=8)
            self.b_remove = NeonButton(row, "✖  QUITAR LAS MARCADAS", self.remove_marked, color=RED, filled=True, padx=16, pady=6,
                                       font=F(10, True))
            self.b_remove.pack(side="right")
            for a in self.appx[:80]:
                v = tk.BooleanVar(value=False)
                self.vars[a["name"]] = v
                line = tk.Frame(c.body, bg=PANEL)
                line.pack(fill="x", pady=1)
                checkbox(line, a["title"], v, bg=PANEL, font=F(10)).pack(side="left")
                if a["rec"]:
                    tk.Label(line, text="  recomendada", font=F(8, True), fg=GREEN, bg=PANEL).pack(side="left")
                if a["why"]:
                    tk.Label(line, text="  " + a["why"], font=F(9), fg=MUTED, bg=PANEL).pack(side="left")
        # ---- programas
        p = Card(self.body, accent=CYAN, title="Programas instalados")
        p.pack(fill="x", pady=(0, 12))
        if not self.win32:
            WrapLabel(p.body, text="No he encontrado programas que sobren.", font=F(10), fg=GREEN).pack(fill="x")
        for a in self.win32[:60]:
            r = tk.Frame(p.body, bg=PANEL)
            r.pack(fill="x", pady=3)
            tx = tk.Frame(r, bg=PANEL)
            tx.pack(side="left", fill="x", expand=True)
            head = tk.Frame(tx, bg=PANEL)
            head.pack(fill="x")
            tk.Label(head, text=a["name"], font=F(10, True), fg=FG, bg=PANEL).pack(side="left")
            if a["rec"]:
                tk.Label(head, text="  recomendado quitar", font=F(8, True), fg=GREEN, bg=PANEL).pack(side="left")
            info = a["publisher"] or ""
            if a["size"]:
                info += ("  ·  " if info else "") + (f"{a['size']:.0f} MB" if a["size"] < 1024 else f"{a['size'] / 1024:.1f} GB")
            tk.Label(tx, text=info, font=F(9), fg=MUTED, bg=PANEL, anchor="w").pack(fill="x")
            NeonButton(r, "Desinstalar", lambda n=a["name"]: self.uninstall(n), color=RED if a["rec"] else MUTED,
                       padx=14, pady=5, font=F(9, True)).pack(side="right")

    def mark_rec(self):
        for a in self.appx:
            if a["name"] in self.vars:
                self.vars[a["name"]].set(a["rec"])

    def unmark(self):
        for v in self.vars.values():
            v.set(False)

    # ------------------------------------------------------------------
    def remove_marked(self):
        chosen = [a for a in self.appx if self.vars.get(a["name"]) and self.vars[a["name"]].get()]
        if not chosen or self.busy:
            if not chosen:
                self.msg.config(text="Marca primero alguna app.", fg=YELLOW)
            return
        if not DEMO and not messagebox.askyesno(
                "Quitar apps", f"Se van a quitar {len(chosen)} apps de Windows:\n\n" + "\n".join("· " + a["title"] for a in chosen[:12])
                + ("\n…" if len(chosen) > 12 else "") + "\n\nPodrás volver a instalarlas desde la Microsoft Store.\n¿Continuar?"):
            return
        self.busy = True
        self.b_scan.set_enabled(False)
        self.msg.config(text=f"Quitando {len(chosen)} apps…", fg=CYAN)

        def work():
            ok = fail = 0
            for a in chosen:
                r = actions.execute(debloat.AppxRemoveAction(a["name"], a["title"]))
                ok += r.ok
                fail += (not r.ok)
            return ok, fail

        self.app.bg(work, self._removed, self._scan_fail)

    def _removed(self, res):
        ok, fail = res
        self.busy = False
        self.msg.config(text=f"✓ {ok} quitadas" + (f"  ·  {fail} no se pudieron quitar" if fail else ""), fg=GREEN if not fail else YELLOW)
        if DEMO:
            self.b_scan.set_enabled(True)
            return
        self.scan()

    def uninstall(self, name):
        if self.busy:
            return
        if not DEMO and not messagebox.askyesno("Desinstalar", f"Se abrirá el desinstalador de:\n\n{name}\n\n¿Continuar?"):
            return
        self.app.bg(lambda: actions.execute(debloat.Win32UninstallAction(name)),
                    lambda r: self.msg.config(text=("✓ " if r.ok else "✗ ") + r.msg, fg=GREEN if r.ok else RED),
                    lambda e: self.msg.config(text=f"✗ {e}", fg=RED))
