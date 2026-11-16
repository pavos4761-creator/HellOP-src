"""Pantalla «Ajustes de juego»: perfiles de gráficos para tus juegos, con copia y deshacer (versión Qt)."""
from PySide6.QtWidgets import QVBoxLayout

import actions
import gameprofiles as gp
from util import DEMO

from ..widgets import Boton, Etiqueta, Pagina, Tarjeta, fila, vacia


class AjustesJuego(Pagina):
    titulo_texto = "Ajustes de juego"
    sub_texto = "Baja lo que más cuesta FPS dentro del propio juego (sombras, efectos, límite de FPS) con un clic."

    def __init__(self, app):
        super().__init__(app)
        self.busy = False
        self._loaded = False
        c = Tarjeta(tone="yellow", titulo="Qué hace y qué no")
        for t in ("Cambia el archivo de configuración del juego. Solo toca valores que ya existen y antes guarda una copia.",
                  "Es lo que más FPS da si tu gráfica va al 100 %: los ajustes de Windows no pueden darle más potencia, "
                  "pero bajar sombras y efectos sí.",
                  "Cierra el juego antes de aplicar. Si está abierto, lo reescribe al salir y se pierde el cambio.",
                  "«Restaurar» devuelve el archivo tal como estaba. También aparece en Historial."):
            c.add(Etiqueta("•  " + t, "muted"))
        self.add(c)

        self.msg = Etiqueta("", "muted")
        self.add(fila(Boton("↻  BUSCAR MIS JUEGOS", self.refresh, kind="primary"), self.msg, None, espacio=14))
        self.list = QVBoxLayout()
        self.list.setContentsMargins(0, 0, 0, 0)
        self.list.setSpacing(12)
        self.col.addLayout(self.list)
        self.miss = Etiqueta("", "small", "muted")
        self.add(self.miss)

    def al_mostrar(self):
        if not self._loaded:
            self.refresh()

    def _msg(self, texto, tone="muted"):
        self.msg.setText(texto)
        self.msg.tono(tone)

    def refresh(self):
        self._loaded = True
        self._msg("Buscando…", "teal")
        self.app.bg(self._collect, self._render, lambda e: self._msg(f"Error: {e}", "red"))

    def _collect(self):
        found = gp.find_files()
        out = []
        for gid in gp.GAMES:
            if gid in found:
                out.append((gid, str(found[gid]), {p: gp.plan(gid, p) for p in gp.PRESETS}))
        return out, [g for g in gp.find_guides() if g in gp.GUIDES]

    def _last_entry(self, gid):
        for e in reversed(actions.load_log()):
            if e.get("cls") == "GameConfigAction" and not e.get("undone") and e.get("data", {}).get("gid") == gid:
                return e
        return None

    def _render(self, res):
        data, guides = res
        names = [gp.GAMES[g]["name"] for g in gp.GAMES if g not in {d[0] for d in data}]
        self.miss.setText(("No encontrados en este PC: " + ", ".join(names) + ". Si lo tienes instalado, ábrelo una vez, entra en "
                           "Ajustes → Vídeo, cámbialo algo y ciérralo para que cree su archivo; luego pulsa «Buscar mis juegos».")
                          if names else "")
        vacia(self.list)
        for gid in guides:
            g = gp.GUIDES[gid]
            c = Tarjeta(tone="teal", titulo=f"{g['name']}  ·  guía de ajustes")
            c.add(Etiqueta(g["note"], "muted"))
            for i, t in enumerate(g["steps"], 1):
                c.add(Etiqueta(f"{i}.  {t}"))
            self.list.addWidget(c)
        if not data and not guides:
            self._msg("No he encontrado ninguno de los juegos compatibles (Fortnite, VALORANT, Minecraft Java, League of Legends, CS2, eFootball).", "yellow")
            return
        self._msg(f"{len(data) + len(guides)} juego(s) encontrado(s)", "green")
        for gid, path, plans in data:
            g = gp.GAMES[gid]
            c = Tarjeta(tone="red", titulo=g["name"])
            c.add(Etiqueta(path, "mono"))
            c.add(Etiqueta(g["note"], "muted"))
            botones = []
            for key, (label, _d) in gp.PRESETS.items():
                n = len(plans[key])
                b = Boton(f"{label}  ({n} cambios)" if n else f"{label}  (ya está así)",
                          lambda g_=gid, k=key: self.apply(g_, k), kind="primary" if key == "max" else "soft")
                if not n:
                    b.set_enabled(False)
                botones.append(b)
            rb = Boton("↺  Restaurar", lambda g_=gid: self.restore(g_), kind="soft", tone="yellow")
            if not self._last_entry(gid):
                rb.set_enabled(False)
            botones.append(rb)
            botones.append(None)
            c.add(fila(*botones, espacio=10))
            best = plans["max"] or plans["balanced"]
            if best:
                c.add(Etiqueta("Cambios de «Máximo FPS»:" if plans["max"] else "Cambios:", "h3"))
                for k, old, new in best[:10]:
                    c.add(Etiqueta(f"{k}:   {old}  →  {new}", "mono"))
            self.list.addWidget(c)

    def apply(self, gid, preset):
        if self.busy:
            return
        name = gp.GAMES[gid]["name"]
        if not DEMO and not self.app.pregunta("Aplicar perfil", f"Se cambiará la configuración de {name} (se guarda una copia).\n\n"
                                                                 "¿Has cerrado el juego?"):
            return
        self.busy = True
        self._msg("Aplicando…", "teal")
        self.app.bg(lambda: actions.execute(gp.GameConfigAction(gid, preset)), self._done, lambda e: self._done(None, str(e)))

    def _done(self, res, err=None):
        self.busy = False
        if res is None or not res.ok:
            self._msg("✗ " + (err or res.msg), "red")
        else:
            self._msg("✓ " + res.msg, "green")
        self.refresh_keep()

    def refresh_keep(self):
        self.app.bg(self._collect, self._render_keep, lambda e: None)

    def _render_keep(self, data):
        txt, tone = self.msg.text(), self.msg.property("tone")
        self._render(data)
        if txt:
            self._msg(txt, tone or "muted")

    def restore(self, gid):
        e = self._last_entry(gid)
        if not e:
            return
        r = actions.undo_entry(e["id"])
        self._msg("✓ Restaurado como estaba." if r.ok else "✗ " + r.msg, "green" if r.ok else "red")
        self.refresh_keep()
