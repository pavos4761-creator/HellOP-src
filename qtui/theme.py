"""Colores, fuentes y hoja de estilo (QSS) de HellOP. Dos modos: claro y negro mate.

Todo el color sale de aquí: los widgets propios leen `theme.C[...]` al pintarse y la hoja de estilo se
vuelve a aplicar al cambiar de modo, así el cambio es instantáneo y sin reiniciar."""
import json
import os
import sys

from PySide6.QtGui import QColor, QFont, QFontDatabase

PALETAS = {
    "claro": dict(bg="#eef0f7", side="#ffffff", panel="#ffffff", panel2="#f3f4fb", border="#dfe2f0", fg="#151a2d", muted="#5b6280",
                  accent="#3b5bfd", teal="#0f9b8e", green="#17a56b", yellow="#d9822b", red="#d1383d", on_accent="#ffffff",
                  hover="#e8ebf8", track="#e3e6f2", shadow="#10131a"),
    "oscuro": dict(bg="#121316", side="#1a1c20", panel="#1a1c20", panel2="#23262b", border="#2c3036", fg="#ecedf0", muted="#9aa0aa",
                   accent="#7b92ff", teal="#3ccfc0", green="#3ddc97", yellow="#ffb224", red="#ff6b6b", on_accent="#10131a",
                   hover="#262a30", track="#2b2f35", shadow="#000000"),
}
C = dict(PALETAS["claro"])
MODO = "claro"
TONOS = ("accent", "teal", "green", "yellow", "red", "muted")


def modo_guardado():
    forzado = os.environ.get("HELLOP_MODE", "").strip().lower()
    if forzado in ("claro", "oscuro"):
        return forzado
    try:
        from util import APP_DIR
        m = str(json.loads((APP_DIR / "tema.json").read_text("utf-8")).get("modo", "")).lower()
        return m if m in PALETAS else "claro"
    except Exception:  # noqa: BLE001
        return "claro"


def guarda_modo(modo):
    try:
        from util import APP_DIR
        d = {}
        try:
            d = json.loads((APP_DIR / "tema.json").read_text("utf-8"))
        except Exception:  # noqa: BLE001
            pass
        d["modo"] = modo
        APP_DIR.mkdir(parents=True, exist_ok=True)
        (APP_DIR / "tema.json").write_text(json.dumps(d), "utf-8")
    except Exception:  # noqa: BLE001
        pass


def pon_modo(modo):
    global MODO
    MODO = modo if modo in PALETAS else "claro"
    C.clear()
    C.update(PALETAS[MODO])


def color(nombre, alpha=None):
    q = QColor(C.get(nombre, nombre))
    if alpha is not None:
        q.setAlphaF(alpha)
    return q


def mezcla(a, b, t):
    qa, qb = QColor(C.get(a, a)), QColor(C.get(b, b))
    return QColor(int(qa.red() + (qb.red() - qa.red()) * t), int(qa.green() + (qb.green() - qa.green()) * t),
                  int(qa.blue() + (qb.blue() - qa.blue()) * t))


def hexa(nombre, t=None, con="panel"):
    """Color como #rrggbb; con t mezcla `nombre` sobre `con` (t=0.15 → tinte suave)."""
    if t is None:
        return QColor(C.get(nombre, nombre)).name()
    return mezcla(con, nombre, t).name()


_FAMILIA = None


def familia():
    """Segoe UI Variable en Windows 11 (la fuente del propio sistema); si no existe, la mejor disponible."""
    global _FAMILIA
    if _FAMILIA:
        return _FAMILIA
    libres = set(QFontDatabase.families())
    for f in ("Segoe UI Variable Text", "Segoe UI Variable", "Segoe UI", "SF Pro Text", "Inter", "Noto Sans", "DejaVu Sans"):
        if f in libres:
            _FAMILIA = f
            break
    else:
        _FAMILIA = QFont().family()
    return _FAMILIA


def fuente(px=13, bold=False, mono=False):
    f = QFont("Cascadia Mono" if mono else familia())
    f.setPixelSize(int(px))
    f.setWeight(QFont.Weight.DemiBold if bold else QFont.Weight.Normal)
    return f


