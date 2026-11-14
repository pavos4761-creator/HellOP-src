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
    return app, v


def main():
    app, v = run()
    sys.exit(app.exec())
