"""HellOP — punto de entrada.
Uso:  python main.py          (normal)
      python main.py --demo   (datos de ejemplo, no toca nada)"""
import sys

from util import DEMO, IS_WIN


def main():
    if not IS_WIN and not DEMO:
        print("Esta app es para Windows. Para verla en otro sistema usa:  python main.py --demo")
        sys.exit(1)
    if IS_WIN:
        try:
            import ctypes
            ctypes.windll.shcore.SetProcessDpiAwareness(1)   # texto nítido en pantallas 4K/escaladas
        except Exception:  # noqa: BLE001
            pass
    while True:
        from app import App
        app = App()
        app.after(250, _cierra_splash)
        app.mainloop()
        if not getattr(app, "recarga", False):
            break
        _recarga_modulos()          # cambio de Claro/Oscuro: se vuelven a leer los colores y se abre la ventana otra vez


def _cierra_splash():
    """Cierra la pantallita de carga del .exe (solo existe en el programa compilado)."""
    try:
        import pyi_splash  # type: ignore
        pyi_splash.close()
    except Exception:  # noqa: BLE001
        pass


def _recarga_modulos():
    """Descarta los módulos que traen colores copiados (widgets, páginas...) para que se carguen con la paleta nueva."""
    for n in list(sys.modules):
        if n in ("widgets", "app", "asistente", "bienvenida", "cajas", "config_io", "paleta", "sidebar") or n.startswith("page_"):
            del sys.modules[n]


if __name__ == "__main__":
    main()
