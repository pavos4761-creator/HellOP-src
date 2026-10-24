"""Ventana principal: cabecera, menú lateral, hilos de trabajo y páginas."""
import queue
import sys
import threading
import tkinter as tk
from tkinter import messagebox, ttk  # noqa: F401

from util import DEMO, IS_WIN, is_admin, relaunch_as_admin
import psutil

import anim
import logo_data
import updater
import version

from widgets import (BG, CYAN, F, FG, GREEN, MUTED, PANEL2, PINK, RED, SIDE, VIOLET, GradientBar, MiniBar,
                     NeonButton, PulseLogo, SparkField, badge, install_mousewheel, mix, round_rect, setup_styles)

SECTIONS = [
    ("INICIO", [("home", "⌂", "Inicio"), ("analysis", "◎", "Análisis de PC")]),
    ("OPTIMIZAR", [("hidden", "⌕", "Rendimiento oculto"), ("optimize", "⚡", "Optimizar"), ("clean", "✦", "Limpieza"), ("bench", "▲", "Antes y después")]),
    ("GAMING", [("games", "▣", "Mis juegos"), ("gameprof", "✧", "Ajustes de juego"), ("booster", "☢", "Modo Extremo"),
                ("monitor", "≈", "Monitor"), ("diag", "◈", "Diagnóstico"), ("fps", "▤", "FPS reales")]),
    ("AVANZADO", [("tweaks", "☄", "Tweaks"), ("bios", "◉", "BIOS"), ("oc", "⚙", "Overclock")]),
    ("SISTEMA", [("health", "♥", "Salud del PC"), ("debloat", "✖", "Quitar bloatware"),
                ("history", "↺", "Historial / Deshacer"), ("update", "⟳", "Actualizaciones")]),
]
PAGES = [item for _title, items in SECTIONS for item in items]


