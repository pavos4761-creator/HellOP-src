"""Página «Limpieza»: temporales, cachés, papelera, duplicados."""
import os
import time
import tkinter as tk
from tkinter import messagebox, ttk

import cleanup
from util import DEMO, fmt_bytes, is_admin
from widgets import PANEL2
from widgets import (BG, CYAN, F, FG, GREEN, MUTED, PANEL, PINK, RED, VIOLET, YELLOW, Card, NeonButton,
                     ScrollFrame, WrapLabel, badge, checkbox, page_title)


class CleanPage(tk.Frame):
    def __init__(self, parent, app):
        super().__init__(parent, bg=BG)
        self.app = app
        self.items = []
        self.vars = {}
        self.dups = []
        self.dup_vars = {}
        self.busy = False
        self.scanned = False

        top = tk.Frame(self, bg=BG)
        top.pack(fill="x", padx=26, pady=(22, 6))
        page_title(top, "Limpieza", "Libera espacio y quita lo que ralentiza. Primero escaneo y tú eliges qué borrar.",
                   accent=GREEN).pack(anchor="w")
        self.scroll = ScrollFrame(self)
        self.scroll.pack(fill="both", expand=True, padx=(26, 10), pady=(8, 10))
        self.build()

    def on_show(self):
        if not self.scanned and not self.busy:
            self.scan()

    # ------------------------------------------------------------------
    def build(self):
        root = self.scroll.inner
        self.card1 = Card(root, accent=CYAN, title="Archivos temporales y cachés")
        self.card1.pack(fill="x", pady=(0, 12))
        self.list_box = tk.Frame(self.card1.body, bg=PANEL)
        self.list_box.pack(fill="x")
        bar = tk.Frame(self.card1.body, bg=PANEL)
        bar.pack(fill="x", pady=(12, 0))
        self.b_scan = NeonButton(bar, "Escanear de nuevo", self.scan, color=CYAN, padx=14, pady=7)
        self.b_scan.pack(side="left")
        self.b_clean = NeonButton(bar, "✦  LIMPIAR SELECCIONADO", self.clean, color=GREEN, filled=True, padx=20, pady=8)
        self.b_clean.pack(side="left", padx=10)
        self.total = tk.Label(bar, text="", font=F(11, True), fg=GREEN, bg=PANEL)
        self.total.pack(side="left", padx=8)
        self.pb = ttk.Progressbar(self.card1.body, style="Green.Horizontal.TProgressbar", mode="determinate", maximum=100)
        self.msg = tk.Label(self.card1.body, text="", font=F(10), fg=MUTED, bg=PANEL, anchor="w", justify="left", wraplength=800)
        self.msg.pack(fill="x", pady=(8, 0))
        self.extra = tk.Frame(self.card1.body, bg=PANEL)
        self.extra.pack(fill="x")

        self.card2 = Card(root, accent=PINK, title="Archivos duplicados")
        self.card2.pack(fill="x", pady=(0, 12))
        WrapLabel(self.card2.body, fg=MUTED,
                  text="Busca copias idénticas en Descargas, Documentos, Escritorio, Imágenes, Vídeos y Música. "
                       "Los que elijas van a la Papelera (se pueden recuperar). Siempre se conserva una copia.").pack(fill="x")
        self.b_dup = NeonButton(self.card2.body, "Buscar duplicados", self.find_dups, color=PINK, padx=16, pady=8)
        self.b_dup.pack(anchor="w", pady=(10, 4))
        self.dup_msg = tk.Label(self.card2.body, text="", font=F(10), fg=MUTED, bg=PANEL, anchor="w")
        self.dup_msg.pack(fill="x")
        self.dup_box = tk.Frame(self.card2.body, bg=PANEL)
        self.dup_box.pack(fill="x")

    # ---- escaneo -----------------------------------------------------------
    def scan(self):
        if self.busy:
            return
        self.busy = True
        self.b_scan.set_enabled(False)
        self.b_clean.set_enabled(False)
        self.msg.config(text="Escaneando…", fg=CYAN)
        self.app.status("Escaneando archivos basura…")

        def work():
            items = cleanup.build_items()
            for it in items:
                it.scan()
            return items
        self.app.bg(work, self.scan_done, self.scan_fail)

    def scan_fail(self, e):
        self.busy = False
        self.b_scan.set_enabled(True)
        self.msg.config(text=f"Error al escanear: {e}", fg=RED)

    def scan_done(self, items):
        self.busy = False
        self.scanned = True
        self.items = items
        self.b_scan.set_enabled(True)
        self.b_clean.set_enabled(True)
        for w in self.list_box.winfo_children():
            w.destroy()
        self.vars = {}
        for it in items:
            ok = it.available()
            v = tk.BooleanVar(value=ok and it.default and it.size > 0)
            self.vars[it.id] = v
            r = tk.Frame(self.list_box, bg=PANEL)
            r.pack(fill="x", pady=3)
            cb = checkbox(r, "", v)
            cb.pack(side="left", anchor="n")
            if not ok:
                cb.config(state="disabled")
            t = tk.Frame(r, bg=PANEL)
            t.pack(side="left", fill="x", expand=True)
            tk.Label(t, text=it.title, font=F(10, True), fg=FG if ok else MUTED, bg=PANEL, anchor="w").pack(fill="x")
            d = it.desc + (f"  ·  {it.warn}" if it.warn else "") + ("" if ok else "  ·  (necesita administrador)")
            WrapLabel(t, text=d, fg=MUTED, font=F(9)).pack(fill="x")
            tk.Label(r, text=fmt_bytes(it.size), font=F(11, True), fg=YELLOW if it.size > 200 * 1024 ** 2 else FG,
                     bg=PANEL, width=10, anchor="e").pack(side="right")
            v.trace_add("write", lambda *a: self.update_total())
        for w in self.extra.winfo_children():
            w.destroy()
        if cleanup.windows_old_size_hint():
            f = tk.Frame(self.extra, bg=PANEL)
            f.pack(fill="x", pady=(10, 0))
            WrapLabel(f, fg=YELLOW, text="Hay una carpeta Windows.old (restos de una versión anterior de Windows) que puede ocupar "
                                         "muchos GB. Se borra con la herramienta oficial de Windows:").pack(side="left", fill="x", expand=True)
            NeonButton(f, "Abrir Liberador de espacio", cleanup.open_disk_cleanup, color=YELLOW, padx=10, pady=5,
                       font=F(9, True)).pack(side="right")
        self.update_total()
        self.msg.config(text="Escaneo completado. Marca lo que quieras limpiar.", fg=MUTED)
        self.app.status("Escaneo completado")

    def update_total(self):
        sel = sum(it.size for it in self.items if self.vars.get(it.id) and self.vars[it.id].get())
        self.total.config(text=f"Se liberarán ≈ {fmt_bytes(sel)}")

    # ---- limpieza ------------------------------------------------------------
    def clean(self):
        if self.busy:
            return
        chosen = [it for it in self.items if self.vars[it.id].get()]
        if not chosen:
            messagebox.showinfo("Limpieza", "No hay nada seleccionado.")
            return
        size = sum(it.size for it in chosen)
        if not messagebox.askyesno("Confirmar limpieza", f"Se van a borrar {len(chosen)} categorías (≈ {fmt_bytes(size)}).\n"
                                   "Son archivos que se pueden regenerar. Esta acción no se puede deshacer.\n\n¿Continuar?"):
            return
        self.busy = True
        self.b_scan.set_enabled(False)
        self.b_clean.set_enabled(False)
        self.pb.pack(fill="x", pady=(8, 0), before=self.msg)
        self.pb["value"] = 0

        def work():
            freed = failed = 0
            for i, it in enumerate(chosen):
                self.app.ui(self._clean_prog, int(i / len(chosen) * 100), f"Limpiando: {it.title}…")
                f, x = it.clean()
                freed += f
                failed += x
            return freed, failed
        self.app.bg(work, self.clean_done, self.scan_fail)

    def _clean_prog(self, pct, text):
        self.pb["value"] = pct
        self.msg.config(text=text, fg=CYAN)

    def clean_done(self, res):
        freed, failed = res
        self.pb["value"] = 100
        self.pb.pack_forget()
        self.busy = False
        extra = f" ({failed} archivos estaban en uso y se omitieron)" if failed else ""
        self.msg.config(text=f"✓ Liberados {fmt_bytes(freed)}{extra}", fg=GREEN)
        self.app.status(f"Limpieza completada: {fmt_bytes(freed)} liberados")
        self.scan()

    # ---- duplicados ------------------------------------------------------------
    def find_dups(self):
        if self.busy:
            return
        self.busy = True
        self.b_dup.set_enabled(False)
        self.dup_msg.config(text="Buscando… puede tardar varios minutos si tienes muchos archivos.", fg=CYAN)
        roots = cleanup.default_scan_roots()
        self.app.bg(lambda: cleanup.find_duplicates(roots, progress=lambda m: self.app.ui(self.dup_msg.config, text=m)),
                    self.dups_done, self.dups_fail)

    def dups_fail(self, e):
        self.busy = False
        self.b_dup.set_enabled(True)
        self.dup_msg.config(text=f"Error: {e}", fg=RED)

    def dups_done(self, groups):
        self.busy = False
        self.b_dup.set_enabled(True)
        self.dups = groups
        for w in self.dup_box.winfo_children():
            w.destroy()
        self.dup_vars = {}
        if not groups:
            self.dup_msg.config(text="No encontré archivos duplicados grandes ✓", fg=GREEN)
            return
        waste = sum(g["size"] * (len(g["files"]) - 1) for g in groups)
        self.dup_msg.config(text=f"{len(groups)} grupos de duplicados · {fmt_bytes(waste)} recuperables. "
                                 "Marcado = irá a la Papelera (se conserva siempre el más antiguo).", fg=YELLOW)
        for gi, g in enumerate(groups[:60]):
            f = tk.Frame(self.dup_box, bg=PANEL2)
            f.pack(fill="x", pady=4)
            tk.Label(f, text=f"{fmt_bytes(g['size'])} × {len(g['files'])} copias", font=F(10, True), fg=PINK, bg=PANEL2,
                     anchor="w").pack(fill="x", padx=8, pady=(6, 2))
            for fi, (path, mtime) in enumerate(g["files"]):
                v = tk.BooleanVar(value=fi > 0)
                self.dup_vars[(gi, fi)] = v
                label = f"{path}   ·   {time.strftime('%d/%m/%Y', time.localtime(mtime))}" + ("   ← se conserva" if fi == 0 else "")
                cb = checkbox(f, label, v, bg=PANEL2, font=("Consolas", 9))
                cb.pack(fill="x", padx=8)
            tk.Frame(f, bg=PANEL2, height=4).pack()
        bar = tk.Frame(self.dup_box, bg=PANEL)
        bar.pack(fill="x", pady=(8, 0))
        NeonButton(bar, "Enviar marcados a la Papelera", self.trash_dups, color=PINK, filled=True, padx=16, pady=8).pack(side="left")

    def trash_dups(self):
        paths = []
        for gi, g in enumerate(self.dups[:60]):
            marked = [g["files"][fi][0] for fi in range(len(g["files"])) if self.dup_vars.get((gi, fi)) and self.dup_vars[(gi, fi)].get()]
            if len(marked) >= len(g["files"]):          # protección: nunca borrar todas las copias
                marked = marked[1:]
            paths += marked
        if not paths:
            messagebox.showinfo("Duplicados", "No hay nada marcado.")
            return
        if not messagebox.askyesno("Enviar a la Papelera", f"Se enviarán {len(paths)} archivos a la Papelera de reciclaje.\n"
                                   "Podrás recuperarlos desde allí.\n\n¿Continuar?"):
            return
        self.b_dup.set_enabled(False)
        self.app.bg(lambda: cleanup.send_to_recycle_bin(paths), self.trash_done)

    def trash_done(self, res):
        ok, fail = res
        self.b_dup.set_enabled(True)
        self.dup_msg.config(text=f"✓ {ok} archivos enviados a la Papelera" + (f" · {fail} no se pudieron mover" if fail else ""), fg=GREEN)
        for w in self.dup_box.winfo_children():
            w.destroy()
