"""Hilos de trabajo para la interfaz Qt: `bg(fn, done, fail)` corre `fn` fuera de la pantalla y llama a `done` en el hilo de la interfaz."""
import traceback

from PySide6.QtCore import QObject, QRunnable, QThreadPool, Signal, Slot, Qt


class _Senales(QObject):
    hecho = Signal(object)
    fallo = Signal(object)
    llamada = Signal(object)


class _Tarea(QRunnable):
    def __init__(self, fn, senales):
        super().__init__()
        self.fn, self.s = fn, senales

    @Slot()
    def run(self):
        try:
            r = self.fn()
        except Exception as e:  # noqa: BLE001
            e._tb = traceback.format_exc()
            self.s.fallo.emit(e)
            return
        self.s.hecho.emit(r)


class Puente(QObject):
    """Vive en el hilo de la interfaz. `ui(fn, *args)` se puede llamar desde cualquier hilo."""
    _llamada = Signal(object)

    def __init__(self, error_por_defecto=None):
        super().__init__()
        self.pool = QThreadPool.globalInstance()
        self.pool.setMaxThreadCount(12)
        self.error_por_defecto = error_por_defecto
        self._vivos = set()
        self._llamada.connect(self._ejecuta, Qt.ConnectionType.QueuedConnection)

    @Slot(object)
    def _ejecuta(self, f):
        try:
            f()
        except Exception:  # noqa: BLE001
            self._registra(traceback.format_exc())

    def _registra(self, tb):
        try:
            from util import APP_DIR
            APP_DIR.mkdir(parents=True, exist_ok=True)
            with open(APP_DIR / "errores.log", "a", encoding="utf-8") as f:
                f.write(tb + "\n")
        except Exception:  # noqa: BLE001
            pass

    def ui(self, fn, *args):
        self._llamada.emit(lambda: fn(*args))

    def bg(self, fn, done=None, fail=None):
        s = _Senales()
        self._vivos.add(s)

        def ok(r):
            self._vivos.discard(s)
            if done:
                self._ejecuta(lambda: done(r))

        def mal(e):
            self._vivos.discard(s)
            self._registra(getattr(e, "_tb", repr(e)))
            if fail:
                self._ejecuta(lambda: fail(e))
            elif self.error_por_defecto:
                self._ejecuta(lambda: self.error_por_defecto(e))

        s.hecho.connect(ok, Qt.ConnectionType.QueuedConnection)
        s.fallo.connect(mal, Qt.ConnectionType.QueuedConnection)
        self.pool.start(_Tarea(fn, s))
