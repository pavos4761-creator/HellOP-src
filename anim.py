"""Pequeñas ayudas de animación para Tk (todo con `after`, sin hilos)."""
import os

ENABLED = os.environ.get("HELLOP_NO_ANIM") != "1"      # HELLOP_NO_ANIM=1 desactiva las animaciones


def ease_out(t):
    return 1 - (1 - t) ** 3


FRAME_MS = 8                                            # 120 fotogramas por segundo (una pantalla de 60 Hz enseñará 60)


def kf(f, ref=16):
    """Suavizado por fotograma f pensado para pasos de `ref` ms, ajustado a FRAME_MS: la velocidad se ve igual pero con más pasos."""
    return 1 - (1 - f) ** (FRAME_MS / ref)


_RELOJ = {"on": False}


def reloj_fino(on=True):
    """Windows trabaja por defecto con relojes de ~15 ms: así `after(8)` no sería de 8 ms. Se pide 1 ms mientras la app está abierta."""
    try:
        import ctypes
        if on and not _RELOJ["on"]:
            ctypes.windll.winmm.timeBeginPeriod(1)
            _RELOJ["on"] = True
        elif not on and _RELOJ["on"]:
            ctypes.windll.winmm.timeEndPeriod(1)
            _RELOJ["on"] = False
    except Exception:  # noqa: BLE001
        pass


def tween(widget, ms, step, done=None, fps=120):
    """Llama a step(p) con p de 0 a 1 (suavizado) durante `ms` milisegundos, medidos con reloj (no por número de fotogramas).
    Devuelve una función cancelar()."""
    import time
    state = {"job": None, "dead": False, "t0": None}

    def tick():
        if state["dead"]:
            return
        if state["t0"] is None:
            state["t0"] = time.perf_counter()
        p = min(1.0, (time.perf_counter() - state["t0"]) * 1000 / max(1, ms))
        try:
            step(ease_out(p))
        except Exception:  # noqa: BLE001  (el widget puede haberse destruido)
            return
        if p < 1.0:
            state["job"] = widget.after(max(1, int(1000 / fps)), tick)
        elif done:
            done()

    def cancel():
        state["dead"] = True
        if state["job"] is not None:
            try:
                widget.after_cancel(state["job"])
            except Exception:  # noqa: BLE001
                pass

    state["job"] = widget.after(0, tick)
    return cancel
