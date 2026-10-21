"""Ventana principal: cabecera, menú lateral, hilos de trabajo y páginas."""
import queue
import sys
import threading
import tkinter as tk
from tkinter import messagebox, ttk  # noqa: F401

from util import DEMO, IS_WIN, is_admin, relaunch_as_admin
import psutil

import logo_data
import updater
import version

from widgets import (BG, CYAN, F, FG, GREEN, MUTED, PANEL2, PINK, RED, SIDE, VIOLET, GradientBar, MiniBar,
                     NeonButton, badge, install_mousewheel, setup_styles)

PAGES = [
    ("analysis", "◎", "Análisis de PC"),
    ("optimize", "⚡", "Optimizar"),
    ("booster", "☢", "Modo Extremo"),
    ("bios", "◉", "BIOS"),
    ("clean", "✦", "Limpieza"),
    ("bench", "▲", "Rendimiento"),
    ("history", "↺", "Historial / Deshacer"),
    ("update", "⟳", "Actualizaciones"),
]


class NavItem(tk.Frame):
    def __init__(self, parent, icon, text, command):
        super().__init__(parent, bg=SIDE, cursor="hand2")
        self.strip = tk.Frame(self, bg=SIDE, width=3)
        self.strip.pack(side="left", fill="y")
        self.lbl = tk.Label(self, text=f"  {icon}   {text}", font=F(11, True), fg=MUTED, bg=SIDE,
                            anchor="w", padx=8, pady=13, cursor="hand2")
        self.lbl.pack(side="left", fill="x", expand=True)
        for w in (self, self.lbl):
            w.bind("<Button-1>", lambda e: command())
            w.bind("<Enter>", lambda e: self._hover(True))
            w.bind("<Leave>", lambda e: self._hover(False))
        self.active = False

    def _hover(self, on):
        if not self.active:
            self.lbl.config(fg=FG if on else MUTED)

    def set_active(self, on):
        self.active = on
        self.strip.config(bg=CYAN if on else SIDE)
        self.lbl.config(fg=CYAN if on else MUTED, bg=PANEL2 if on else SIDE)
        self.config(bg=PANEL2 if on else SIDE)


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(f"HellOP v{version.__version__}" + ("  ·  MODO DEMO" if DEMO else ""))
        self.geometry("1140x760")
        self.minsize(980, 640)
        self.configure(bg=BG)
        setup_styles(self)
        install_mousewheel(self)
        self.q = queue.Queue()
        self.current = None
        self._dark_titlebar()
        self._build_header()

        body = tk.Frame(self, bg=BG)
        body.pack(fill="both", expand=True)
        side = tk.Frame(body, bg=SIDE, width=230)
        side.pack(side="left", fill="y")
        side.pack_propagate(False)
        tk.Frame(body, bg="#2c1619", width=1).pack(side="left", fill="y")
        self.content = tk.Frame(body, bg=BG)
        self.content.pack(side="left", fill="both", expand=True)

        tk.Label(side, text="MENÚ", font=F(8, True), fg=MUTED, bg=SIDE, anchor="w").pack(fill="x", padx=18, pady=(18, 6))
        self.nav = {}
        for key, icon, text in PAGES:
            n = NavItem(side, icon, text, lambda k=key: self.show(k))
            n.pack(fill="x")
            self.nav[key] = n
        tk.Label(side, text="Todo lo que cambia se guarda\nen el Historial para poder\ndeshacerlo.", font=F(9),
                 fg=MUTED, bg=SIDE, justify="left", anchor="w").pack(side="bottom", fill="x", padx=18, pady=(8, 18))
        live = tk.Frame(side, bg=SIDE)
        live.pack(side="bottom", fill="x", padx=18, pady=(0, 6))
        tk.Label(live, text="EN VIVO", font=F(8, True), fg=MUTED, bg=SIDE, anchor="w").pack(fill="x", pady=(0, 4))
        self.bar_cpu = MiniBar(live, "CPU", CYAN)
        self.bar_ram = MiniBar(live, "RAM", PINK)
        self.bar_cpu.pack(pady=1)
        self.bar_ram.pack(pady=1)
        self._tick_live()

        self.statusbar = tk.Label(self, text="Listo", font=F(9), fg=MUTED, bg=SIDE, anchor="w", padx=14, pady=5)
        self.statusbar.pack(fill="x", side="bottom")

        from page_analysis import AnalysisPage
        from page_bench import BenchPage
        from page_bios import BiosPage
        from page_booster import BoosterPage
        from page_clean import CleanPage
        from page_history import HistoryPage
        from page_optimize import OptimizePage
        from page_update import UpdatePage
        self.pages = {
            "analysis": AnalysisPage(self.content, self),
            "optimize": OptimizePage(self.content, self),
            "booster": BoosterPage(self.content, self),
            "bios": BiosPage(self.content, self),
            "clean": CleanPage(self.content, self),
            "bench": BenchPage(self.content, self),
            "history": HistoryPage(self.content, self),
            "update": UpdatePage(self.content, self),
        }
        self.show("analysis")
        self.protocol("WM_DELETE_WINDOW", self.on_close)
        import booster
        rec = booster.recover_after_crash()
        if rec:
            self.status("Se reanudaron servicios que el Modo Extremo había pausado: " + ", ".join(rec))
        self.after(50, self._pump)
        self.after(4000, self._auto_check)
        self.after(600, self._admin_prompt)

    # ---- cabecera -------------------------------------------------------
    def _build_header(self):
        h = tk.Frame(self, bg=SIDE)
        h.pack(fill="x")
        self._logo = tk.PhotoImage(data=logo_data.LOGO_64)
        self._logo_big = tk.PhotoImage(data=logo_data.LOGO_128)
        try:
            self.iconphoto(True, self._logo_big)
        except tk.TclError:
            pass
        tk.Label(h, image=self._logo, bg=SIDE, bd=0).pack(side="left", padx=(18, 8), pady=6)
        tk.Label(h, text="Hell", font=F(20, True), fg=FG, bg=SIDE).pack(side="left")
        tk.Label(h, text="OP", font=F(20, True), fg=CYAN, bg=SIDE).pack(side="left")
        tk.Label(h, text=f"v{version.__version__}", font=F(9, True), fg=MUTED, bg=SIDE).pack(side="left", padx=(12, 0), pady=(10, 0))
        tk.Label(h, text="análisis · optimización · limpieza", font=F(9), fg=MUTED, bg=SIDE).pack(side="left", padx=16, pady=(8, 0))
        right = tk.Frame(h, bg=SIDE)
        right.pack(side="right", padx=18)
        self.hdr_right = right
        self.upd_btn = None
        if DEMO:
            badge(right, "MODO DEMO: NO TOCA NADA", "#ff9f1c").pack(side="left", padx=6)
        if is_admin():
            badge(right, "ADMINISTRADOR", GREEN).pack(side="left", padx=6)
        else:
            badge(right, "SIN ADMINISTRADOR", RED).pack(side="left", padx=6)
            NeonButton(right, "Reabrir como administrador", self.restart_admin, color=RED, padx=10, pady=4,
                       font=F(9, True)).pack(side="left", padx=6)
        GradientBar(self, height=3).pack(fill="x")

    def mark_update_available(self, latest):
        """Muestra en la cabecera un botón verde cuando hay una versión nueva."""
        if self.upd_btn is not None:
            return
        self.upd_btn = NeonButton(self.hdr_right, f"⬇ Actualización v{latest} disponible", lambda: self.show("update"),
                                  color=GREEN, filled=True, padx=10, pady=4, font=F(9, True))
        self.upd_btn.pack(side="left", padx=6)
        self.status(f"Hay una versión nueva: v{latest}")

    def _auto_check(self):
        if DEMO or not updater.get_repo():
            return

        def done(info):
            if info["newer"]:
                self.pages["update"].info = info
                self.pages["update"].checked(info)

        self.bg(updater.check, done, lambda e: None)        # silencioso: si falla, no molesta

    def _tick_live(self):
        try:
            self.bar_cpu.set(psutil.cpu_percent(interval=None))
            self.bar_ram.set(psutil.virtual_memory().percent)
        except Exception:  # noqa: BLE001
            pass
        self.after(1500, self._tick_live)

    def _dark_titlebar(self):
        if not IS_WIN:
            return
        try:
            import ctypes
            self.update()
            hwnd = ctypes.windll.user32.GetParent(self.winfo_id())
            val = ctypes.c_int(1)
            ctypes.windll.dwmapi.DwmSetWindowAttribute(hwnd, 20, ctypes.byref(val), ctypes.sizeof(val))
        except Exception:  # noqa: BLE001
            pass

    def _admin_prompt(self):
        if IS_WIN and not DEMO and not is_admin():
            if messagebox.askyesno("Permisos de administrador",
                                   "Para optimizar a fondo (servicios, energía, restauración del sistema) "
                                   "necesito permisos de administrador.\n\n¿Reabrir la app como administrador?"):
                self.restart_admin()

    def on_close(self):
        """Antes de cerrar deja todo como estaba (prioridades, servicios, temporizador)."""
        try:
            self.pages["booster"].shutdown()
        except Exception:  # noqa: BLE001
            pass
        self.destroy()

    def restart_admin(self):
        if relaunch_as_admin():
            self.destroy()
            sys.exit(0)
        messagebox.showwarning("Administrador", "No se pudo reabrir como administrador.")

    # ---- navegación -------------------------------------------------------
    def show(self, key):
        for k, p in self.pages.items():
            p.pack_forget()
        for k, n in self.nav.items():
            n.set_active(k == key)
        self.current = key
        page = self.pages[key]
        page.pack(fill="both", expand=True)
        if hasattr(page, "on_show"):
            page.on_show()

    def status(self, text):
        self.statusbar.config(text=text)

    # ---- hilos ---------------------------------------------------------------
    def bg(self, fn, done=None, fail=None):
        """Ejecuta fn en otro hilo y llama a done(resultado) en el hilo de la interfaz."""
        def work():
            try:
                self.q.put(("ok", done, fn()))
            except Exception as e:  # noqa: BLE001
                self.q.put(("err", fail, e))
        threading.Thread(target=work, daemon=True).start()

    def ui(self, fn, *args):
        """Pide ejecutar fn(*args) en el hilo de la interfaz (seguro desde otros hilos)."""
        self.q.put(("call", fn, args))

    def _pump(self):
        try:
            while True:
                kind, f, x = self.q.get_nowait()
                try:
                    if kind == "ok":
                        if f:
                            f(x)
                    elif kind == "err":
                        (f or self._default_error)(x)
                    else:
                        f(*x)
                except tk.TclError:
                    pass   # el widget ya no existe
        except queue.Empty:
            pass
        self.after(40, self._pump)

    def _default_error(self, e):
        self.status(f"Error: {e}")
        messagebox.showerror("Algo ha fallado", f"{type(e).__name__}: {e}")
