"""Pantalla «FPS reales»: mide los FPS, el 1 % low y la latencia de fotogramas de tu juego, y compara antes/después."""
import threading
import time

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QHBoxLayout, QLineEdit, QVBoxLayout, QWidget

import fps
from util import DEMO

from ..widgets import Barra, Boton, Etiqueta, Pagina, Tarjeta, fila, vacia
from .diagnostico import _kv


def _vbox(spacing=8):
    w = QWidget()
    v = QVBoxLayout(w)
    v.setContentsMargins(0, 0, 0, 0)
    v.setSpacing(spacing)
    return w, v


class Fps(Pagina):
    titulo_texto = "FPS reales"
    sub_texto = "Mide los FPS de tu juego y comprueba con números si un cambio ayudó de verdad."

    def __init__(self, app):
        super().__init__(app)
        self.busy = False
        self.stop = None
        self.mode = "now"
        self.run_a = self.run_b = None
        self.seconds = 30

        # --- explicación (se coloca al final de la pantalla para que los resultados se vean arriba)
        expl = Tarjeta(tone="yellow", titulo="Cómo se usa (importante para que la medición valga)")
        for t in ("Abre tu juego y ponte en una situación que puedas REPETIR: en VALORANT, el Campo de tiro caminando por la misma ruta; "
                  "en otros juegos, el mismo mapa y el mismo recorrido.",
                  "Elige el juego, pulsa medir y tendrás 5 s para volver al juego (Alt+Tab). Juega con normalidad mientras mide.",
                  "Para comparar, mide dos veces en la MISMA situación. Entre dos mediciones iguales hay ≈3-4 % de variación normal: "
                  "diferencias menores que eso no cuentan.",
                  "Usa PresentMon (gratis, de Intel). Lee los eventos de Windows y no se mete dentro del juego. "
                  "Se descarga una sola vez y se verifica su huella. HellOP debe estar como administrador."):
            expl.add(Etiqueta("•  " + t, "small"))

        # --- selección de juego
        sel = Tarjeta(tone="teal", titulo="¿Qué juego?")
        self.var = QLineEdit(fps.KNOWN_GAMES[0])
        self.var.setMinimumWidth(320)
        sel.add(fila(self.var, Boton("↻  Juegos abiertos", self.refresh_candidates, kind="soft"), None, espacio=10))
        self.chips = QWidget()
        self.chips_lay = QHBoxLayout(self.chips)
        self.chips_lay.setContentsMargins(0, 0, 0, 0)
        self.chips_lay.setSpacing(6)
        sel.add(self.chips)
        self.dur_btns = {}
        fila_dur = [Etiqueta("Duración:", "muted", wrap=False)]
        for s in (30, 60, 90):
            b = Boton(f"{s} s", lambda s_=s: self.set_dur(s_), kind="soft")
            self.dur_btns[s] = b
            fila_dur.append(b)
        fila_dur.append(None)
        sel.add(fila(*fila_dur, espacio=8))
        self.add(sel)

        # --- modos
        self.m_now = Boton("▶  MEDIR AHORA", lambda: self.set_mode("now"), kind="primary")
        self.m_ab = Boton("⇄  ASISTENTE ANTES / DESPUÉS", lambda: self.set_mode("ab"), kind="soft")
        self.msg = Etiqueta("", "muted")
        self.add(fila(self.m_now, self.m_ab, self.msg, espacio=10))
        self.pb = Barra(0, "accent")
        self.pb.hide()
        self.add(self.pb)

        self.f_now, lay_now = _vbox()
        self.f_ab, lay_ab = _vbox()
        # modo medir ahora
        self.b_go = Boton("▶  EMPEZAR MEDICIÓN", lambda: self.measure("now"), kind="primary")
        lay_now.addWidget(self.b_go, 0, Qt.AlignmentFlag.AlignLeft)
        self.now_res, self.now_lay = _vbox()
        lay_now.addWidget(self.now_res)
        # modo asistente
        lay_ab.addWidget(Etiqueta("1) Mide ANTES (A).   2) Haz el cambio que quieras probar: un tweak, un ajuste del juego, un driver…   "
                                  "3) Mide DESPUÉS (B) en la misma situación.   4) Te digo si de verdad ayudó.", "muted"))
        self.b_a = Boton("1 · MEDIR ANTES (A)", lambda: self.measure("a"), kind="primary")
        self.b_b = Boton("3 · MEDIR DESPUÉS (B)", lambda: self.measure("b"), kind="primary", tone="green")
        self.b_b.set_enabled(False)
        lay_ab.addWidget(fila(self.b_a, self.b_b, Boton("Empezar de nuevo", self.reset_ab, kind="ghost"), None, espacio=10))
        cambia = [Etiqueta("2) Cambiar algo:", "muted", wrap=False)]
        for k, label in (("tweaks", "Tweaks"), ("gameprof", "Ajustes de juego")):
            cambia.append(Boton(label, lambda k_=k: self.app.ir(k_), kind="soft"))
        cambia.append(None)
        lay_ab.addWidget(fila(*cambia, espacio=8))
        self.ab_res, self.ab_lay = _vbox()
        lay_ab.addWidget(self.ab_res)
        self.add(self.f_now)
        self.add(self.f_ab)

        self.hist, self.hist_lay = _vbox()
        self.add(self.hist)
        self.add(expl)
        self.set_dur(30)
        self.set_mode("now")
        self.render_history()

    # ------------------------------------------------------------------
    def al_mostrar(self):
        self.refresh_candidates()

    def apaga(self):
        if self.stop:
            self.stop.set()

    def set_dur(self, s):
        self.seconds = s
        for k, b in self.dur_btns.items():
            b.estilo(kind="primary" if k == s else "soft")

    def set_mode(self, mode):
        self.mode = mode
        self.f_now.setVisible(mode == "now")
        self.f_ab.setVisible(mode == "ab")
        self.m_now.estilo(kind="primary" if mode == "now" else "soft")
        self.m_ab.estilo(kind="primary" if mode == "ab" else "soft")

    def say(self, text, tone="muted"):
        self.msg.setText(text)
        self.msg.tono(tone)

    def refresh_candidates(self):
        vacia(self.chips_lay)
        names = fps.running_candidates()
        if names and names[0] in fps.KNOWN_GAMES:
            self.var.setText(names[0])
        for n in names[:6]:
            self.chips_lay.addWidget(Boton(n, lambda n_=n: self.var.setText(n_), kind="primary" if n in fps.KNOWN_GAMES else "soft",
                                           tone="green" if n in fps.KNOWN_GAMES else None))
        self.chips_lay.addStretch(1)

    def reset_ab(self):
        self.run_a = self.run_b = None
        self.b_b.set_enabled(False)
        vacia(self.ab_lay)

    # ------------------------------------------------------------------
    def measure(self, slot):
        if self.busy:
            if self.stop:
                self.stop.set()
            return
        proc = self.var.text().strip()
        if not proc.lower().endswith(".exe"):
            self.say("Escribe el nombre del programa del juego, por ejemplo VALORANT-Win64-Shipping.exe", "yellow")
            return
        if not DEMO and not fps.have_presentmon() and not self.app.pregunta(
                "Descargar PresentMon", "Para medir FPS hace falta PresentMon, una herramienta gratuita de Intel (≈1 MB).\n\n"
                "Se descarga una sola vez de GitHub y se comprueba su huella SHA256 antes de usarla.\n\n¿Descargarla ahora?"):
            return
        self.busy, self.stop = True, threading.Event()
        activo = {"now": self.b_go, "a": self.b_a, "b": self.b_b}[slot]
        for b in (self.b_go, self.b_a, self.b_b):
            if b is activo:
                b.set_enabled(True)
                b.set_text("■  Cancelar")
            else:
                b.set_enabled(False)
        self.pb.pon(0)
        self.pb.show()
        variant = 1 if slot == "b" else 0
        sec, stop = self.seconds, self.stop

        def work():
            fps.ensure_presentmon(lambda p, m: self.app.ui(self._prog, p * 0.0, m))
            for i in range(5, 0, -1):
                if stop.is_set():
                    raise fps.FpsError("Medición cancelada")
                self.app.ui(self._prog, 0, f"Vuelve al juego (Alt+Tab): empiezo en {i}…")
                time.sleep(1)
            ft, g, c = fps.capture(proc, sec, lambda p, m: self.app.ui(self._prog, p, m), stop, variant)
            return fps.analyze(ft, g, c)

        self.app.bg(work, lambda m: self._done(slot, proc, m), self._fail)

    def _prog(self, p, m):
        self.pb.pon(int(p * 100))
        self.say(m, "accent")

    def _restore_buttons(self):
        self.busy, self.stop = False, None
        self.pb.hide()
        self.b_go.set_text("▶  EMPEZAR MEDICIÓN")
        self.b_a.set_text("1 · MEDIR ANTES (A)")
        self.b_b.set_text("3 · MEDIR DESPUÉS (B)")
        self.b_go.set_enabled(True)
        self.b_a.set_enabled(True)
        self.b_b.set_enabled(self.run_a is not None)

    def _fail(self, e):
        self._restore_buttons()
        self.say(("✗ " + str(e)) if isinstance(e, fps.FpsError) else f"✗ Error: {type(e).__name__}: {e}", "red")

    def _done(self, slot, proc, m):
        self._restore_buttons()
        self.say("✓ Medición terminada", "green")
        fps.save_run(proc, m, {"now": "", "a": "A (antes)", "b": "B (después)"}[slot])
        if slot == "now":
            self._show(self.now_lay, m, "Resultado")
        elif slot == "a":
            self.run_a = m
            self.b_b.set_enabled(True)
            self._show(self.ab_lay, m, "A · ANTES")
            self.ab_lay.addWidget(Etiqueta("Ahora cambia lo que quieras probar y mide DESPUÉS (B) en la misma situación.", "h3", "yellow"))
        else:
            self.run_b = m
            self._show(self.ab_lay, self.run_a, "A · ANTES")
            self._show(self.ab_lay, m, "B · DESPUÉS", keep=True)
            self._compare()
        self.render_history()

    # ------------------------------------------------------------------
    def _show(self, lay, m, title, keep=False):
        if not keep:
            vacia(lay)
        c = Tarjeta(tone="accent", titulo=title)
        cifras = []
        for label, val, tone in (("FPS medios", m["avg"], "accent"), ("1 % low", m["low1"], "yellow"), ("0,1 % low", m["low01"], "red")):
            cifras.append(self._cifra(f"{val:.0f}", label, tone))
        cifras.append(None)
        c.add(fila(*cifras, espacio=30))
        c.add(_kv([("Fotograma típico", f"{m['ft_med']} ms"),
                   ("El 1 % más lento tarda", f"{m['ft_p99']} ms o más"),
                   ("El peor fotograma", f"{m['ft_max']} ms"),
                   ("Tirones fuertes", f"{m['stutters']} en {m['seconds']:.0f} s  ({m['stutter_per_min']}/min)")]))
        if m.get("verdict"):
            c.add(Etiqueta("→ " + m["verdict"], "h3"))
        lay.addWidget(c)

    @staticmethod
    def _cifra(valor, etiqueta, tone):
        w, v = _vbox(0)
        v.addWidget(Etiqueta(valor, "big", tone, wrap=False))
        v.addWidget(Etiqueta(etiqueta, "small", wrap=False))
        return w

    def _compare(self):
        txt, col, d = fps.compare(self.run_a, self.run_b)
        c = Tarjeta(tone=col, titulo="Comparación A → B")
        c.add(Etiqueta(txt, "h3", col))
        sg = lambda v: f"{v:+.1f} %"  # noqa: E731
        c.add(_kv([("FPS medios", sg(d["avg"])), ("1 % low", sg(d["low1"])), ("0,1 % low", sg(d["low01"])),
                   ("Tirones fuertes", f"{d['stutters']:+d}")]))
        self.ab_lay.addWidget(c)

    def render_history(self):
        vacia(self.hist_lay)
        h = fps.load_history()[-8:][::-1]
        if not h:
            return
        c = Tarjeta(tone="muted", titulo="Últimas mediciones")
        for r in h:
            line = f"{r['ts']}   {r['process'][:26]:<26}  {r['avg']:>6.0f} FPS   1 % low {r['low1']:>5.0f}   0,1 % low {r['low01']:>5.0f}   {r.get('label', '')}"
            c.add(Etiqueta(line, "mono", wrap=False))
        self.hist_lay.addWidget(c)
