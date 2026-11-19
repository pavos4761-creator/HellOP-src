"""Arranque de la interfaz Qt."""
import os
import sys


def run():
    os.environ.setdefault("QT_ENABLE_HIGHDPI_SCALING", "1")
    from PySide6.QtCore import Qt
    from PySide6.QtGui import QFont
    from PySide6.QtWidgets import QApplication
    from . import theme
    QApplication.setHighDpiScaleFactorRoundingPolicy(Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)
    app = QApplication.instance() or QApplication(sys.argv)
    theme.pon_modo(theme.modo_guardado())
    app.setFont(theme.fuente(13))
    app.setStyleSheet(theme.qss())
    app.setApplicationName("HellOP")
    from .shell import Ventana
    v = Ventana()
    v.show()
    if sys.platform == "win32":      # esquinas redondeadas de Windows 11 (en Windows 10 no hace nada)
        try:
            import ctypes
            ctypes.windll.dwmapi.DwmSetWindowAttribute(int(v.winId()), 33, ctypes.byref(ctypes.c_int(2)), 4)
        except Exception:  # noqa: BLE001
            pass
    return app, v


def main():
    app, v = run()
    sys.exit(app.exec())
