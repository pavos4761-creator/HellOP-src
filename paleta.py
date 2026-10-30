"""Buscador rápido (Ctrl+K): escribe y salta a cualquier apartado de HellOP."""
import tkinter as tk
import unicodedata

from widgets import BORDER, CYAN, F, FG, MUTED, PANEL, PANEL2, SIDE, mix

CLAVES = {   # palabras extra para encontrar cada apartado
    "home": "inicio principal nota", "analysis": "analisis pc hardware ram cpu gpu", "score": "puntuacion nota medalla logros",
    "optimize": "optimizar gaming trabajo extremo perfil", "streaming": "streaming obs directo twitch emitir", "doctor": "doctor sintomas problema tirones crujidos cierra lento por que", "movil": "movil telefono celular qr segunda pantalla temperaturas remoto", "noche": "noche silencio ruido ventiladores horario calor", "mando": "mando gamepad control xbox ps5 dualsense input lag",
    "clean": "limpieza basura temporales disco", "shaders": "shaders cache nvidia amd", "arranque": "arranque inicio programas startup",
    "games": "juegos biblioteca steam", "gameprof": "ajustes de juego perfil por juego", "booster": "modo extremo booster procesos",
    "monitor": "monitor temperaturas uso", "diag": "diagnostico problemas", "fps": "fps reales medir tirones",
    "tweaks": "tweaks ajustes registro latencia", "cuello": "cuello de botella pieza mejorar", "bios": "bios xmp expo rebar",
    "oc": "overclock oc", "health": "salud pc disco smart", "debloat": "bloatware quitar apps", "history": "historial deshacer cambios",
    "update": "actualizaciones version nueva", "license": "licencia pro clave",
    "cmd:informe": "informe exportar html guardar compartir reporte", "cmd:atras": "atras volver anterior", "cmd:modo": "modo claro oscuro negro mate tema color",
}


def _n(s):
    return "".join(c for c in unicodedata.normalize("NFD", s.lower()) if unicodedata.category(c) != "Mn")


class Paleta(tk.Toplevel):
    def __init__(self, app, entradas, comandos=()):
        super().__init__(app)
        self.app, self.res, self.sel = app, [], 0
        self.comandos = {k: f for k, _i, _t, f in comandos}
        self.entradas = list(entradas) + [(k, i, t) for k, i, t, _f in comandos]
        self.overrideredirect(True)
        self.configure(bg=mix(BORDER, CYAN, 0.5))
        w, h = 460, 330
        x = app.winfo_rootx() + (app.winfo_width() - w) // 2
        y = app.winfo_rooty() + 90
        self.geometry(f"{w}x{h}+{x}+{y}")
        caja = tk.Frame(self, bg=SIDE)
        caja.pack(fill="both", expand=True, padx=1, pady=1)
        self.v = tk.StringVar()
        self.e = tk.Entry(caja, textvariable=self.v, font=F(13), bg=PANEL2, fg=FG, insertbackground=CYAN, relief="flat", bd=0)
        self.e.pack(fill="x", padx=14, pady=(14, 8), ipady=7)
        self.lista = tk.Frame(caja, bg=SIDE)
        self.lista.pack(fill="both", expand=True, padx=8)
        tk.Label(caja, text="↑↓ moverse   ·   Enter abrir   ·   Esc cerrar", font=F(8), fg=MUTED, bg=SIDE).pack(pady=(0, 8))
        self.v.trace_add("write", lambda *_: self.filtra())
        for k, f in (("<Escape>", lambda e: self.destroy()), ("<Return>", lambda e: self.abre()),
                     ("<Down>", lambda e: self.mueve(1)), ("<Up>", lambda e: self.mueve(-1))):
            self.e.bind(k, f)
        self.bind("<FocusOut>", lambda e: self.after(120, self._cierra_si_pierde))
        self.filtra()
        self.after(10, self.e.focus_force)

    def _cierra_si_pierde(self):
        try:
            if self.focus_displayof() is None:
                self.destroy()
        except tk.TclError:
            pass

    def filtra(self):
        q = _n(self.v.get()).split()
        self.res = [(k, i, t) for k, i, t in self.entradas if all(w in _n(t + " " + CLAVES.get(k, "")) for w in q)][:8]
        self.sel = 0
        self.pinta()

    def pinta(self):
        for w in self.lista.winfo_children():
            w.destroy()
        if not self.res:
            tk.Label(self.lista, text="Nada coincide. Prueba con «fps», «mando», «limpieza»…", font=F(10), fg=MUTED, bg=SIDE).pack(pady=20)
            return
        for n, (k, icon, t) in enumerate(self.res):
            on = n == self.sel
            f = tk.Frame(self.lista, bg=mix(SIDE, CYAN, 0.22) if on else SIDE, cursor="hand2")
            f.pack(fill="x", pady=1)
            tk.Label(f, text=icon, font=F(11, True), fg=CYAN if on else MUTED, bg=f["bg"], width=3).pack(side="left", pady=6)
            tk.Label(f, text=t, font=F(10, True), fg=FG if on else MUTED, bg=f["bg"], anchor="w").pack(side="left", fill="x", expand=True)
            for w in (f, *f.winfo_children()):
                w.bind("<Button-1>", lambda e, k=k: self.ir(k))

    def mueve(self, d):
        if self.res:
            self.sel = (self.sel + d) % len(self.res)
            self.pinta()
        return "break"

    def abre(self):
        if self.res:
            self.ir(self.res[self.sel][0])

    def ir(self, key):
        self.destroy()
        if key in self.comandos:
            self.comandos[key]()
        else:
            self.app.show(key)
