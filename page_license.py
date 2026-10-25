"""Página «Licencia»: activar tu clave y, si eres el creador, generar claves para otras personas."""
import sys
import tkinter as tk
from tkinter import filedialog, messagebox

import actions
import claves
import config_io
import licencia as lic
import widgets
from util import DEMO
from widgets import BORDER
from widgets import (BG, CYAN, F, FG, GREEN, MUTED, PANEL, PANEL2, PINK, RED, YELLOW, Card, NeonButton, ScrollFrame, WrapLabel,
                     badge, page_title)

LEVEL_COL = {"owner": PINK, "pro": CYAN, "free": MUTED, "expired": YELLOW, "invalid": RED}
LEVEL_TXT = {"owner": "CREADOR", "pro": "PRO", "free": "GRATIS", "expired": "CADUCADA", "invalid": "NO VÁLIDA"}


def date_es(iso):
    y, m, d = iso.split("-")
    return f"{d}/{m}/{y}"


def _entry(parent, var, width=60, readonly=False):
    return tk.Entry(parent, textvariable=var, font=("Consolas", 10), bg=PANEL2, fg=FG, insertbackground=FG, relief="flat",
                    highlightthickness=1, highlightbackground=BORDER, highlightcolor=CYAN, width=width,
                    readonlybackground=PANEL2, state="readonly" if readonly else "normal")


