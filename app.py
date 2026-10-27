"""Ventana principal: cabecera, menú lateral, hilos de trabajo y páginas."""
import os
import queue
import sys
import threading
import time
import tkinter as tk
from tkinter import messagebox, ttk  # noqa: F401

from util import DEMO, IS_WIN, is_admin, relaunch_as_admin
import psutil

import anim
import licencia
from sidebar import BarraLateral
import logo_data
import updater
import version

from widgets import BORDER, PRO_THEME, themed_logo
from widgets import (BG, CYAN, F, FG, GREEN, MUTED, PANEL2, PINK, RED, SIDE, VIOLET, YELLOW, GradientBar, MiniBar,
                     NeonButton, PanelGlow, PanelRedondo, PulseLogo, ScrollFrame, SparkField, badge, install_mousewheel, mix, round_rect, setup_styles)

SECTIONS = [
    ("INICIO", [("home", "⌂", "Inicio"), ("analysis", "◎", "Análisis de PC"), ("score", "★", "Puntuación")]),
    ("OPTIMIZAR", [("optimize", "⚡", "Optimizar"), ("clean", "✦", "Limpieza"), ("shaders", "❖", "Limpiar shaders"),
                   ("arranque", "⏻", "Gestor de arranque"), ("bench", "▲", "Antes y después")]),
    ("GAMING", [("games", "▣", "Mis juegos"), ("gameprof", "✧", "Ajustes de juego"), ("booster", "☢", "Modo Extremo"),
                ("monitor", "≈", "Monitor"), ("diag", "◈", "Diagnóstico"), ("fps", "▤", "FPS reales")]),
    ("AVANZADO", [("tweaks", "☄", "Tweaks"), ("cuello", "⬆", "Qué pieza mejorar"), ("bios", "◉", "BIOS"), ("oc", "⚙", "Overclock")]),
    ("SISTEMA", [("health", "♥", "Salud del PC"), ("debloat", "✖", "Quitar bloatware"),
                ("history", "↺", "Historial / Deshacer"), ("update", "⟳", "Actualizaciones"), ("license", "★", "Licencia")]),
]
PAGES = [item for _title, items in SECTIONS for item in items]


