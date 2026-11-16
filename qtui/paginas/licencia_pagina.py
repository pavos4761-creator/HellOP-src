"""Pantalla «Licencia»: activar tu clave y, si eres el creador, generar claves para otras personas."""
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import QFileDialog, QLineEdit, QVBoxLayout, QWidget

import actions
import claves
import config_io
import licencia as lic
from util import DEMO

from .. import theme
from ..widgets import Boton, Casilla, Etiqueta, Insignia, Pagina, Tarjeta, columna, fila, vacia

LEVEL_TONE = {"owner": "teal", "pro": "accent", "free": "muted", "expired": "yellow", "invalid": "red"}
LEVEL_TXT = {"owner": "CREADOR", "pro": "PRO", "free": "GRATIS", "expired": "CADUCADA", "invalid": "NO VÁLIDA"}


def date_es(iso):
    y, m, d = iso.split("-")
    return f"{d}/{m}/{y}"


def _campo(texto="", ancho=None, solo_lectura=False):
    e = QLineEdit(texto)
    e.setFont(theme.fuente(13, mono=True))
    e.setReadOnly(solo_lectura)
    if ancho:
        e.setMinimumWidth(ancho)
    return e


def _pon(lbl, texto, tone):
    """Pone texto y tono en una etiqueta que puede haber sido destruida por una reconstrucción."""
    try:
        lbl.setText(texto)
        lbl.tono(tone)
    except RuntimeError:
        pass


