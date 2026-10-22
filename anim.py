"""Pequeñas ayudas de animación para Tk (todo con `after`, sin hilos)."""
import os

ENABLED = os.environ.get("HELLOP_NO_ANIM") != "1"      # HELLOP_NO_ANIM=1 desactiva las animaciones


def ease_out(t):
    return 1 - (1 - t) ** 3


def tween(widget, ms, step, done=None, fps=60):
    """Llama a step(p) con p de 0 a 1 (suavizado) durante `ms` milisegundos. Devuelve una función cancelar()."""
    frames = max(1, int(ms * fps / 1000))
    state = {"i": 0, "job": None, "dead": False}

    def tick():
        if state["dead"]:
            return
        state["i"] += 1
        p = min(1.0, state["i"] / frames)
        try:
            step(ease_out(p))
        except Exception:  # noqa: BLE001  (el widget puede haberse destruido)
            return
        if p < 1.0:
            state["job"] = widget.after(int(1000 / fps), tick)
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