class NavItem(tk.Canvas):
    """Entrada del menú: el fondo y el color se funden suavemente, la barra lateral «crece» al activarse
    y puede llevar un punto que late (p. ej. modo automático activo)."""
    H = 27

    def __init__(self, parent, icon, text, command):
        super().__init__(parent, bg=SIDE, height=self.H, highlightthickness=0, bd=0, cursor="hand2")
        self.icon, self.text, self.command = icon, text, command
        self.hov = self.act = 0.0
        self.active = self._hover_goal = False
        self.dot, self.pulse, self._job = None, 0.0, None
        self.pro = False
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

    def set_pro(self, on):
        self.pro = on
        self._draw()

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
                round_rect(self, 8, 2, w - 8, self.H - 2, 13, fill=mix(SIDE, PANEL2, k), outline="")
            if self.act > 0.02:
                hgt = 4 + 14 * self.act
                round_rect(self, 8, self.H / 2 - hgt / 2, 11, self.H / 2 + hgt / 2, 1.5, fill=CYAN, outline="")
            col = mix(mix(MUTED, FG, self.hov), CYAN, self.act)
            self.create_text(27, self.H / 2, text=self.icon, fill=col, font=F(11, True), anchor="center")
            self.create_text(44, self.H / 2, text=self.text, fill=col, font=F(10, True), anchor="w")
            if self.pro:
                self.create_text(w - 16, self.H / 2, text="PRO", fill=mix(SIDE, YELLOW, 0.8), font=F(7, True), anchor="e")
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
        # Tras la animación «Bienvenido a PRO» la app nueva carga en segundo plano y aparece justo cuando la animación acaba.
        _show_at = os.environ.pop("HELLOP_SHOW_AT", None)
        if _show_at:
            self.withdraw()
        self.title("HellOP  ·  " + ("PRO" if PRO_THEME else "FREE") + ("  ·  MODO DEMO" if DEMO else ""))
        self.geometry("1140x840")
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
        sidehost = tk.Frame(body, bg=BG, width=252)
        sidehost.pack(side="left", fill="y", padx=(12, 0), pady=12)
        sidehost.pack_propagate(False)
        self.sidebar = BarraLateral(sidehost, SECTIONS, self.show)
        self.sidebar.pack(fill="both", expand=True)
        self.nav = self.sidebar.nav
        self.bar_cpu, self.bar_ram, self.live_lbl = self.sidebar.bar_cpu, self.sidebar.bar_ram, self.sidebar.live_lbl
        marco = PanelRedondo(body, fill=BG, line=mix(BORDER, CYAN, 0.35), radius=28, margen=6)
        marco.pack(side="left", fill="both", expand=True, padx=12, pady=12)
        self.content = marco.body

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
        from page_license import LicensePage
        from page_locked import LockedPage
        from page_health import HealthPage
        from page_home import HomePage
        from page_monitor import MonitorPage
        from page_oc import OcPage
        from page_history import HistoryPage
        from page_optimize import OptimizePage
        from page_tweaks import TweaksPage
        from page_update import UpdatePage
        from page_arranque import ArranquePage
        from page_cuello import CuelloPage
        from page_puntuacion import ScorePage
        from page_shaders import ShadersPage
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
            "health": HealthPage(self.content, self),
            "debloat": DebloatPage(self.content, self),
            "update": UpdatePage(self.content, self),
            "arranque": ArranquePage(self.content, self),
            "cuello": CuelloPage(self.content, self),
            "score": ScorePage(self.content, self),
            "shaders": ShadersPage(self.content, self),
            "license": LicensePage(self.content, self),
            "locked": LockedPage(self.content, self),
        }
        self.refresh_license()
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
        self.after(6000, self._check_revoked)
        self.after(1500, self._asistente_primera_vez)
        self.after(1500, self.pages["games"].boot)
        self.after(600, self._admin_prompt)
        self.after(300, self._titlebar_start)
        self.after(450, self._poner_icono_windows)
        self.after(2500, self._poner_icono_windows)
        if _show_at:
            try:
                espera = max(0, int((float(_show_at) - time.time()) * 1000))
            except ValueError:
                espera = 0
            self.after(espera, self.deiconify)

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
            ico.write_bytes(self._pro_ico() if PRO_THEME else base64.b64decode(logo_data.ICO))
            self._ico_path = str(ico)
            self.iconbitmap(default=str(ico))
        except Exception:  # noqa: BLE001
            pass

    def _pro_ico(self):
        """Icono .ico del color elegido, en el formato clásico (BMP de 32 bits) que entiende cualquier Windows y Tk.
        Lleva 4 tamaños: 128, 64, 32 y 16."""
        import struct
        fuentes = [themed_logo(tk.PhotoImage(data=logo_data.LOGO_128), force=True),
                   themed_logo(tk.PhotoImage(data=logo_data.LOGO_64), force=True)]
        imgs = [fuentes[0], fuentes[1], fuentes[1].subsample(2, 2), fuentes[0].subsample(8, 8)]
        entradas = []
        for im in imgs:
            w, h = im.width(), im.height()
            filas, mascara = [], []
            for y in range(h - 1, -1, -1):                            # los .ico guardan las filas de abajo arriba
                px, bits = bytearray(), [0] * (((w + 31) // 32) * 32)
                for x in range(w):
                    if im.transparency_get(x, y):
                        px += b"\x00\x00\x00\x00"
                        bits[x] = 1
                    else:
                        r, g, b = im.get(x, y)
                        px += bytes((b, g, r, 255))
                filas.append(bytes(px))
                mascara.append(bytes(int("".join(map(str, bits[k:k + 8])), 2) for k in range(0, len(bits), 8)))
            cab = struct.pack("<IiiHHIIiiII", 40, w, h * 2, 1, 32, 0, 0, 0, 0, 0, 0)
            entradas.append((w, h, cab + b"".join(filas) + b"".join(mascara)))
        out = struct.pack("<HHH", 0, 1, len(entradas))
        off = 6 + 16 * len(entradas)
        cuerpo = b""
        for w, h, data in entradas:
            out += struct.pack("<BBBBHHII", w % 256, h % 256, 0, 0, 1, 32, len(data), off + len(cuerpo))
            cuerpo += data
        return out + cuerpo

    def _poner_icono_windows(self):
        """Pone el icono directamente en la ventana (título y barra de tareas) sin depender del análisis de Tk."""
        if not IS_WIN or DEMO or not getattr(self, "_ico_path", None):
            return
        try:
            import ctypes
            u = ctypes.windll.user32
            u.LoadImageW.restype = ctypes.c_void_p
            u.LoadImageW.argtypes = [ctypes.c_void_p, ctypes.c_wchar_p, ctypes.c_uint, ctypes.c_int, ctypes.c_int, ctypes.c_uint]
            u.SendMessageW.argtypes = [ctypes.c_void_p, ctypes.c_uint, ctypes.c_size_t, ctypes.c_void_p]
            u.GetParent.restype = ctypes.c_void_p
            u.GetParent.argtypes = [ctypes.c_void_p]
            hwnd = u.GetParent(self.winfo_id()) or self.winfo_id()
            for metrica, cual in ((11, 1), (49, 0)):                  # SM_CXICON→ICON_BIG, SM_CXSMICON→ICON_SMALL
                s = u.GetSystemMetrics(metrica)
                h = u.LoadImageW(None, self._ico_path, 1, s, s, 0x10)   # IMAGE_ICON, LR_LOADFROMFILE
                if h:
                    u.SendMessageW(hwnd, 0x80, cual, h)               # WM_SETICON
        except Exception:  # noqa: BLE001
            pass

    # ---- barra de título de Windows: del color del tema, con un pulso suave -----------
    def _titlebar_start(self):
        """Windows 11: pinta la barra de título (y su borde) con el color del tema y la hace «respirar».
        En Windows 10 o anteriores no hace nada (la barra queda como siempre)."""
        if not IS_WIN or DEMO:
            return
        try:
            import ctypes
            from ctypes import byref, c_int
            hwnd = ctypes.windll.user32.GetParent(self.winfo_id()) or self.winfo_id()
            dwm = ctypes.windll.dwmapi.DwmSetWindowAttribute

            def rgb(c):                                               # COLORREF = 0x00BBGGRR
                r, g, b = int(c[1:3], 16), int(c[3:5], 16), int(c[5:7], 16)
                return (b << 16) | (g << 8) | r
            dwm(hwnd, 20, byref(c_int(1)), 4)                         # botones claros sobre fondo oscuro
            dwm(hwnd, 36, byref(c_int(rgb(FG))), 4)                   # texto del título
        except Exception:  # noqa: BLE001
            return
        import math
        import time as _t
        t0 = _t.time()

        def tick():
            try:
                k = 0.5 + 0.5 * math.sin((_t.time() - t0) * 1.6)
                col = rgb(mix(SIDE, CYAN, 0.10 + 0.28 * k))
                dwm(hwnd, 35, byref(c_int(col)), 4)                   # color de la barra
                dwm(hwnd, 34, byref(c_int(rgb(mix(BORDER, CYAN, 0.2 + 0.6 * k)))), 4)   # borde
                self.after(70, tick)
            except Exception:  # noqa: BLE001
                pass
        tick()

    # ---- cabecera -------------------------------------------------------
    def _build_header(self):
        h = tk.Frame(self, bg=SIDE)
        h.pack(fill="x")
        self._logo = themed_logo(tk.PhotoImage(data=logo_data.LOGO_64))
        self._logo_big = themed_logo(tk.PhotoImage(data=logo_data.LOGO_128))
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

    def refresh_license(self):
        """Actualiza la etiqueta de licencia de la cabecera y las marcas PRO del menú."""
        st = licencia.status()
        txt = {"owner": "CREADOR", "pro": "PRO" + (f" · {st['days']} d" if st["days"] is not None else ""), "free": "GRATIS",
               "expired": "CLAVE CADUCADA", "invalid": "CLAVE NO VÁLIDA"}[st["level"]]
        col = {"owner": PINK, "pro": CYAN, "free": MUTED, "expired": YELLOW, "invalid": RED}[st["level"]]
        if getattr(self, "lic_badge", None):
            self.lic_badge.destroy()
        self.lic_badge = badge(self.hdr_right, txt, col)
        self.lic_badge.pack(side="left", padx=6, before=self.hdr_right.winfo_children()[0])
        self.lic_badge.bind("<Button-1>", lambda e: self.show("license"))
        for k, n in self.nav.items():
            n.set_pro(licencia.locked(k))
        home = getattr(self, "pages", {}).get("home")
        if home is not None and getattr(home, "caja_lic", None):
            home.caja_lic.set(st)

    def mark_update_available(self, latest):
        """Muestra en la cabecera un botón verde cuando hay una versión nueva."""
        if self.upd_btn is not None:
            return
        self.upd_btn = NeonButton(self.hdr_right, f"⬇ Actualización v{latest} disponible", lambda: self.show("update"),
                                  color=GREEN, filled=True, padx=10, pady=4, font=F(9, True))
        self.upd_btn.pack(side="left", padx=6)
        self.status(f"Hay una versión nueva: v{latest}")

    def abrir_asistente(self):
        """Abre el asistente de primera vez (también desde el botón de Inicio)."""
        import asistente
        ya = getattr(self, "_asistente", None)
        if ya is not None and ya.winfo_exists():
            return
        self._asistente = asistente.Asistente(self, lambda destino: self.show(destino) if destino else None)

    def _asistente_primera_vez(self):
        import asistente
        if os.environ.get("HELLOP_ASISTENTE") == "1" or (not DEMO and not asistente.visto()):
            self.abrir_asistente()

    def _check_revoked(self):
        """Descarga la lista de claves anuladas (al abrir y cada 3 horas). Si la tuya está, se bloquean las funciones PRO."""
        if DEMO:
            return
        antes = licencia.status()["level"]

        def trabajo():
            licencia.refresh_revoked()
            return licencia.status()

        def hecho(st):
            if antes in ("pro",) and st["level"] == "invalid":
                self.refresh_license()
                self.show("license")
                messagebox.showinfo("Clave anulada", st["msg"] + "\n\nHellOP vuelve al modo gratis. Se verá en verde al reiniciar.")
            elif antes != st["level"]:
                self.refresh_license()
        self.bg(trabajo, hecho, lambda e: None)
        self.after(3 * 3600 * 1000, self._check_revoked)

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

    def pro_welcome(self):
        """Animación «Bienvenido a PRO». Si la app estaba en verde, la versión morada se abre sola mientras suena
        la animación y aparece justo cuando termina (sin pantalla negra)."""
        from bienvenida import DURACION, LANZAR, Bienvenida
        logo = themed_logo(tk.PhotoImage(data=logo_data.LOGO_128), force=True)
        self._pro_logo = logo
        self._relanzada = False

        def lanzar():
            if PRO_THEME or DEMO or not IS_WIN:
                return
            try:
                self.pages["games"].shutdown()
                self.pages["monitor"].shutdown()
                self.pages["booster"].shutdown()
            except Exception:  # noqa: BLE001
                pass
            os.environ["HELLOP_SHOW_AT"] = str(time.time() + (DURACION - LANZAR) - 0.15)
            self._relanzada = relaunch_as_admin()
            os.environ.pop("HELLOP_SHOW_AT", None)

        def fin():
            if self._relanzada:
                self.destroy()
                sys.exit(0)
            ov.destroy()
            if not PRO_THEME:
                self.status("PRO activado. Cierra y abre HellOP para verlo en morado.")
        ov = Bienvenida(self, logo, fin, bg0=BG, on_launch=lanzar)

    def restart_now(self):
        """Reinicia HellOP (por ejemplo, para aplicar un color nuevo)."""
        if DEMO or not IS_WIN:
            self.status("Reinicio no disponible en este modo: cierra y abre HellOP.")
            return
        try:
            self.pages["games"].shutdown()
            self.pages["monitor"].shutdown()
            self.pages["booster"].shutdown()
        except Exception:  # noqa: BLE001
            pass
        if relaunch_as_admin():
            self.destroy()
            sys.exit(0)
        self.status("No pude reiniciar solo: cierra y abre HellOP.")

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
        names = {k: t for _s, items in SECTIONS for k, _i, t in items}
        if licencia.locked(key):                    # función PRO sin clave: se enseña la pantalla de bloqueo
            self.pages["locked"].set(names.get(key, key))
            page = self.pages["locked"]
        else:
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