class NavItem(tk.Canvas):
    """Entrada del menú: el fondo y el color se funden suavemente, la barra lateral «crece» al activarse
    y puede llevar un punto que late (p. ej. modo automático activo)."""
    H = 23

    def __init__(self, parent, icon, text, command):
        super().__init__(parent, bg=SIDE, height=self.H, highlightthickness=0, bd=0, cursor="hand2")
        self.icon, self.text, self.command = icon, text, command
        self.hov = self.act = 0.0
        self.active = self._hover_goal = False
        self.dot, self.pulse, self._job = None, 0.0, None
        self.bind("<Configure>", lambda e: self._draw())
        self.bind("<Enter>", lambda e: self._go(hover=True))
        self.bind("<Leave>", lambda e: self._go(hover=False))
        self.bind("<Button-1>", lambda e: self.command())
        self.bind("<Destroy>", lambda e: self._stop())

    def _stop(self):
        if self._job is not None:
            try:
                self.after_cancel(self._job)
            except tk.TclError:
                pass
            self._job = None

    def _go(self, hover=None):
        if hover is not None:
            self._hover_goal = hover
        if not anim.ENABLED:
            self.hov, self.act = float(self._hover_goal), float(self.active)
            self._draw()
            return
        if self._job is None:
            self._job = self.after(16, self._step)

    def _step(self):
        self._job = None
        gh, ga = float(self._hover_goal), float(self.active)
        self.hov += (gh - self.hov) * 0.3
        self.act += (ga - self.act) * 0.25
        done = abs(gh - self.hov) < 0.02 and abs(ga - self.act) < 0.02
        if done:
            self.hov, self.act = gh, ga
        else:
            self._job = self.after(16, self._step)
        self._draw()

    def set_active(self, on):
        self.active = on
        self._go()

    def set_dot(self, color):
        self.dot = color
        self._draw()

    def beat(self, phase):
        if self.dot:
            self.pulse = phase
            self._draw()

    def _draw(self):
        import math
        try:
            self.delete("all")
            w = max(10, self.winfo_width())
            k = max(self.hov * 0.55, self.act)
            if k > 0.02:
                round_rect(self, 8, 2, w - 8, self.H - 2, 9, fill=mix(SIDE, PANEL2, k), outline="")
            if self.act > 0.02:
                hgt = 4 + 14 * self.act
                round_rect(self, 8, self.H / 2 - hgt / 2, 11, self.H / 2 + hgt / 2, 1.5, fill=CYAN, outline="")
            col = mix(mix(MUTED, FG, self.hov), CYAN, self.act)
            self.create_text(26, self.H / 2, text=self.icon, fill=col, font=F(11, True), anchor="center")
            self.create_text(44, self.H / 2, text=self.text, fill=col, font=F(10, True), anchor="w")
            if self.dot:
                a = 0.45 + 0.55 * (0.5 + 0.5 * math.sin(self.pulse))
                r = 4 + 1.5 * (0.5 + 0.5 * math.sin(self.pulse))
                cx, cy = w - 22, self.H / 2
                self.create_oval(cx - r - 3, cy - r - 3, cx + r + 3, cy + r + 3, fill=mix(SIDE, self.dot, 0.18 * a), outline="")
                self.create_oval(cx - r, cy - r, cx + r, cy + r, fill=mix(SIDE, self.dot, a), outline="")
        except tk.TclError:
            pass


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(f"HellOP v{version.__version__}" + ("  ·  MODO DEMO" if DEMO else ""))
        self.geometry("1140x800")
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
        tk.Frame(body, bg="#16301f", width=1).pack(side="left", fill="y")
        self.content = tk.Frame(body, bg=BG)
        self.content.pack(side="left", fill="both", expand=True)

        spark = SparkField(side, bg=SIDE, n=14)
        spark.configure(height=30)
        spark.pack(fill="x")
        self.nav = {}
        for title, items in SECTIONS:
            tk.Label(side, text=title, font=F(8, True), fg=MUTED, bg=SIDE, anchor="w").pack(fill="x", padx=20, pady=(6, 0))
            for key, icon, text in items:
                n = NavItem(side, icon, text, lambda k=key: self.show(k))
                n.pack(fill="x")
                self.nav[key] = n
        live = tk.Frame(side, bg=SIDE)
        live.pack(side="bottom", fill="x", padx=18, pady=(0, 6))
        self.live_lbl = tk.Label(live, text="●  EN VIVO", font=F(8, True), fg=MUTED, bg=SIDE, anchor="w")
        self.live_lbl.pack(fill="x", pady=(0, 4))
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
        from page_diag import DiagPage
        from page_debloat import DebloatPage
        from page_gameprof import GameProfilePage
        from page_fps import FpsPage
        from page_games import GamesPage
        from page_health import HealthPage
        from page_hidden import HiddenPage
        from page_home import HomePage
        from page_monitor import MonitorPage
        from page_oc import OcPage
        from page_history import HistoryPage
        from page_optimize import OptimizePage
        from page_tweaks import TweaksPage
        from page_update import UpdatePage
        self.pages = {
            "home": HomePage(self.content, self),
            "analysis": AnalysisPage(self.content, self),
            "optimize": OptimizePage(self.content, self),
            "games": GamesPage(self.content, self),
            "booster": BoosterPage(self.content, self),
            "bios": BiosPage(self.content, self),
            "monitor": MonitorPage(self.content, self),
            "diag": DiagPage(self.content, self),
            "oc": OcPage(self.content, self),
            "clean": CleanPage(self.content, self),
            "bench": BenchPage(self.content, self),
            "history": HistoryPage(self.content, self),
            "gameprof": GameProfilePage(self.content, self),
            "tweaks": TweaksPage(self.content, self),
            "fps": FpsPage(self.content, self),
            "hidden": HiddenPage(self.content, self),
            "health": HealthPage(self.content, self),
            "debloat": DebloatPage(self.content, self),
            "update": UpdatePage(self.content, self),
        }
        self.show("home")
        self._anim_phase = 0.0
        self.after(80, self._anim_tick)
        self.protocol("WM_DELETE_WINDOW", self.on_close)
        import booster
        rec = booster.recover_after_crash()
        if rec:
            self.status("Se reanudaron servicios que el Modo Extremo había pausado: " + ", ".join(rec))
        self.after(50, self._pump)
        self.after(4000, self._auto_check)
        self.after(1500, self.pages["games"].boot)
        self.after(600, self._admin_prompt)

    def _set_window_icon(self):
        """Icono de la ventana y de la barra de tareas (en vez del plumín por defecto de Tk)."""
        try:
            self.iconphoto(True, self._logo_big)
        except tk.TclError:
            pass
        if not IS_WIN:
            return
        try:
            import base64
            import ctypes
            from util import APP_DIR
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("HellOP.App")
            APP_DIR.mkdir(parents=True, exist_ok=True)
            ico = APP_DIR / "hellop.ico"
            ico.write_bytes(base64.b64decode(logo_data.ICO))
            self.iconbitmap(default=str(ico))
        except Exception:  # noqa: BLE001
            pass

    # ---- cabecera -------------------------------------------------------
    def _build_header(self):
        h = tk.Frame(self, bg=SIDE)
        h.pack(fill="x")
        self._logo = tk.PhotoImage(data=logo_data.LOGO_64)
        self._logo_big = tk.PhotoImage(data=logo_data.LOGO_128)
        self._set_window_icon()
        PulseLogo(h, self._logo, size=74, bg=SIDE).pack(side="left", padx=(14, 6), pady=2)
        tk.Label(h, text="Hell", font=F(20, True), fg=FG, bg=SIDE).pack(side="left")
        tk.Label(h, text="OP", font=F(20, True), fg=CYAN, bg=SIDE).pack(side="left")
        tk.Label(h, text=f"v{version.__version__}", font=F(9, True), fg=MUTED, bg=SIDE).pack(side="left", padx=(12, 0), pady=(10, 0))
        tk.Label(h, text="optimización extrema para gaming", font=F(9), fg=MUTED, bg=SIDE).pack(side="left", padx=16, pady=(8, 0))
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
            self.pages["games"].shutdown()
            self.pages["monitor"].shutdown()
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
        first = self.current is None
        for p in self.pages.values():
            p.place_forget()
        for k, n in self.nav.items():
            n.set_active(k == key)
        if getattr(self, "_slide_cancel", None):
            self._slide_cancel()
        self.current = key
        page = self.pages[key]
        if first or not anim.ENABLED:
            page.place(x=0, y=0, relwidth=1, relheight=1)
        else:                                     # entra deslizando suavemente desde la derecha
            page.place(x=30, y=0, relwidth=1, relheight=1)
            self._slide_cancel = anim.tween(self, 190, lambda p: page.place_configure(x=int(30 * (1 - p))),
                                            done=lambda: page.place_configure(x=0))
        if hasattr(page, "on_show"):
            page.on_show()

    def _anim_tick(self):
        """Latido de los puntos del menú y del indicador «en vivo»."""
        import math
        self._anim_phase += 0.28
        for n in self.nav.values():
            n.beat(self._anim_phase)
        try:
            self.live_lbl.config(fg=mix(MUTED, GREEN, 0.5 + 0.5 * math.sin(self._anim_phase * 0.8)))
        except tk.TclError:
            return
        self.after(90, self._anim_tick)

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
