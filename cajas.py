"""Cuadros redondeados de Inicio: licencia («PRO ACTIVO · quedan N días») y asistente."""
import tkinter as tk

from widgets import BORDER, CYAN, F, FG, MUTED, PANEL, PINK, RED, SIDE, TRACK, YELLOW, mix, round_rect


class _CajaRedonda(tk.Canvas):
    """Cuadro redondeado de la Inicio (fondo suave del color de acento)."""
    ALTO = 70

    def __init__(self, parent, command, fondo=None, ancho=200):
        self.fondo = fondo or SIDE
        super().__init__(parent, bg=self.fondo, width=ancho, height=self.ALTO, highlightthickness=0, bd=0, cursor="hand2")
        self.command, self.hov = command, False
        self.bind("<Configure>", lambda e: self._draw())
        self.bind("<Enter>", lambda e: self._h(True))
        self.bind("<Leave>", lambda e: self._h(False))
        self.bind("<Button-1>", lambda e: self.command())

    def _h(self, on):
        self.hov = on
        self._draw()

    def _contenido(self, w):
        pass

    def _col(self):
        return CYAN

    def _draw(self):
        try:
            self.delete("all")
            w = max(40, self.winfo_width())
            c = self._col()
            round_rect(self, 1, 1, w - 1, self.ALTO - 1, 20, fill=mix(PANEL, c, 0.06 if self.hov else 0.0),
                       outline=mix(BORDER, c, 0.6 if self.hov else 0.0))
            self._contenido(w)
        except tk.TclError:
            pass


class CajaLicencia(_CajaRedonda):
    """«PRO ACTIVO · quedan N días» (o plan gratis / creador / caducada), con barra de días que quedan."""
    ALTO = 72

    def __init__(self, parent, command, fondo=None, ancho=200):
        super().__init__(parent, command, fondo, ancho)
        self.st = {"level": "free", "days": None}

    def set(self, st):
        self.st = st
        self._draw()

    def textos(self):
        lv, d = self.st.get("level"), self.st.get("days")
        if lv == "owner":
            return "CREADOR", "Modo creador: sin límites", None
        if lv == "pro":
            return "PRO ACTIVO", ("Quedan %d %s" % (d, "día" if d == 1 else "días")), min(100.0, d / 30 * 100)
        if lv == "expired":
            return "CLAVE CADUCADA", "Pulsa para poner una nueva", 0
        if lv == "invalid":
            return "CLAVE NO VÁLIDA", "Pulsa para revisarla", 0
        return "PLAN GRATIS", "Desbloquea todo con una clave", None

    def _col(self):
        return {"owner": PINK, "pro": CYAN, "expired": YELLOW, "invalid": RED}.get(self.st.get("level"), CYAN)

    def _contenido(self, w):
        t, sub, pct = self.textos()
        c = self._col()
        self.create_oval(16, 15, 24, 23, fill=c, outline="")
        self.create_oval(13, 12, 27, 26, outline=mix(PANEL, c, 0.4))
        self.create_text(34, 19, text=t, anchor="w", fill=c, font=F(9, True))
        self.create_text(16, 40, text=sub, anchor="w", fill=FG, font=F(9))
        by = 56
        round_rect(self, 16, by, w - 16, by + 6, 3, fill=TRACK, outline="")
        if pct:
            round_rect(self, 16, by, 16 + max(6, (w - 32) * pct / 100), by + 6, 3, fill=c, outline="")


class CajaAsistente(_CajaRedonda):
    ALTO = 72

    def _contenido(self, w):
        self.create_text(16, 17, text="Hazlo en 1 minuto", anchor="w", fill=FG, font=F(10, True))
        self.create_text(16, 36, text="Te guía paso a paso.", anchor="w", fill=MUTED, font=F(8))
        self.create_text(16, 56, text="✧  Abrir asistente", anchor="w", fill=CYAN, font=F(9, True))
