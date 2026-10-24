"""Catálogo de «Tweaks» por nivel de riesgo: reúne los ajustes de rendimiento y latencia de HellOP para que tú elijas
cuáles aplicar, con su explicación, su efecto real y su riesgo. Todo se puede deshacer desde el Historial."""
import actions
from actions import REG_DWORD, RegTweak
from util import DEMO

LEVELS = [
    ("bajo", "SEGUROS", "Sin riesgo de inestabilidad. Se pueden dejar siempre puestos.", "green"),
    ("medio", "MEDIOS", "Funcionan bien en la mayoría de equipos, pero pueden dar más calor/consumo o fallar con un driver raro. "
                        "Si algo va mal, deshaz el cambio desde el Historial.", "yellow"),
    ("alto", "EXTREMOS", "Cambian seguridad o el arranque a cambio de FPS. Léelos con calma: algunos anti-cheat los rechazan.", "red"),
]
EFFECTS = {"real": "Efecto real", "pequeño": "Efecto pequeño", "depende": "Depende de tu equipo", "mínimo": "Casi nulo"}

_IFEO = r"SOFTWARE\Microsoft\Windows NT\CurrentVersion\Image File Execution Options"
# juegos con anti-cheat estricto (Vanguard, EasyAntiCheat…): NO se les toca el arranque del proceso
_ANTICHEAT = {"valorant", "fortnite"}
_KNOWN_EXE = {"lol": ("League of Legends.exe", "League of Legends"), "cs2": ("cs2.exe", "Counter-Strike 2")}


def priority_actions():
    """Prioridad ALTA permanente para tus juegos: Windows la aplica sola al abrir el juego (no hace falta tener HellOP abierto)."""
    import games
    import gameprofiles
    found = {}
    try:
        for gid in gameprofiles.find_files():
            if gid in _KNOWN_EXE:
                found[_KNOWN_EXE[gid][0]] = _KNOWN_EXE[gid][1]
        for g in games.load()["games"]:
            exe = g.get("exe") or ""
            low = exe.replace("/", "\\").split("\\")[-1].lower()
            if low.endswith(".exe") and not any(a in low for a in _ANTICHEAT):
                found[exe.replace("/", "\\").split("\\")[-1]] = g.get("name", low)
    except Exception:  # noqa: BLE001
        pass
    acts = []
    for exe, name in sorted(found.items(), key=lambda kv: kv[1].lower()):
        acts.append(RegTweak(
            f"x_gprio:{exe.lower()}", "latency", f"Prioridad alta permanente: {name}",
            f"Windows abrirá «{exe}» siempre con prioridad ALTA en el procesador, aunque HellOP esté cerrado. Así el juego gana "
            "tiempo de CPU frente a lo que haya de fondo (menos tirones con Discord, navegador, etc.). No toques esto en juegos con "
            "anti-cheat estricto: por eso VALORANT y Fortnite no aparecen; para ellos usa el Modo juego automático.",
            [("HKLM", rf"{_IFEO}\{exe}\PerfOptions", "CpuPriorityClass", 3, REG_DWORD)],
            needs_admin=True, profiles=("extreme",), effect="pequeño", risk="bajo"))
    return acts


def collect(progress=None):
    """Lista de acciones aplicables en ESTE equipo (ya filtradas), con .status."""
    if DEMO:
        import time
        time.sleep(1.2)
        pool = [a for a in actions.demo_actions() if a.group in ("latency", "gpu", "tradeoff", "gaming", "speed", "power")]
    else:
        import deepclean
        import extreme
        pool = []
        for step, fn in (("Revisando energía, arranque y registro…", extreme.extreme_actions),
                         ("Revisando tarjeta de red y gráfica…", extreme.hardware_actions),
                         ("Revisando ajustes de juego…", actions.reg_tweaks),
                         ("Revisando Windows Defender y servicios…", deepclean.extra_gaming_actions),
                         ("Buscando tus juegos…", priority_actions)):
            if progress:
                progress(step)
            try:
                pool.extend(fn())
            except Exception:  # noqa: BLE001
                pass
        pool.insert(0, actions.PowerPlanAction())
    out, seen = [], set()
    for a in pool:
        if a.id in seen or a.group in ("bloat", "network", "procs", "startup", "services", "deep"):
            continue
        try:
            st = a.check()
        except Exception:  # noqa: BLE001
            continue
        if st is None:
            continue
        seen.add(a.id)
        a.status = st
        out.append(a)
    return out
