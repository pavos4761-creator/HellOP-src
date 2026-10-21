"""PC Optimizer — punto de entrada.
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
    from app import App
    App().mainloop()


if __name__ == "__main__":
    main()