class LicensePage(tk.Frame):
    def __init__(self, parent, app):
        super().__init__(parent, bg=BG)
        self.app = app
        top = tk.Frame(self, bg=BG)
        top.pack(fill="x", padx=26, pady=(22, 6))
        page_title(top, "Licencia", "Activa tu clave para desbloquear las funciones PRO.", accent=YELLOW).pack(anchor="w")
        self.scroll = ScrollFrame(self)
        self.scroll.pack(fill="both", expand=True, padx=(26, 10), pady=(8, 10))
        self.root = self.scroll.inner
        self.build()

    def on_show(self):
        self.build()

    def build(self):
        for w in self.root.winfo_children():
            w.destroy()
        root = self.root
        st = lic.status()
        col = LEVEL_COL[st["level"]]
        c = Card(root, accent=col, title="Tu licencia")
        c.pack(fill="x", pady=(0, 12))
        row = tk.Frame(c.body, bg=PANEL)
        row.pack(fill="x")
        badge(row, LEVEL_TXT[st["level"]], col).pack(side="left")
        tk.Label(row, text="   " + st["msg"], font=F(11, True), fg=FG, bg=PANEL).pack(side="left")
        line = tk.Frame(c.body, bg=PANEL)
        line.pack(fill="x", pady=(10, 0))
        tk.Label(line, text="ID de este PC:", font=F(10), fg=MUTED, bg=PANEL).pack(side="left", padx=(0, 8))
        self.v_pc = tk.StringVar(value=lic.pc_id())
        _entry(line, self.v_pc, 24, readonly=True).pack(side="left", ipady=4, padx=(0, 8))
        NeonButton(line, "Copiar", lambda: self.copy(self.v_pc.get(), "ID copiado"), color=CYAN, padx=12, pady=5, font=F(9, True)).pack(side="left")
        WrapLabel(c.body, text="Si quien te dio la clave la quiere atada a tu PC, mándale este ID.", font=F(9), fg=MUTED).pack(fill="x", pady=(6, 0))

        a = Card(root, accent=CYAN, title="Activar una clave")
        a.pack(fill="x", pady=(0, 12))
        self.v_key = tk.StringVar()
        _entry(a.body, self.v_key, 70).pack(fill="x", ipady=6)
        r2 = tk.Frame(a.body, bg=PANEL)
        r2.pack(fill="x", pady=(8, 0))
        NeonButton(r2, "Pegar", self.paste, color=CYAN, padx=14, pady=6, font=F(10, True)).pack(side="left")
        NeonButton(r2, "ACTIVAR", self.activate, color=GREEN, filled=True, padx=22, pady=6, font=F(10, True)).pack(side="left", padx=8)
        self.msg = tk.Label(a.body, text="", font=F(10, True), fg=MUTED, bg=PANEL, anchor="w", justify="left")
        self.msg.pack(fill="x", pady=(8, 0))

        inc = Card(root, accent=PINK, title="Qué incluye PRO")
        inc.pack(fill="x", pady=(0, 12))
        names = {k: t for _s, items in sys.modules[type(self.app).__module__].SECTIONS for k, _i, t in items}
        WrapLabel(inc.body, text=", ".join(names[k] for k in names if k in lic.PRO_PAGES) + ".",
                  font=F(10), fg=FG).pack(fill="x")
        WrapLabel(inc.body, text="GRATIS incluye solo: análisis de tu PC, limpieza, monitor, historial y actualizaciones.", font=F(9), fg=MUTED).pack(fill="x", pady=(6, 0))

        if lic.is_pro():
            self.build_color(root)
            self.build_config(root)
        if lic.owner_secret() or DEMO:
            self.build_generator(root)
            self.build_registry(root)

    # ------------------------------------------------------------------
    def build_color(self, root):
        c = Card(root, accent=CYAN, title="Tu color PRO")
        c.pack(fill="x", pady=(0, 12))
        WrapLabel(c.body, text="Elige el color de HellOP. Se aplica al reiniciar la app.", font=F(9), fg=MUTED).pack(fill="x", pady=(0, 8))
        row = tk.Frame(c.body, bg=PANEL)
        row.pack(fill="x")
        self.cur_color = widgets.ACENTO
        for name, pal in widgets.ACENTOS.items():
            NeonButton(row, name.capitalize() + ("  ✓" if name == self.cur_color else ""), lambda n=name: self.pick_color(n), color=pal[7],
                       filled=(name == self.cur_color), padx=18, pady=7, font=F(10, True)).pack(side="left", padx=(0, 8))
        self.cmsg = tk.Label(c.body, text="", font=F(10, True), fg=MUTED, bg=PANEL, anchor="w")
        self.cmsg.pack(fill="x", pady=(8, 0))
        self.crow = tk.Frame(c.body, bg=PANEL)
        self.crow.pack(fill="x")

    def pick_color(self, name):
        try:
            widgets.guardar_acento(name)
        except (OSError, ValueError) as e:
            self.cmsg.config(text=f"✗ {e}", fg=RED)
            return
        self.cmsg.config(text=f"✓ Color «{name}» guardado. Reinicia para verlo.", fg=GREEN)
        for w in self.crow.winfo_children():
            w.destroy()
        NeonButton(self.crow, "↻  Reiniciar ahora", self.app.restart_now, color=CYAN, filled=True, padx=16, pady=6,
                   font=F(10, True)).pack(side="left", pady=(8, 0))

    # ------------------------------------------------------------------
    def build_config(self, root):
        c = Card(root, accent=PINK, title="Mi configuración (exportar / importar)")
        c.pack(fill="x", pady=(0, 12))
        WrapLabel(c.body, text="Guarda tus ajustes en un archivo para llevarlos a otro PC o pasárselos a un amigo. No incluye tu clave, "
                               "tu ID de PC ni rutas de tu equipo. Al importar no se aplica nada solo: tú marcas qué quieres.",
                  font=F(9), fg=MUTED).pack(fill="x", pady=(0, 8))
        row = tk.Frame(c.body, bg=PANEL)
        row.pack(fill="x")
        NeonButton(row, "⇪  Exportar a archivo…", self.export_cfg, color=PINK, filled=True, padx=18, pady=7, font=F(10, True)).pack(side="left")
        NeonButton(row, "⇩  Importar archivo…", self.import_cfg, color=CYAN, padx=18, pady=7, font=F(10, True)).pack(side="left", padx=8)
        self.kmsg = tk.Label(c.body, text="", font=F(10, True), fg=MUTED, bg=PANEL, anchor="w", justify="left")
        self.kmsg.pack(fill="x", pady=(8, 0))
        self.kbox = tk.Frame(c.body, bg=PANEL)
        self.kbox.pack(fill="x")

    def export_cfg(self):
        path = filedialog.asksaveasfilename(title="Guardar mi configuración", defaultextension=".json", initialfile="mi-configuracion-hellop.json",
                                            filetypes=[("Configuración de HellOP", "*.json")])
        if not path:
            return
        try:
            nt, ng = config_io.export(path)
        except OSError as e:
            self.kmsg.config(text=f"✗ No pude guardar: {e}", fg=RED)
            return
        self.kmsg.config(text=f"✓ Guardado: {nt} tweaks y {ng} juegos.", fg=GREEN)

    def import_cfg(self):
        path = filedialog.askopenfilename(title="Abrir una configuración de HellOP", filetypes=[("Configuración de HellOP", "*.json")])
        if not path:
            return
        try:
            cfg = config_io.read(path)
        except (ValueError, OSError) as e:
            self.kmsg.config(text=f"✗ {e}", fg=RED)
            return
        self.kmsg.config(text="Mirando qué se puede aplicar en este PC…", fg=CYAN)
        self.app.bg(lambda: config_io.applicable_tweaks(cfg), lambda acts: self._show_import(cfg, acts),
                    lambda e: self.kmsg.config(text=f"✗ {e}", fg=RED))

    def _show_import(self, cfg, acts):
        for w in self.kbox.winfo_children():
            w.destroy()
        self.kmsg.config(text=f"Configuración de HellOP v{cfg['version']} ({cfg['created'] or 'sin fecha'}). Marca lo que quieras aplicar:", fg=FG)
        from widgets import checkbox
        self.k_t = []
        for a in acts:
            v = tk.BooleanVar(value=False)
            self.k_t.append((a, v))
            checkbox(self.kbox, f"{a.title}   [riesgo {a.risk}]", v, bg=PANEL, font=F(9)).pack(anchor="w", pady=1)
        skipped = len(cfg["tweaks"]) - len(acts)
        if skipped > 0:
            WrapLabel(self.kbox, text=f"{skipped} tweak(s) no se ofrecen: ya están aplicados o no corresponden a este equipo.", font=F(9), fg=MUTED).pack(fill="x")
        self.k_g = tk.BooleanVar(value=False)
        if cfg["games"]:
            checkbox(self.kbox, f"Usar sus perfiles de juego ({len(cfg['games'])}; solo en los juegos que tú también tengas)", self.k_g, bg=PANEL, font=F(9)).pack(anchor="w", pady=1)
        self.k_c = tk.BooleanVar(value=False)
        if cfg["acento"]:
            checkbox(self.kbox, f"Usar su color ({cfg['acento']})", self.k_c, bg=PANEL, font=F(9)).pack(anchor="w", pady=1)
        NeonButton(self.kbox, "APLICAR LO MARCADO", lambda: self.apply_import(cfg), color=GREEN, filled=True, padx=18, pady=7,
                   font=F(10, True)).pack(anchor="w", pady=(8, 0))

    def apply_import(self, cfg):
        chosen = [a for a, v in self.k_t if v.get()]
        want_g, want_c = self.k_g.get(), self.k_c.get()

        def work():
            ok = fail = 0
            for a in chosen:
                r = actions.execute(a)
                ok += r.ok
                fail += (not r.ok)
            g = config_io.apply_games(cfg) if want_g else (0, [])
            if want_c and cfg["acento"]:
                widgets.guardar_acento(cfg["acento"])
            return ok, fail, g

        def done(res):
            ok, fail, (gn, missing) = res
            parts = [f"{ok} tweaks aplicados"] + ([f"{fail} fallaron"] if fail else []) + ([f"perfiles en {gn} juegos"] if want_g else []) \
                + (["color guardado: reinicia para verlo"] if want_c and cfg["acento"] else [])
            self.kmsg.config(text="✓ " + " · ".join(parts), fg=GREEN if not fail else YELLOW)
        self.app.bg(work, done, lambda e: self.kmsg.config(text=f"✗ {e}", fg=RED))

    # ------------------------------------------------------------------
    def build_generator(self, root):
        g = Card(root, accent=PINK, title="Generador de claves (solo tú lo ves)")
        g.pack(fill="x", pady=(0, 12))
        WrapLabel(g.body, text="Crea una clave con caducidad. Si pegas el ID del PC de la otra persona, la clave solo funcionará en su PC; "
                               "si lo dejas vacío, valdrá en cualquier PC.", font=F(9), fg=MUTED).pack(fill="x")
        rn = tk.Frame(g.body, bg=PANEL)
        rn.pack(fill="x", pady=(8, 0))
        tk.Label(rn, text="¿Para quién es?", font=F(10), fg=MUTED, bg=PANEL).pack(side="left", padx=(0, 8))
        self.v_gname = tk.StringVar()
        _entry(rn, self.v_gname, 30).pack(side="left", ipady=4)
        tk.Label(rn, text="  (un nombre o nota, para tu lista)", font=F(9), fg=MUTED, bg=PANEL).pack(side="left")
        r = tk.Frame(g.body, bg=PANEL)
        r.pack(fill="x", pady=(8, 0))
        tk.Label(r, text="ID del PC:", font=F(10), fg=MUTED, bg=PANEL).pack(side="left", padx=(0, 8))
        self.v_gpc = tk.StringVar()
        _entry(r, self.v_gpc, 26).pack(side="left", ipady=4)
        d = tk.Frame(g.body, bg=PANEL)
        d.pack(fill="x", pady=(8, 0))
        tk.Label(d, text="Caduca en:", font=F(10), fg=MUTED, bg=PANEL).pack(side="left", padx=(0, 8))
        self.days = 30
        self.dbtn = {}
        for n, label in ((7, "7 días"), (30, "30 días"), (90, "90 días"), (180, "6 meses"), (365, "1 año")):
            b = NeonButton(d, label, lambda n_=n: self.set_days(n_), color=MUTED, padx=12, pady=5, font=F(9, True))
            b.pack(side="left", padx=3)
            self.dbtn[n] = b
        self.set_days(30)
        fila = tk.Frame(g.body, bg=PANEL)
        fila.pack(anchor="w", pady=(10, 0))
        NeonButton(fila, "✦  GENERAR CLAVE", self.generate, color=PINK, filled=True, padx=22, pady=7, font=F(10, True)).pack(side="left")
        NeonButton(fila, "▶  Ver animación «Bienvenido a Pro»", lambda: self.app.pro_welcome(), color=CYAN, padx=16, pady=7,
                   font=F(10, True)).pack(side="left", padx=10)
        self.v_out = tk.StringVar()
        _entry(g.body, self.v_out, 70, readonly=True).pack(fill="x", ipady=6, pady=(10, 0))
        r3 = tk.Frame(g.body, bg=PANEL)
        r3.pack(fill="x", pady=(8, 0))
        NeonButton(r3, "Copiar clave", lambda: self.copy(self.v_out.get(), "Clave copiada"), color=CYAN, padx=14, pady=6, font=F(10, True)).pack(side="left")
        self.gmsg = tk.Label(r3, text="", font=F(10, True), fg=MUTED, bg=PANEL)
        self.gmsg.pack(side="left", padx=12)

    # ------------------------------------------------------------------
    def build_registry(self, root):
        self.reg_card = Card(root, accent=YELLOW, title="Claves que has dado (puedes anularlas aquí)")
        self.reg_card.pack(fill="x", pady=(0, 12))
        self.build_registry_body()

    def build_registry_body(self):
        card = getattr(self, "reg_card", None)
        if card is None or not card.winfo_exists():
            return
        for w in card.body.winfo_children():
            w.destroy()
        b = card.body
        items = sorted(claves.load(), key=lambda e: e["caduca"])
        if not claves.token():
            WrapLabel(b, text="Para poder ANULAR claves necesito un token de GitHub (solo la primera vez). Créalo en GitHub: tu foto → Settings → "
                              "Developer settings → Personal access tokens → Fine-grained tokens → Generate new token. Elige solo el repositorio "
                              "PCOptimizer (el público) y en Permissions → Contents: Read and write. Se guarda solo en tu PC.",
                      font=F(9), fg=MUTED).pack(fill="x", pady=(0, 6))
            tr = tk.Frame(b, bg=PANEL)
            tr.pack(fill="x", pady=(0, 8))
            self.v_tok = tk.StringVar()
            _entry(tr, self.v_tok, 46).pack(side="left", ipady=4)
            NeonButton(tr, "Guardar token", self.save_token, color=YELLOW, filled=True, padx=14, pady=5, font=F(9, True)).pack(side="left", padx=8)
        else:
            tr = tk.Frame(b, bg=PANEL)
            tr.pack(fill="x", pady=(0, 8))
            tk.Label(tr, text="✓ Token guardado: puedes anular claves.", font=F(9, True), fg=GREEN, bg=PANEL).pack(side="left")
            pend = [e for e in items if e.get("anulada") and not e.get("publicada")]
            if pend:
                NeonButton(tr, f"Publicar {len(pend)} anulación(es) pendiente(s)", self.publish_pending, color=YELLOW, filled=True,
                           padx=12, pady=4, font=F(9, True)).pack(side="left", padx=10)
        pronto = claves.por_vencer()
        if pronto:
            WrapLabel(b, text="⚠ Vencen pronto: " + ", ".join(f"{e['nombre']} ({claves.estado(e)[1]} d)" for e in pronto) + ".",
                      font=F(10, True), fg=YELLOW).pack(fill="x", pady=(0, 6))
        self.rmsg = tk.Label(b, text="", font=F(10, True), fg=MUTED, bg=PANEL, anchor="w", justify="left", wraplength=760)
        self.rmsg.pack(fill="x", pady=(0, 4))
        if not items:
            WrapLabel(b, text="Aún no has generado ninguna clave desde esta versión. Cada clave nueva aparecerá aquí.",
                      font=F(9), fg=MUTED).pack(fill="x")
            return
        col = {"activa": GREEN, "pronto": YELLOW, "caducada": MUTED, "anulada": RED, "pendiente": YELLOW}
        txt = {"activa": "ACTIVA", "pronto": "VENCE PRONTO", "caducada": "CADUCADA", "anulada": "ANULADA", "pendiente": "ANULACIÓN PENDIENTE"}
        for e in items:
            est, dias = claves.estado(e)
            row = tk.Frame(b, bg=PANEL)
            row.pack(fill="x", pady=4)
            tx = tk.Frame(row, bg=PANEL)
            tx.pack(side="left", fill="x", expand=True)
            head = tk.Frame(tx, bg=PANEL)
            head.pack(fill="x")
            tk.Label(head, text=e["nombre"], font=F(10, True), fg=FG, bg=PANEL).pack(side="left")
            badge(head, txt[est], col[est]).pack(side="left", padx=8)
            cad = date_es(e["caduca"])
            tk.Label(tx, text=f"Caduca el {cad}" + (f" · quedan {dias} días" if dias >= 0 else " · ya caducó")
                     + (f" · atada a un PC" if e.get("pc") else " · vale en cualquier PC"), font=F(9), fg=MUTED, bg=PANEL, anchor="w").pack(fill="x")
            btns = tk.Frame(row, bg=PANEL)
            btns.pack(side="right")
            NeonButton(btns, "Copiar", lambda k=e["key"]: self.copy(k, "Clave copiada"), color=CYAN, padx=10, pady=4, font=F(9, True)).pack(side="left", padx=3)
            if e.get("anulada"):
                NeonButton(btns, "Reactivar", lambda i=e["id"]: self.reactivate(i), color=GREEN, padx=10, pady=4, font=F(9, True)).pack(side="left", padx=3)
            elif est != "caducada":
                NeonButton(btns, "Anular", lambda i=e["id"], n=e["nombre"]: self.revoke(i, n), color=RED, filled=True, padx=12, pady=4,
                           font=F(9, True)).pack(side="left", padx=3)
            if est in ("caducada", "anulada"):
                NeonButton(btns, "Quitar", lambda i=e["id"]: self.drop(i), color=MUTED, padx=10, pady=4, font=F(9, True)).pack(side="left", padx=3)

    def save_token(self):
        try:
            claves.guardar_token(self.v_tok.get())
        except (OSError, claves.ClavesError) as e:
            self.rmsg.config(text=f"✗ {e}", fg=RED)
            return
        self.build_registry_body()
        self.rmsg.config(text="✓ Token guardado.", fg=GREEN)
        if any(e.get("anulada") and not e.get("publicada") for e in claves.load()):
            self.publish_pending()

    def _run_reg(self, work, ok_text=None):
        """Ejecuta una operación de red del registro en segundo plano y vuelve a pintar la lista."""
        self.rmsg.config(text="Un momento…", fg=CYAN)

        def done(res):
            self.build_registry_body()
            okf, msg = res if isinstance(res, tuple) else (True, res)
            self.rmsg.config(text=("✓ " if okf else "⚠ ") + msg, fg=GREEN if okf else YELLOW)
        self.app.bg(work, done, lambda e: self.rmsg.config(text=f"✗ {e}", fg=RED))

    def revoke(self, kid, nombre):
        if not DEMO and not messagebox.askyesno("Anular clave", f"Vas a anular la clave de «{nombre}».\n\nSe quedará sin PRO en cuanto su "
                                                "HellOP se conecte a internet. ¿Seguro?"):
            return
        if DEMO:
            self.rmsg.config(text="(Demo) aquí se anularía la clave.", fg=YELLOW)
            return
        self._run_reg(lambda: claves.anular(kid))

    def publish_pending(self):
        self._run_reg(claves.publicar_pendientes)

    def reactivate(self, kid):
        if DEMO:
            return
        self._run_reg(lambda: claves.reactivar(kid))

    def drop(self, kid):
        claves.borrar(kid)
        self.build_registry_body()

    def set_days(self, n):
        self.days = n
        for k, b in self.dbtn.items():
            b.set_color(PINK if k == n else MUTED)

    def generate(self):
        sec = lic.owner_secret()
        if not sec:
            self.gmsg.config(text="(Demo) aquí saldría la clave: falta tu llave privada." if DEMO else "Falta tu llave privada.", fg=YELLOW)
            return
        try:
            key, exp = lic.make_key(sec, self.v_gpc.get(), self.days)
        except ValueError as e:
            self.gmsg.config(text=str(e), fg=RED)
            return
        self.v_out.set(key)
        try:
            claves.add(self.v_gname.get(), key, exp, self.v_gpc.get())
            self.gmsg.config(text=f"Lista y apuntada en tu lista · caduca el {exp.strftime('%d/%m/%Y')}", fg=GREEN)
            self.v_gname.set("")
            self.build_registry_body()
        except (OSError, claves.ClavesError) as e:
            self.gmsg.config(text=f"Lista (pero no pude apuntarla: {e})", fg=YELLOW)

    # ------------------------------------------------------------------
    def copy(self, text, ok):
        try:
            self.clipboard_clear()
            self.clipboard_append(text)
            self.app.status(ok)
        except tk.TclError:
            pass

    def paste(self):
        try:
            self.v_key.set(self.clipboard_get().strip())
        except tk.TclError:
            pass

    def activate(self):
        key = self.v_key.get()
        self.msg.config(text="Comprobando la clave…", fg=CYAN)

        def work():
            if not DEMO:
                lic.refresh_revoked(timeout=5)          # por si esa clave ya la anularon
            return lic.activate(key)

        def done(res):
            ok, m = res
            self.msg.config(text=("✓ " if ok else "✗ ") + m, fg=GREEN if ok else RED)
            if ok:
                self.app.refresh_license()
                self.after(900, self.build)
                self.app.pro_welcome()
        self.app.bg(work, done, lambda e: self.msg.config(text=f"✗ {e}", fg=RED))
