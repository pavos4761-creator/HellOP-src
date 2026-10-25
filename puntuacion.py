"""Puntuación HellOP: una nota de 0 a 100 para tu PC, con medalla y logros.

La nota sale de comprobaciones REALES de tu equipo (las mismas de «Rendimiento oculto», más programas de inicio y espacio libre):
cada una pesa según lo que cuesta de verdad en rendimiento. No es un benchmark ni mide potencia: mide lo bien configurado que está.
"""
import json
import time

import actions
import hidden
from util import APP_DIR, DEMO

LOGROS_FILE = APP_DIR / ("logros_demo.json" if DEMO else "logros.json")
PESO = {"hz": 15, "ramspeed": 15, "channel": 10, "hdd": 10, "vbs": 5, "plan": 10, "rebar": 5, "pcie": 10, "bg": 10, "startup": 10, "space": 5}
FACTOR = {"ok": 1.0, "info": 0.85, "warn": 0.5, "bad": 0.0}
MEDALLAS = [(90, "Diamante", "#7de7ff"), (75, "Oro", "#ffd23f"), (60, "Plata", "#c0c8d8"), (40, "Bronce", "#cd7f32"), (0, "Hierro", "#8a8f98")]

LOGROS = [   # (id, título, descripción)
    ("primer_ajuste", "Primer ajuste", "Aplicaste tu primera optimización."),
    ("diez_ajustes", "Manitas", "Tienes 10 o más ajustes aplicados."),
    ("medidor", "Con números", "Mediste los FPS de un juego."),
    ("arranque_limpio", "Arranque limpio", "5 programas o menos se abren al iniciar."),
    ("sin_problemas", "Sin problemas", "«Rendimiento oculto» no encuentra ningún problema."),
    ("oro", "Medalla de oro", "Tu PC llegó a 75 puntos."),
    ("diamante", "Diamante", "Tu PC llegó a 90 puntos."),
    ("biblioteca", "Jugador", "Tienes 3 o más juegos en tu biblioteca de HellOP."),
    ("pro", "Miembro PRO", "Tienes HellOP PRO."),
]


def medal(score):
    for lim, name, col in MEDALLAS:
        if score >= lim:
            return name, col


def _startup():
    try:
        import arranque
        items, _boot = arranque.entries()
        n = sum(1 for i in items if i["enabled"] and not i["protected"])
        sev = "ok" if n <= 6 else "warn" if n <= 12 else "bad"
        return n, {"key": "startup", "sev": sev, "title": f"{n} programas se abren al iniciar Windows",
                   "fix": ("goto", "arranque", "Abrir el gestor de arranque")}
    except Exception:  # noqa: BLE001
        return None, None


def _space():
    try:
        import sysinfo
        vols = [(f / t * 100) for _m, f, t in sysinfo.volumes() if t]
        if not vols:
            return None
        low = min(vols)
        sev = "ok" if low >= 25 else "warn" if low >= 15 else "bad"
        return {"key": "space", "sev": sev, "title": f"Espacio libre mínimo en tus discos: {low:.0f} %", "fix": ("goto", "clean", "Ir a Limpieza")}
    except Exception:  # noqa: BLE001
        return None


def calcular(progress=lambda s: None):
    """Devuelve {score, medal, perdidos:[(titulo, puntos, fix)], hallazgos, logros, nuevos}."""
    progress("Revisando tu equipo (unos segundos)…")
    found = [f for f in hidden.scan(progress) if f["key"] in PESO]
    progress("Mirando programas de inicio y espacio libre…")
    n_start, st = _startup()
    if st:
        found.append(st)
    sp = _space()
    if sp:
        found.append(sp)
    total = sum(PESO[f["key"]] for f in found) or 1
    got = sum(PESO[f["key"]] * FACTOR[f["sev"]] for f in found)
    score = round(got / total * 100)
    perdidos = []
    for f in found:
        lost = PESO[f["key"]] * (1 - FACTOR[f["sev"]]) / total * 100
        if lost >= 1:
            fix = f.get("fix")
            if fix and fix[0] == "action":
                fix = ("goto", "tweaks", "Ir a Tweaks")        # el arreglo con un clic vive ahora en Tweaks
            perdidos.append((f["title"], round(lost), fix))
    perdidos.sort(key=lambda x: -x[1])
    ctx = {"score": score, "found": found, "startup": n_start}
    logros, nuevos = evaluar(ctx)
    return {"score": score, "medal": medal(score), "perdidos": perdidos, "hallazgos": found, "logros": logros, "nuevos": nuevos}


def _cargar():
    try:
        return json.loads(LOGROS_FILE.read_text("utf-8"))
    except Exception:  # noqa: BLE001
        return {}


def evaluar(ctx):
    """Comprueba los logros, guarda los nuevos con su fecha y devuelve (lista, ids nuevos)."""
    log = [e for e in actions.load_log() if not e.get("undone")]
    try:
        import fps
        medido = bool(fps.load_history())
    except Exception:  # noqa: BLE001
        medido = False
    try:
        import games
        n_juegos = len(games.load()["games"])
    except Exception:  # noqa: BLE001
        n_juegos = 0
    try:
        import licencia
        pro = licencia.is_pro()
    except Exception:  # noqa: BLE001
        pro = False
    f = ctx["found"]
    cond = {
        "primer_ajuste": len(log) >= 1,
        "diez_ajustes": len(log) >= 10,
        "medidor": medido,
        "arranque_limpio": ctx["startup"] is not None and ctx["startup"] <= 5,
        "sin_problemas": bool(f) and not any(x["sev"] in ("bad", "warn") for x in f),
        "oro": ctx["score"] >= 75,
        "diamante": ctx["score"] >= 90,
        "biblioteca": n_juegos >= 3,
        "pro": pro,
    }
    saved = _cargar()
    nuevos = []
    for lid, ok in cond.items():
        if ok and lid not in saved:
            saved[lid] = time.strftime("%Y-%m-%d")
            nuevos.append(lid)
    if nuevos:
        try:
            APP_DIR.mkdir(parents=True, exist_ok=True)
            LOGROS_FILE.write_text(json.dumps(saved), "utf-8")
        except OSError:
            pass
    return [{"id": i, "title": t, "desc": d, "date": saved.get(i)} for i, t, d in LOGROS], nuevos
