"""Asistente de primera vez: 5 pasos guiados para quien abre HellOP por primera vez (o cuando lo vuelve a pedir).

1 Bienvenida · 2 Tu PC · 3 Lo más importante · 4 Lo seguro (limpieza y, con PRO, ajustes sin riesgo) · 5 Listo.
Nada se aplica sin que la persona lo marque y lo apruebe. Todo lo que se aplica queda en el Historial y se puede deshacer.
"""
import json
import tkinter as tk

import actions
import cleanup
import hidden
import licencia
import sysinfo
import tweaks
from util import APP_DIR, DEMO, fmt_bytes, is_admin
from widgets import (BG, CYAN, F, FG, GREEN, MUTED, PANEL, PINK, RED, YELLOW, Card, NeonButton, ScrollFrame, WrapLabel,
                     checkbox, mix)

FLAG = APP_DIR / "asistente.json"
PASOS = ["Bienvenida", "Tu PC", "Lo importante", "Lo seguro", "Listo"]
SEV_COL = {"bad": RED, "warn": YELLOW, "info": CYAN}
SEV_TXT = {"bad": "PROBLEMA", "warn": "MEJORABLE", "info": "A REVISAR"}


def visto():
    try:
        return bool(json.loads(FLAG.read_text("utf-8")).get("hecho"))
    except Exception:  # noqa: BLE001
        return False


def marcar_visto():
    try:
        APP_DIR.mkdir(parents=True, exist_ok=True)
        FLAG.write_text(json.dumps({"hecho": True}), "utf-8")
    except OSError:
        pass