class Licencia(Pagina):
    titulo_texto = "Licencia"
    sub_texto = "Activa tu clave para desbloquear las funciones PRO."

    def __init__(self, app):
        super().__init__(app)
        self.cont = QWidget()
        self.cont.setObjectName("pagina")
        self.lay = QVBoxLayout(self.cont)
        self.lay.setContentsMargins(0, 0, 0, 0)
        self.lay.setSpacing(12)
        self.add(self.cont)
        self.days = 30
        self.dbtn = {}
        self.k_t = []
        self.k_g = None
        self.k_c = None
        self.reg_lay = None
        self.construye()

    def al_mostrar(self):
        self.construye()

    def reconstruye(self):
        self.construye()

    def construye(self):
        vacia(self.lay)
        self.dbtn = {}
        self.reg_lay = None
        st = lic.status()
        tone = LEVEL_TONE[st["level"]]

        # ---- tu licencia
        c = Tarjeta(tone=tone, titulo="Tu licencia")
        self.lay.addWidget(c)
        c.add(fila(Insignia(LEVEL_TXT[st["level"]], tone), Etiqueta(st["msg"], "h3"), None, espacio=12))
        self.v_pc = _campo(lic.pc_id(), 240, solo_lectura=True)
        c.add(fila(Etiqueta("ID de este PC:", "muted", wrap=False), self.v_pc,
                   Boton("Copiar", lambda: self.copia(self.v_pc.text(), "ID copiado"), kind="soft"), None))
        c.add(Etiqueta("Si quien te dio la clave la quiere atada a tu PC, mándale este ID.", "small", "muted"))

        # ---- activar
        a = Tarjeta(tone="accent", titulo="Activar una clave")
        self.lay.addWidget(a)
        self.v_key = _campo()
        a.add(self.v_key)
        a.add(fila(Boton("Pegar", self.pega, kind="soft"), Boton("ACTIVAR", self.activa, kind="primary", tone="green"), None))
        self.msg = Etiqueta("", "h3", "muted")
        a.add(self.msg)

        # ---- qué incluye
        inc = Tarjeta(tone="teal", titulo="Qué incluye PRO")
        self.lay.addWidget(inc)
        try:
            from ..shell import NOMBRES
        except Exception:  # noqa: BLE001
            NOMBRES = {}
        nombres = [NOMBRES.get(k, k) for k in NOMBRES if k in lic.PRO_PAGES] or sorted(lic.PRO_PAGES)
        inc.add(Etiqueta(", ".join(nombres) + "."))
        inc.add(Etiqueta("GRATIS incluye solo: análisis de tu PC, limpieza, monitor, historial y actualizaciones.", "small", "muted"))

        if lic.is_pro():
            self.construye_config()
        if lic.owner_secret() or DEMO:
            self.construye_generador()
            self.construye_registro()

    # ------------------------------------------------------------------
    # Mi configuración
    # ------------------------------------------------------------------
    def construye_config(self):
        c = Tarjeta(tone="teal", titulo="Mi configuración (exportar / importar)")
        self.lay.addWidget(c)
        c.add(Etiqueta("Guarda tus ajustes en un archivo para llevarlos a otro PC o pasárselos a un amigo. No incluye tu clave, "
                       "tu ID de PC ni rutas de tu equipo. Al importar no se aplica nada solo: tú marcas qué quieres.", "muted"))
        c.add(fila(Boton("⇪  Exportar a archivo…", self.exporta_cfg, kind="primary"),
                   Boton("⇩  Importar archivo…", self.importa_cfg, kind="soft"), None))
        self.kmsg = Etiqueta("", "h3", "muted")
        c.add(self.kmsg)
        self.kbox_w = QWidget()
        self.kbox = QVBoxLayout(self.kbox_w)
        self.kbox.setContentsMargins(0, 0, 0, 0)
        self.kbox.setSpacing(6)
        c.add(self.kbox_w)

    def exporta_cfg(self):
        path, _f = QFileDialog.getSaveFileName(self, "Guardar mi configuración", "mi-configuracion-hellop.json",
                                               "Configuración de HellOP (*.json)")
        if not path:
            return
        if not path.lower().endswith(".json"):
            path += ".json"
        try:
            nt, ng = config_io.export(path)
        except OSError as e:
            _pon(self.kmsg, f"✗ No pude guardar: {e}", "red")
            return
        _pon(self.kmsg, f"✓ Guardado: {nt} tweaks y {ng} juegos.", "green")

    def importa_cfg(self):
        path, _f = QFileDialog.getOpenFileName(self, "Abrir una configuración de HellOP", "", "Configuración de HellOP (*.json)")
        if not path:
            return
        try:
            cfg = config_io.read(path)
        except (ValueError, OSError) as e:
            _pon(self.kmsg, f"✗ {e}", "red")
            return
        _pon(self.kmsg, "Mirando qué se puede aplicar en este PC…", "accent")
        self.app.bg(lambda: config_io.applicable_tweaks(cfg), lambda acts: self._muestra_import(cfg, acts),
                    lambda e: _pon(self.kmsg, f"✗ {e}", "red"))

    def _muestra_import(self, cfg, acts):
        try:
            vacia(self.kbox)
        except RuntimeError:
            return
        _pon(self.kmsg, f"Configuración de HellOP v{cfg['version']} ({cfg['created'] or 'sin fecha'}). Marca lo que quieras aplicar:", "muted")
        self.k_t = []
        for a in acts:
            cb = Casilla(f"{a.title}   [riesgo {a.risk}]")
            self.k_t.append((a, cb))
            self.kbox.addWidget(cb)
        saltados = len(cfg["tweaks"]) - len(acts)
        if saltados > 0:
            self.kbox.addWidget(Etiqueta(f"{saltados} tweak(s) no se ofrecen: ya están aplicados o no corresponden a este equipo.", "small", "muted"))
        self.k_g = None
        self.k_c = None
        if cfg["games"]:
            self.k_g = Casilla(f"Usar sus perfiles de juego ({len(cfg['games'])}; solo en los juegos que tú también tengas)")
            self.kbox.addWidget(self.k_g)
        if cfg["acento"]:
            self.k_c = Casilla(f"Usar su color ({cfg['acento']})")
            self.kbox.addWidget(self.k_c)
        self.kbox.addWidget(fila(Boton("APLICAR LO MARCADO", lambda: self.aplica_import(cfg), kind="primary", tone="green"), None))

    def aplica_import(self, cfg):
        elegidos = [a for a, cb in self.k_t if cb.isChecked()]
        quiere_g = bool(self.k_g is not None and self.k_g.isChecked())
        quiere_c = bool(self.k_c is not None and self.k_c.isChecked())

        def trabajo():
            ok = fallos = 0
            for a in elegidos:
                r = actions.execute(a)
                ok += r.ok
                fallos += (not r.ok)
            g = config_io.apply_games(cfg) if quiere_g else (0, [])
            if quiere_c and cfg["acento"]:
                import widgets
                widgets.guardar_acento(cfg["acento"])
            return ok, fallos, g

        def hecho(res):
            ok, fallos, (gn, _faltan) = res
            partes = [f"{ok} tweaks aplicados"] + ([f"{fallos} fallaron"] if fallos else []) + ([f"perfiles en {gn} juegos"] if quiere_g else []) \
                + (["color guardado: reinicia para verlo"] if quiere_c and cfg["acento"] else [])
            _pon(self.kmsg, "✓ " + " · ".join(partes), "green" if not fallos else "yellow")
        self.app.bg(trabajo, hecho, lambda e: _pon(self.kmsg, f"✗ {e}", "red"))

    # ------------------------------------------------------------------
    # Generador de claves
    # ------------------------------------------------------------------
    def construye_generador(self):
        g = Tarjeta(tone="teal", titulo="Generador de claves (solo tú lo ves)")
        self.lay.addWidget(g)
        g.add(Etiqueta("Crea una clave con caducidad. Si pegas el ID del PC de la otra persona, la clave solo funcionará en su PC; "
                       "si lo dejas vacío, valdrá en cualquier PC.", "muted"))
        self.v_gname = _campo(ancho=260)
        g.add(fila(Etiqueta("¿Para quién es?", "muted", wrap=False), self.v_gname,
                   Etiqueta("(un nombre o nota, para tu lista)", "small", "muted", wrap=False), None))
        self.v_gpc = _campo(ancho=260)
        g.add(fila(Etiqueta("ID del PC:", "muted", wrap=False), self.v_gpc, None))
        botones = [Etiqueta("Caduca en:", "muted", wrap=False)]
        for n, texto in ((7, "7 días"), (30, "30 días"), (90, "90 días"), (180, "6 meses"), (365, "1 año")):
            b = Boton(texto, lambda n_=n: self.pon_dias(n_), kind="soft")
            self.dbtn[n] = b
            botones.append(b)
        botones.append(None)
        g.add(fila(*botones, espacio=6))
        self.pon_dias(self.days)
        botones2 = [Boton("✦  GENERAR CLAVE", self.genera, kind="primary")]
        if hasattr(self.app, "pro_welcome"):
            botones2.append(Boton("▶  Ver animación «Bienvenido a Pro»", lambda: self.app.pro_welcome(), kind="soft"))
        botones2.append(None)
        g.add(fila(*botones2))
        self.v_out = _campo(solo_lectura=True)
        g.add(self.v_out)
        self.gmsg = Etiqueta("", "h3", "muted")
        g.add(fila(Boton("Copiar clave", lambda: self.copia(self.v_out.text(), "Clave copiada"), kind="soft"), self.gmsg, None, espacio=12))

    def pon_dias(self, n):
        self.days = n
        for k, b in self.dbtn.items():
            b.estilo(kind="primary" if k == n else "soft")

    def genera(self):
        sec = lic.owner_secret()
        if not sec:
            _pon(self.gmsg, "(Demo) aquí saldría la clave: falta tu llave privada." if DEMO else "Falta tu llave privada.", "yellow")
            return
        try:
            key, exp = lic.make_key(sec, self.v_gpc.text(), self.days)
        except ValueError as e:
            _pon(self.gmsg, str(e), "red")
            return
        self.v_out.setText(key)
        try:
            claves.add(self.v_gname.text(), key, exp, self.v_gpc.text())
            _pon(self.gmsg, f"Lista y apuntada en tu lista · caduca el {exp.strftime('%d/%m/%Y')}", "green")
            self.v_gname.setText("")
            self.pinta_registro()
        except (OSError, claves.ClavesError) as e:
            _pon(self.gmsg, f"Lista (pero no pude apuntarla: {e})", "yellow")

    # ------------------------------------------------------------------
    # Registro de claves dadas
    # ------------------------------------------------------------------
    def construye_registro(self):
        self.reg_card = Tarjeta(tone="yellow", titulo="Claves que has dado (puedes anularlas aquí)")
        self.lay.addWidget(self.reg_card)
        self.reg_w = QWidget()
        self.reg_lay = QVBoxLayout(self.reg_w)
        self.reg_lay.setContentsMargins(0, 0, 0, 0)
        self.reg_lay.setSpacing(8)
        self.reg_card.add(self.reg_w)
        self.pinta_registro()

    def pinta_registro(self):
        if self.reg_lay is None:
            return
        vacia(self.reg_lay)
        b = self.reg_lay
        items = sorted(claves.load(), key=lambda e: e["caduca"])
        if not claves.token():
            b.addWidget(Etiqueta("Para poder ANULAR claves necesito un token de GitHub (solo la primera vez). Créalo en GitHub: tu foto → Settings → "
                                 "Developer settings → Personal access tokens → Fine-grained tokens → Generate new token. Elige solo el repositorio "
                                 "PCOptimizer (el público) y en Permissions → Contents: Read and write. Se guarda solo en tu PC.", "muted"))
            self.v_tok = _campo(ancho=340)
            b.addWidget(fila(self.v_tok, Boton("Guardar token", self.guarda_token, kind="primary", tone="yellow"), None))
        else:
            fila_tok = [Etiqueta("✓ Token guardado: puedes anular claves.", "small", "green", wrap=False)]
            pend = [e for e in items if e.get("anulada") and not e.get("publicada")]
            if pend:
                fila_tok.append(Boton(f"Publicar {len(pend)} anulación(es) pendiente(s)", self.publica_pendientes, kind="primary", tone="yellow"))
            fila_tok.append(None)
            b.addWidget(fila(*fila_tok))
        pronto = claves.por_vencer()
        if pronto:
            b.addWidget(Etiqueta("⚠ Vencen pronto: " + ", ".join(f"{e['nombre']} ({claves.estado(e)[1]} d)" for e in pronto) + ".", "h3", "yellow"))
        self.rmsg = Etiqueta("", "h3", "muted")
        b.addWidget(self.rmsg)
        if not items:
            b.addWidget(Etiqueta("Aún no has generado ninguna clave desde esta versión. Cada clave nueva aparecerá aquí.", "small", "muted"))
            return
        tono = {"activa": "green", "pronto": "yellow", "caducada": "muted", "anulada": "red", "pendiente": "yellow"}
        txt = {"activa": "ACTIVA", "pronto": "VENCE PRONTO", "caducada": "CADUCADA", "anulada": "ANULADA", "pendiente": "ANULACIÓN PENDIENTE"}
        for e in items:
            est, dias = claves.estado(e)
            cad = date_es(e["caduca"])
            detalle = (f"Caduca el {cad}" + (f" · quedan {dias} días" if dias >= 0 else " · ya caducó")
                       + (" · atada a un PC" if e.get("pc") else " · vale en cualquier PC"))
            cabeza = fila(Etiqueta(e["nombre"], "h3", wrap=False), Insignia(txt[est], tono[est]), None, espacio=8)
            izq = columna(cabeza, Etiqueta(detalle, "small", "muted"), espacio=2)
            bts = [Boton("Copiar", lambda _=False, k=e["key"]: self.copia(k, "Clave copiada"), kind="soft")]
            if e.get("anulada"):
                bts.append(Boton("Reactivar", lambda _=False, i=e["id"]: self.reactiva(i), kind="soft", tone="green"))
            elif est != "caducada":
                bts.append(Boton("Anular", lambda _=False, i=e["id"], n=e["nombre"]: self.anula(i, n), kind="primary", tone="red"))
            if est in ("caducada", "anulada"):
                bts.append(Boton("Quitar", lambda _=False, i=e["id"]: self.quita(i), kind="ghost"))
            tarj = Tarjeta(soft=True, margen=10)
            tarj.add(fila(izq, None, *bts, espacio=6))
            b.addWidget(tarj)

    def guarda_token(self):
        try:
            claves.guardar_token(self.v_tok.text())
        except (OSError, claves.ClavesError) as e:
            _pon(self.rmsg, f"✗ {e}", "red")
            return
        self.pinta_registro()
        _pon(self.rmsg, "✓ Token guardado.", "green")
        if any(e.get("anulada") and not e.get("publicada") for e in claves.load()):
            self.publica_pendientes()

    def _ejecuta_reg(self, trabajo):
        """Ejecuta una operación de red del registro en segundo plano y vuelve a pintar la lista."""
        _pon(self.rmsg, "Un momento…", "accent")

        def hecho(res):
            self.pinta_registro()
            okf, m = res if isinstance(res, tuple) else (True, res)
            _pon(self.rmsg, ("✓ " if okf else "⚠ ") + str(m), "green" if okf else "yellow")
        self.app.bg(trabajo, hecho, lambda e: _pon(self.rmsg, f"✗ {e}", "red"))

    def anula(self, kid, nombre):
        if not DEMO and not self.app.pregunta("Anular clave", f"Vas a anular la clave de «{nombre}».\n\nSe quedará sin PRO en cuanto su "
                                              "HellOP se conecte a internet. ¿Seguro?"):
            return
        if DEMO:
            _pon(self.rmsg, "(Demo) aquí se anularía la clave.", "yellow")
            return
        self._ejecuta_reg(lambda: claves.anular(kid))

    def publica_pendientes(self):
        self._ejecuta_reg(claves.publicar_pendientes)

    def reactiva(self, kid):
        if DEMO:
            return
        self._ejecuta_reg(lambda: claves.reactivar(kid))

    def quita(self, kid):
        claves.borrar(kid)
        self.pinta_registro()

    # ------------------------------------------------------------------
    def copia(self, texto, ok):
        try:
            QGuiApplication.clipboard().setText(texto)
            self.app.status(ok)
        except Exception:  # noqa: BLE001
            pass

    def pega(self):
        try:
            self.v_key.setText(QGuiApplication.clipboard().text().strip())
        except Exception:  # noqa: BLE001
            pass

    def activa(self):
        key = self.v_key.text()
        _pon(self.msg, "Comprobando la clave…", "accent")

        def trabajo():
            if not DEMO:
                lic.refresh_revoked(timeout=5)          # por si esa clave ya la anularon
            return lic.activate(key)

        def hecho(res):
            ok, m = res
            _pon(self.msg, ("✓ " if ok else "✗ ") + m, "green" if ok else "red")
            if ok:
                self.app.refresh_license()
                self.app.after(900, self.reconstruye)
                if hasattr(self.app, "pro_welcome"):
                    self.app.pro_welcome()
        self.app.bg(trabajo, hecho, lambda e: _pon(self.msg, f"✗ {e}", "red"))