def qss():
    c = C
    fam = familia()
    tono = "\n".join(
        f'QLabel[tone="{t}"] {{ color: {c[t] if t != "muted" else c["muted"]}; }}' for t in TONOS)
    return f"""
* {{ font-family: "{fam}"; font-size: 13px; color: {c['fg']}; outline: 0; }}
QMainWindow, QWidget#raiz {{ background: transparent; }}
QWidget#ventana {{ background: {c['bg']}; border: 1px solid {c['border']}; border-radius: 10px; }}
QWidget#pagina, QScrollArea, QScrollArea > QWidget > QWidget {{ background: transparent; }}
QScrollArea {{ border: none; }}
QLabel {{ background: transparent; }}
QLabel[role="title"] {{ font-size: 26px; font-weight: 700; }}
QLabel[role="h2"] {{ font-size: 16px; font-weight: 600; }}
QLabel[role="h3"] {{ font-size: 14px; font-weight: 600; }}
QLabel[role="muted"] {{ color: {c['muted']}; }}
QLabel[role="small"] {{ color: {c['muted']}; font-size: 12px; }}
QLabel[role="mono"] {{ font-family: "Cascadia Mono", "Consolas", "DejaVu Sans Mono"; font-size: 12px; color: {c['accent']}; }}
QLabel[role="big"] {{ font-size: 34px; font-weight: 700; }}
{tono}
QFrame#card {{ background: {c['panel']}; border: 1px solid {c['border']}; border-radius: 12px; }}
QFrame#card[sel="true"] {{ border: 2px solid {c['green']}; }}
QFrame#card[tone="green"] {{ border-left: 3px solid {c['green']}; }}
QFrame#card[tone="yellow"] {{ border-left: 3px solid {c['yellow']}; }}
QFrame#card[tone="red"] {{ border-left: 3px solid {c['red']}; }}
QFrame#card[tone="accent"] {{ border-left: 3px solid {c['accent']}; }}
QFrame#card[tone="teal"] {{ border-left: 3px solid {c['teal']}; }}
QFrame#cardsoft {{ background: {c['panel2']}; border: 1px solid {c['border']}; border-radius: 10px; }}
QFrame#sidebar {{ background: {c['side']}; border: 1px solid {c['border']}; border-radius: 12px; }}
QFrame#barra {{ background: {c['panel']}; border: 1px solid {c['border']}; border-radius: 12px; }}
QFrame#titulo {{ background: transparent; }}
QFrame#sep {{ background: {c['border']}; max-height: 1px; min-height: 1px; border: none; }}
QPushButton {{ border-radius: 8px; padding: 7px 16px; font-weight: 600; border: 1px solid transparent; }}
QPushButton[kind="primary"] {{ background: {c['accent']}; color: {c['on_accent']}; }}
QPushButton[kind="primary"]:hover {{ background: {hexa('accent', 0.85, 'fg')}; }}
QPushButton[kind="primary"][tone="green"] {{ background: {c['green']}; color: {c['on_accent']}; }}
QPushButton[kind="primary"][tone="teal"] {{ background: {c['teal']}; color: {c['on_accent']}; }}
QPushButton[kind="primary"][tone="yellow"] {{ background: {c['yellow']}; color: {c['on_accent']}; }}
QPushButton[kind="primary"][tone="red"] {{ background: {c['red']}; color: #ffffff; }}
QPushButton[kind="soft"] {{ background: {hexa('accent', 0.14)}; color: {c['accent']}; }}
QPushButton[kind="soft"]:hover {{ background: {hexa('accent', 0.24)}; }}
QPushButton[kind="soft"][tone="green"] {{ background: {hexa('green', 0.14)}; color: {c['green']}; }}
QPushButton[kind="soft"][tone="yellow"] {{ background: {hexa('yellow', 0.16)}; color: {c['yellow']}; }}
QPushButton[kind="soft"][tone="red"] {{ background: {hexa('red', 0.14)}; color: {c['red']}; }}
QPushButton[kind="soft"][tone="teal"] {{ background: {hexa('teal', 0.14)}; color: {c['teal']}; }}
QPushButton[kind="ghost"] {{ background: {c['panel2']}; color: {c['fg']}; border: 1px solid {c['border']}; }}
QPushButton[kind="ghost"]:hover {{ background: {c['hover']}; }}
QPushButton[kind="link"] {{ background: transparent; color: {c['accent']}; padding: 2px 4px; }}
QPushButton[kind="link"]:hover {{ text-decoration: underline; }}
QPushButton:disabled {{ background: {c['track']}; color: {c['muted']}; border: 1px solid transparent; }}
QPushButton:focus {{ border: 1px solid {c['accent']}; }}
QPushButton#win {{ background: transparent; border-radius: 6px; padding: 4px 12px; font-size: 14px; }}
QPushButton#win:hover {{ background: {c['hover']}; }}
QPushButton#winx:hover {{ background: {c['red']}; color: #ffffff; }}
QPushButton#winx {{ background: transparent; border-radius: 6px; padding: 4px 12px; font-size: 14px; }}
QPushButton#nav {{ background: transparent; border: none; border-radius: 8px; padding: 7px 12px; text-align: left; font-weight: 500;
  color: {c['fg']}; }}
QPushButton#nav:hover {{ background: {c['hover']}; }}
QPushButton#nav[activo="true"] {{ background: {hexa('accent', 0.14)}; color: {c['accent']}; font-weight: 700; }}
QPushButton#grupo {{ background: transparent; border: none; text-align: left; padding: 8px 12px 4px 12px; color: {c['muted']};
  font-size: 11px; font-weight: 700; }}
QLineEdit, QComboBox, QSpinBox {{ background: {c['panel2']}; border: 1px solid {c['border']}; border-radius: 8px; padding: 7px 10px;
  selection-background-color: {c['accent']}; selection-color: {c['on_accent']}; }}
QLineEdit:focus, QComboBox:focus {{ border: 1px solid {c['accent']}; }}
QComboBox::drop-down {{ border: none; width: 22px; }}
QComboBox QAbstractItemView {{ background: {c['panel']}; border: 1px solid {c['border']}; selection-background-color: {hexa('accent', 0.2)};
  selection-color: {c['fg']}; padding: 4px; }}
QPlainTextEdit, QTextEdit {{ background: {c['panel2']}; border: 1px solid {c['border']}; border-radius: 8px; padding: 8px;
  font-family: "Cascadia Mono", "Consolas", "DejaVu Sans Mono"; font-size: 12px; }}
QProgressBar {{ background: {c['track']}; border: none; border-radius: 4px; max-height: 8px; min-height: 8px; text-align: center; color: transparent; }}
QProgressBar::chunk {{ background: {c['accent']}; border-radius: 4px; }}
QProgressBar[tone="green"]::chunk {{ background: {c['green']}; }}
QProgressBar[tone="yellow"]::chunk {{ background: {c['yellow']}; }}
QProgressBar[tone="red"]::chunk {{ background: {c['red']}; }}
QProgressBar[tone="teal"]::chunk {{ background: {c['teal']}; }}
QScrollBar:vertical {{ background: transparent; width: 10px; margin: 2px; }}
QScrollBar::handle:vertical {{ background: {c['border']}; border-radius: 4px; min-height: 36px; }}
QScrollBar::handle:vertical:hover {{ background: {c['muted']}; }}
QScrollBar::add-line, QScrollBar::sub-line, QScrollBar::add-page, QScrollBar::sub-page {{ background: none; height: 0; width: 0; }}
QScrollBar:horizontal {{ background: transparent; height: 10px; margin: 2px; }}
QScrollBar::handle:horizontal {{ background: {c['border']}; border-radius: 4px; min-width: 36px; }}
QTableWidget, QTreeWidget, QListWidget {{ background: {c['panel']}; border: 1px solid {c['border']}; border-radius: 10px; gridline-color: {c['border']};
  alternate-background-color: {c['panel2']}; selection-background-color: {hexa('accent', 0.18)}; selection-color: {c['fg']}; }}
QHeaderView::section {{ background: {c['panel2']}; color: {c['muted']}; border: none; border-bottom: 1px solid {c['border']}; padding: 6px 8px; font-weight: 600; }}
QToolTip {{ background: {c['panel']}; color: {c['fg']}; border: 1px solid {c['border']}; padding: 6px; }}
QMenu {{ background: {c['panel']}; border: 1px solid {c['border']}; border-radius: 8px; padding: 4px; }}
QMenu::item {{ padding: 6px 18px; border-radius: 6px; }}
QMenu::item:selected {{ background: {hexa('accent', 0.16)}; }}
QDialog, QMessageBox {{ background: {c['panel']}; }}
QLabel#toast {{ background: {c['panel']}; border: 1px solid {c['border']}; border-left: 4px solid {c['accent']}; border-radius: 8px; padding: 12px 16px;
  font-weight: 600; }}
"""
