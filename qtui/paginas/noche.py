"""Pantalla «Modo noche» (versión Qt)."""
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLineEdit

import noche

from ..widgets import Boton, Casilla, Etiqueta, Pagina, Tarjeta, fila

NIVELES = (("suave", "Suave · 90 %"), ("medio", "Media · 80 %"), ("fuerte", "Fuerte · 70 %"))


class Noche(Pagina):
    titulo_texto = "Modo noche"
    sub_texto = "Menos ruido y menos calor de madrugada. Al acabar el horario, todo vuelve a como estaba."

    def __init__(self, app):
        super().__init__(app)
        c = Tarjeta(tone="accent", titulo="Qué hace (y qué no)")
        for t in ("Limita el máximo del procesador en tu plan de energía: menos calor, ventiladores más lentos. Es lo que más se nota.",
                  "En gráficas NVIDIA baja también el límite de potencia (necesita ejecutar HellOP como administrador).",
                  "No cambia tus ajustes de juego ni tu plan: guarda los valores de antes y los devuelve solos.",
                  "Solo funciona mientras HellOP está abierto (puede estar minimizado). Al cerrar HellOP se restaura todo.",
                  "Honesto: a menos potencia, menos FPS. Está pensado para jugar tranquilo o dejar el PC descargando de noche."):
            c.add(Etiqueta("•  " + t))
        self.add(c)

        self.cfg = noche.cargar()
        h = Tarjeta(tone="teal", titulo="Horario")
        self.v_on = Casilla("Activar automáticamente en este horario", bool(self.cfg["activo_horario"]))
        h.add(self.v_on)
        self.e_ini = self._hora(self.cfg["ini"])
        self.e_fin = self._hora(self.cfg["fin"])
        h.add(fila(Etiqueta("Desde", "h3", wrap=False), self.e_ini, Etiqueta("Hasta", "h3", wrap=False), self.e_fin, None, espacio=10))

        self.nivel = self.cfg["nivel"]
        self.btns = {}
        cont = [Etiqueta("Intensidad", "h3", wrap=False)]
        for k, txt in NIVELES:
            b = Boton(txt, lambda k=k: self._nivel(k), kind="primary" if k == self.nivel else "soft")
            self.btns[k] = b
            cont.append(b)
        cont.append(None)
        h.add(fila(*cont, espacio=8))
        self.add(h)

        self.msg = Etiqueta("", "muted")
        self.add(self.msg)
        self.add(fila(Boton("Guardar horario", self.guarda, kind="primary"),
                      Boton("Probar ahora", self.probar, kind="soft", tone="yellow"),
                      Boton("Restaurar ya", self.restaura, kind="soft", tone="green"), None, espacio=10))

    def _hora(self, valor):
        e = QLineEdit(str(valor))
        e.setMaxLength(5)
        e.setFixedWidth(84)
        e.setAlignment(Qt.AlignmentFlag.AlignCenter)
        return e

    def _nivel(self, k):
        self.nivel = k
        for kk, b in self.btns.items():
            b.estilo(kind="primary" if kk == k else "soft")

    def _msg(self, texto, tone):
        self.msg.setText(texto)
        self.msg.tono(tone)

    def al_mostrar(self):
        self.estado()

    def estado(self):
        d = noche.cargar()
        if d["aplicado"]:
            self._msg("● Modo noche ACTIVO ahora mismo.", "green")
        elif d["activo_horario"]:
            self._msg(f"Programado de {d['ini']} a {d['fin']}. Ahora está apagado.", "muted")
        else:
            self._msg("Apagado.", "muted")

    def guarda(self):
        ini, fin = self.e_ini.text().strip(), self.e_fin.text().strip()
        if not (noche.hora_valida(ini) and noche.hora_valida(fin)):
            self._msg("Escribe las horas como 23:00 y 08:00.", "yellow")
            return
        d = noche.cargar()
        d.update({"activo_horario": bool(self.v_on.isChecked()), "ini": ini, "fin": fin, "nivel": self.nivel})
        noche.guardar(d)
        self.app.toast("Horario guardado", "green")
        r = noche.revisa()
        if r:
            self.app.toast(r, "teal")
        self.estado()

    def probar(self):
        txt, avisos = noche.aplicar(self.nivel)
        self._msg("Probando: " + txt + ("  ·  " + avisos[0] if avisos else ""), "yellow" if avisos else "green")

    def restaura(self):
        ok = noche.restaurar()
        self._msg("Todo vuelve a como estaba." if ok else "No había nada que restaurar.", "green")