class Asistente(tk.Frame):
    """Capa a pantalla completa con los pasos. `ir(pagina)` abre una página de la app al terminar."""

    def __init__(self, app, on_close):
        super().__init__(app, bg=BG)
        self.app, self.on_close = app, on_close
        self.i = 0
        self.pro = licencia.is_pro()
        self.hw = self.hallazgos = self.limpieza = self.ajustes = None
        self.hecho = {"liberado": 0, "ajustes": 0}
        self.vars = {}
        self.cerrado = False
        self.place(x=0, y=0, relwidth=1, relheight=1)
        tk.Misc.lift(self)
        box = tk.Frame(self, bg=BG)
        box.pack(fill="both", expand=True, padx=70, pady=26)
        top = tk.Frame(box, bg=BG)
        top.pack(fill="x")
        self.dots = tk.Canvas(top, width=190, height=22, bg=BG, highlightthickness=0, bd=0)
        self.dots.pack(side="left")
        self.paso_txt = tk.Label(top, text="", font=F(9), fg=MUTED, bg=BG)
        self.paso_txt.pack(side="left", padx=8)
        NeonButton(top, "Saltar el asistente", lambda: self.cerrar(None), color=MUTED, padx=12, pady=4, font=F(9, True)).pack(side="right")
        self.titulo = tk.Label(box, text="", font=F(24, True), fg=FG, bg=BG, anchor="w")
        self.titulo.pack(fill="x", pady=(16, 2))
        self.sub = WrapLabel(box, text="", fg=MUTED, font=F(11))
        self.sub.pack(fill="x")
        self.body = tk.Frame(box, bg=BG)
        self.body.pack(fill="both", expand=True, pady=(12, 10))
        foot = tk.Frame(box, bg=BG)
        foot.pack(fill="x")
        self.b_back = NeonButton(foot, "←  Atrás", self.atras, color=MUTED, padx=18, pady=8, font=F(11, True))
        self.b_back.pack(side="left")
        self.msg = tk.Label(foot, text="", font=F(10), fg=MUTED, bg=BG)
        self.msg.pack(side="left", padx=14)
        self.b_next = NeonButton(foot, "Siguiente  →", self.siguiente, color=CYAN, filled=True, padx=26, pady=9, font=F(12, True))
        self.b_next.pack(side="right")
        self.mostrar()

    # ------------------------------------------------------------------
    def vivo(self):
        return not self.cerrado and self.winfo_exists()

    def _puntos(self):
        self.dots.delete("all")
        for k in range(len(PASOS)):
            x = 12 + k * 34
            if k < self.i:
                self.dots.create_oval(x - 6, 5, x + 6, 17, fill=CYAN, outline=CYAN)
            elif k == self.i:
                self.dots.create_oval(x - 8, 3, x + 8, 19, fill=BG, outline=CYAN, width=2)
                self.dots.create_oval(x - 3, 8, x + 3, 14, fill=CYAN, outline=CYAN)
            else:
                self.dots.create_oval(x - 6, 5, x + 6, 17, fill=BG, outline=mix(BG, MUTED, 0.5))
            if k < len(PASOS) - 1:
                self.dots.create_line(x + 10, 11, x + 24, 11, fill=CYAN if k < self.i else mix(BG, MUTED, 0.4))
        self.paso_txt.config(text=f"Paso {self.i + 1} de {len(PASOS)}  ·  {PASOS[self.i]}")

    def _limpiar(self):
        for w in self.body.winfo_children():
            w.destroy()
        self.msg.config(text="")

    def mostrar(self):
        self._puntos()
        self._limpiar()
        self.b_back.set_enabled(self.i > 0)
        ultimo = self.i == len(PASOS) - 1
        self.b_next.set_text("Empezar a usar HellOP" if ultimo else "Siguiente  →")
        [self._p1, self._p2, self._p3, self._p4, self._p5][self.i]()

    def siguiente(self):
        if self.i >= len(PASOS) - 1:
            self.cerrar(None)
            return
        self.i += 1
        self.mostrar()

    def atras(self):
        if self.i > 0:
            self.i -= 1
            self.mostrar()

    def cerrar(self, ir_a):
        if self.cerrado:
            return
        self.cerrado = True
        marcar_visto()
        self.destroy()
        self.on_close(ir_a)

    def _cabecera(self, titulo, sub):
        self.titulo.config(text=titulo)
        self.sub.config(text=sub)

    def _scroll(self):
        s = ScrollFrame(self.body)
        s.pack(fill="both", expand=True)
        return s.inner

    def _cargando(self, parent, texto):
        l = tk.Label(parent, text=texto, font=F(11), fg=CYAN, bg=BG)
        l.pack(anchor="w", pady=20)
        return l

    # ---- 1 · Bienvenida --------------------------------------------------
    def _p1(self):
        self._cabecera("Bienvenido a HellOP", "En 2 minutos miramos tu PC y dejamos lo más importante bien puesto. Tú decides cada cosa.")
        c = Card(self.body, accent=CYAN, title="Antes de empezar, las reglas")
        c.pack(fill="x")
        for t in ("No se aplica nada sin que lo marques tú. Si no estás seguro de algo, se queda como está.",
                  "Todo lo que se cambie queda guardado en el Historial y se puede deshacer con un clic.",
                  "Te cuento la verdad: no hay ajuste mágico que doble tus FPS. Lo que más pesa es el monitor, la RAM, "
                  "el calor y los gráficos del juego. HellOP te ayuda a encontrar lo que de verdad te cuesta.",
                  "Puedes saltar el asistente cuando quieras. Lo vuelves a abrir desde Inicio."):
            WrapLabel(c.body, text="•  " + t, font=F(10), fg=MUTED).pack(fill="x", pady=3)
        st = licencia.status()
        if self.pro:
            msg, col = "Tienes PRO: puedes usar todas las funciones.", GREEN
        else:
            msg, col = "Estás en la versión GRATIS (análisis, limpieza, monitor, historial). Con una clave PRO se desbloquea el resto.", YELLOW
        tk.Label(self.body, text=("✓  " if self.pro else "ⓘ  ") + msg, font=F(10, True), fg=col, bg=BG, anchor="w").pack(fill="x", pady=(14, 0))
        if st["level"] in ("expired", "invalid"):
            tk.Label(self.body, text=st["msg"], font=F(10), fg=RED, bg=BG, anchor="w").pack(fill="x", pady=(4, 0))

    # ---- 2 · Tu PC -------------------------------------------------------
    def _p2(self):
        self._cabecera("Tu PC", "Esto es lo que he encontrado en tu equipo.")
        host = self._scroll()
        if self.hw is not None:
            self._pintar_pc(host)
            return
        lab = self._cargando(host, "Leyendo procesador, RAM, gráfica y discos…")
        self.b_next.set_enabled(False)

        def listo(res):
            if not self.vivo() or self.i != 1:
                return
            self.hw = res
            self.b_next.set_enabled(True)
            lab.destroy()
            self._pintar_pc(host)

        def fallo(e):
            if not self.vivo():
                return
            self.b_next.set_enabled(True)
            lab.config(text=f"No pude leer tu equipo ({e}). Puedes seguir igualmente.", fg=YELLOW)
        self.app.bg(sysinfo.analyze, listo, fallo)

    def _pintar_pc(self, host):
        sec = self.hw["sections"]
        c = Card(host, accent=CYAN, title="Resumen")
        c.pack(fill="x", pady=(0, 10))
        for key in ("cpu", "gpu", "ram", "disks", "os"):
            if key not in sec:
                continue
            nombre, filas = sec[key]
            for k, v in filas[:2]:
                r = tk.Frame(c.body, bg=PANEL)
                r.pack(fill="x", pady=2)
                tk.Label(r, text=nombre if k == filas[0][0] else "", font=F(9, True), fg=CYAN, bg=PANEL, width=16, anchor="w").pack(side="left")
                tk.Label(r, text=k, font=F(10, True), fg=FG, bg=PANEL, anchor="w").pack(side="left", padx=(0, 8))
                WrapLabel(r, text=str(v), font=F(9), fg=MUTED).pack(side="left", fill="x", expand=True)
        recs = [r for r in self.hw.get("recs", []) if r[0] in ("warn", "bad")][:3]
        if recs:
            rc = Card(host, accent=YELLOW, title="Ojo con esto")
            rc.pack(fill="x")
            for _k, titulo, texto in recs:
                tk.Label(rc.body, text=titulo, font=F(10, True), fg=YELLOW, bg=PANEL, anchor="w").pack(fill="x", pady=(4, 0))
                WrapLabel(rc.body, text=texto, font=F(9), fg=MUTED).pack(fill="x")

    # ---- 3 · Lo más importante -----------------------------------------
    def _p3(self):
        self._cabecera("Lo que más te cuesta", "Lo que más rendimiento y fluidez te quita ahora mismo, de más a menos importante.")
        host = self._scroll()
        if self.hallazgos is not None:
            self._pintar_hallazgos(host)
            return
        lab = self._cargando(host, "Buscando lo que te cuesta rendimiento (unos segundos)…")
        self.b_next.set_enabled(False)

        def listo(res):
            if not self.vivo() or self.i != 2:
                return
            self.hallazgos = res
            self.b_next.set_enabled(True)
            lab.destroy()
            self._pintar_hallazgos(host)

        def fallo(e):
            if not self.vivo():
                return
            self.b_next.set_enabled(True)
            lab.config(text=f"No pude revisarlo ({e}). Puedes seguir igualmente.", fg=YELLOW)
        self.app.bg(lambda: hidden.scan(), listo, fallo)

    def _pintar_hallazgos(self, host):
        malos = [f for f in self.hallazgos if f["sev"] in ("bad", "warn", "info")]
        if not malos:
            Card(host, accent=GREEN, title="¡Todo en orden!").pack(fill="x")
            WrapLabel(host, text="No he encontrado nada importante: tu PC está bien configurado.", font=F(11), fg=GREEN).pack(fill="x", pady=8)
            return
        limite = len(malos) if self.pro else 2
        for f in malos[:limite]:
            col = SEV_COL[f["sev"]]
            c = Card(host, accent=col)
            c.pack(fill="x", pady=(0, 8))
            h = tk.Frame(c.body, bg=PANEL)
            h.pack(fill="x")
            tk.Label(h, text=SEV_TXT[f["sev"]], font=F(8, True), fg=col, bg=PANEL).pack(side="left")
            tk.Label(h, text="   " + f["title"], font=F(11, True), fg=FG, bg=PANEL, anchor="w").pack(side="left")
            if f.get("impact"):
                WrapLabel(c.body, text="Impacto: " + f["impact"], font=F(9, True), fg=col).pack(fill="x", pady=(4, 0))
            if f.get("detail"):
                WrapLabel(c.body, text=f["detail"], font=F(9), fg=MUTED).pack(fill="x", pady=(3, 0))
        if len(malos) > limite:
            tk.Label(host, text=f"+ {len(malos) - limite} cosa(s) más. Con una clave PRO las ves todas y las arreglas desde «Puntuación».",
                     font=F(10, True), fg=YELLOW, bg=BG, anchor="w").pack(fill="x", pady=(6, 0))
        elif self.pro:
            tk.Label(host, text="Para ver tu nota y arreglarlas una a una, abre «Puntuación» cuando termines.", font=F(10), fg=MUTED,
                     bg=BG, anchor="w").pack(fill="x", pady=(6, 0))

    # ---- 4 · Lo seguro ---------------------------------------------------
    def _p4(self):
        self._cabecera("Lo seguro", "Dos cosas sin riesgo que puedes hacer ya. No se marca nada que pueda dar problemas.")
        host = self._scroll()
        self.vars = {}
        # limpieza
        self.c_clean = Card(host, accent=CYAN, title="Limpieza rápida de archivos temporales")
        self.c_clean.pack(fill="x", pady=(0, 10))
        self.clean_box = tk.Frame(self.c_clean.body, bg=PANEL)
        self.clean_box.pack(fill="x")
        self._pintar_limpieza()
        # ajustes
        self.c_set = Card(host, accent=PINK, title="Ajustes sin riesgo" + ("" if self.pro else "  ·  PRO"))
        self.c_set.pack(fill="x")
        self.set_box = tk.Frame(self.c_set.body, bg=PANEL)
        self.set_box.pack(fill="x")
        if not self.pro:
            WrapLabel(self.set_box, text="Aquí se aplicarían los ajustes seguros de Tweaks (menos latencia, sin avisos que te sacan del juego…). "
                                         "Con una clave PRO se activan. Mientras tanto, la limpieza de arriba sí funciona.",
                      font=F(10), fg=MUTED).pack(fill="x")
        else:
            self._pintar_ajustes()

    def _pintar_limpieza(self):
        for w in self.clean_box.winfo_children():
            w.destroy()
        if self.limpieza is None:
            lab = self._cargando(self.clean_box, "Mirando cuánto se puede limpiar…")
            lab.config(bg=PANEL)

            def work():
                items = [i for i in cleanup.build_items() if i.default and i.available()]
                for i in items:
                    i.scan()
                return [i for i in items if i.size > 0]

            def listo(items):
                if not self.vivo():
                    return
                self.limpieza = items
                if self.i == 3:
                    self._pintar_limpieza()

            def fallo(_e):
                if not self.vivo():
                    return
                self.limpieza = []
                if self.i == 3:
                    self._pintar_limpieza()
            self.app.bg(work, listo, fallo)
            return
        total = sum(i.size for i in self.limpieza)
        if not self.limpieza or total < 1024 * 1024:
            tk.Label(self.clean_box, text="✓  No hay casi nada que limpiar.", font=F(10, True), fg=GREEN, bg=PANEL).pack(anchor="w")
            return
        tk.Label(self.clean_box, text=f"Se pueden liberar unos {fmt_bytes(total)}.", font=F(12, True), fg=FG, bg=PANEL).pack(anchor="w")
        WrapLabel(self.clean_box, text="Solo archivos temporales y restos que se vuelven a crear solos. No toca tus documentos, "
                                       "contraseñas ni historial.", font=F(9), fg=MUTED).pack(fill="x", pady=(2, 8))
        self.b_clean = NeonButton(self.clean_box, "✦  Limpiar ahora", self._limpiar_ahora, color=CYAN, filled=True, padx=18, pady=7,
                                  font=F(10, True))
        self.b_clean.pack(anchor="w")

    def _limpiar_ahora(self):
        self.b_clean.set_enabled(False)
        self.msg.config(text="Limpiando…", fg=CYAN)

        def work():
            freed = 0
            for i in self.limpieza:
                f, _fail = i.clean()
                freed += f
            return freed

        def listo(freed):
            if not self.vivo():
                return
            self.hecho["liberado"] += freed
            self.limpieza = []
            self.msg.config(text=f"✓ Liberé {fmt_bytes(freed)}", fg=GREEN)
            if self.i == 3:
                self._pintar_limpieza()
        self.app.bg(work, listo, lambda e: self.msg.config(text=f"✗ {e}", fg=RED) if self.vivo() else None)

    def _pintar_ajustes(self):
        for w in self.set_box.winfo_children():
            w.destroy()
        if self.ajustes is None:
            lab = self._cargando(self.set_box, "Buscando ajustes seguros para tu PC (unos segundos)…")
            lab.config(bg=PANEL)

            def work():
                admin = is_admin() or DEMO
                # solo ajustes de registro de riesgo bajo y sin avisos: nada de energía, gráfica ni arranque
                return [a for a in tweaks.collect() if (type(a).__name__ == "RegTweak" or DEMO) and a.risk == "bajo"
                        and not getattr(a, "warning", "") and (admin or not a.needs_admin)
                        and getattr(a, "effect", "") in ("real", "pequeño")][:10]

            def listo(acts):
                if not self.vivo():
                    return
                self.ajustes = acts
                if self.i == 3:
                    self._pintar_ajustes()

            def fallo(_e):
                if not self.vivo():
                    return
                self.ajustes = []
                if self.i == 3:
                    self._pintar_ajustes()
            self.app.bg(work, listo, fallo)
            return
        if not self.ajustes:
            tk.Label(self.set_box, text="✓  No queda ningún ajuste seguro por aplicar.", font=F(10, True), fg=GREEN, bg=PANEL).pack(anchor="w")
            return
        WrapLabel(self.set_box, text="Marcados los de riesgo bajo. Desmarca el que no quieras. Se crea un punto de restauración antes.",
                  font=F(9), fg=MUTED).pack(fill="x", pady=(0, 6))
        for a in self.ajustes:
            v = tk.BooleanVar(value=True)
            self.vars[a.id] = v
            box = tk.Frame(self.set_box, bg=PANEL)
            box.pack(fill="x", pady=3)
            checkbox(box, a.title, v, bg=PANEL, font=F(10, True)).pack(anchor="w")
            WrapLabel(box, text=a.desc, font=F(9), fg=MUTED).pack(fill="x", padx=(28, 0))
        self.b_set = NeonButton(self.set_box, "⚡  Aplicar los marcados", self._aplicar, color=PINK, filled=True, padx=18, pady=7,
                                font=F(10, True))
        self.b_set.pack(anchor="w", pady=(10, 0))

    def _aplicar(self):
        elegidos = [a for a in self.ajustes if self.vars.get(a.id) and self.vars[a.id].get()]
        if not elegidos:
            self.msg.config(text="Marca primero algún ajuste.", fg=YELLOW)
            return
        self.b_set.set_enabled(False)
        self.msg.config(text="Creando punto de restauración…", fg=CYAN)

        def work():
            try:
                actions.create_restore_point()
            except Exception:  # noqa: BLE001
                pass
            ok = 0
            for a in elegidos:
                ok += bool(actions.execute(a).ok)
            return ok, any(a.reboot for a in elegidos)

        def listo(res):
            if not self.vivo():
                return
            ok, reinicio = res
            self.hecho["ajustes"] += ok
            self.ajustes = []
            self.msg.config(text=f"✓ {ok} ajuste(s) aplicados" + ("  ·  reinicia el PC para completarlos" if reinicio else ""), fg=GREEN)
            if self.i == 3:
                self._pintar_ajustes()
        self.app.bg(work, listo, lambda e: self.msg.config(text=f"✗ {e}", fg=RED) if self.vivo() else None)

    # ---- 5 · Listo -------------------------------------------------------
    def _p5(self):
        self._cabecera("¡Listo!", "Esto es lo que hemos hecho y por dónde seguir.")
        c = Card(self.body, accent=GREEN, title="Resumen")
        c.pack(fill="x", pady=(0, 10))
        lib, aj = self.hecho["liberado"], self.hecho["ajustes"]
        lineas = [f"Limpieza: liberé {fmt_bytes(lib)}." if lib else "Limpieza: no hizo falta o la dejaste para luego.",
                  f"Ajustes: {aj} aplicado(s) (puedes deshacerlos desde el Historial)." if aj else
                  ("Ajustes: no apliqué ninguno." if self.pro else "Ajustes: se activan con una clave PRO.")]
        for t in lineas:
            tk.Label(c.body, text="•  " + t, font=F(10), fg=FG, bg=PANEL, anchor="w").pack(fill="x", pady=2)
        tk.Label(self.body, text="¿Por dónde sigues?", font=F(12, True), fg=FG, bg=BG, anchor="w").pack(fill="x", pady=(8, 6))
        row = tk.Frame(self.body, bg=BG)
        row.pack(fill="x")
        destinos = [("◎  Analizar mi PC a fondo", "analysis", CYAN)]
        destinos += [("★  Ver mi puntuación", "score", PINK), ("▣  Añadir mis juegos", "games", GREEN)] if self.pro else \
                    [("★  Activar una clave PRO", "license", PINK)]
        for texto, pagina, col in destinos:
            NeonButton(row, texto, lambda p=pagina: self.cerrar(p), color=col, padx=16, pady=8, font=F(10, True)).pack(side="left", padx=(0, 10))
        WrapLabel(self.body, text="Lo que necesites cambiar después, está en el menú de la izquierda. Si algo no te cuadra, "
                                  "el Historial lo deshace.", font=F(10), fg=MUTED).pack(fill="x", pady=(14, 0))
