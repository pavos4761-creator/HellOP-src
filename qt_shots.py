"""Prueba automática de la interfaz Qt: abre todas las pantallas (modo demo), les saca una captura y apunta los errores."""
import faulthandler
import os
import sys
import time
import traceback

faulthandler.dump_traceback_later(int(os.environ.get("SHOTS_TIMEOUT", "420")), exit=True)
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ["HELLOP_DEMO"] = "1"
sys.argv = ["main.py", "--demo"]
sys.path.insert(0, os.getcwd())
OUT = os.environ.get("OUT", "shots")
os.makedirs(OUT, exist_ok=True)

from PySide6.QtWidgets import QApplication  # noqa: E402

errores = []


def hook(t, v, tb):
    errores.append("".join(traceback.format_exception(t, v, tb)))


sys.excepthook = hook


def espera(app, s):
    fin = time.time() + s
    while time.time() < fin:
        app.processEvents()
        time.sleep(0.01)


def main():
    print('importando', flush=True)
    from qtui import app as qapp, shell
    print('creando ventana', flush=True)
    app, v = qapp.run()
    v.resize(1240, 820)
    # las excepciones dentro de slots/ hilos quedan en errores.log: las recogemos también
    v.puente._registra = lambda tb: errores.append(tb)
    claves = os.environ.get("PAGES", "").split(",") if os.environ.get("PAGES") else [k for k, _i, _t in shell.PAGES]
    informe = []
    from qtui import theme
    modo = theme.MODO
    for k in claves:
        antes = len(errores)
        try:
            v.ir(k)
            espera(app, float(os.environ.get("ESPERA", "1.2")))
            v.grab().save(f"{OUT}/{modo}_{k}.png")
        except Exception:  # noqa: BLE001
            errores.append(f"[{k}] " + traceback.format_exc())
        pend = getattr(v.pages.get(k), "pendiente", False) if v.pages.creada(k) else False
        informe.append(f"{k:10s} {'PENDIENTE' if pend else ('ERROR' if len(errores) > antes else 'ok')}")
    open(f"{OUT}/informe_{modo}.txt", "w", encoding="utf-8").write("\n".join(informe) + f"\n\nERRORES: {len(errores)}\n" + "\n---\n".join(errores[:20]))
    print("\n".join(informe), "\nERRORES", len(errores))
    for e in errores[:10]:
        print(e[-1200:])


try:
    main()
except BaseException:  # noqa: BLE001
    print('FALLO', traceback.format_exc(), flush=True)
    raise
print('FIN', flush=True)
