"""Modo noche: de madrugada baja el consumo y el ruido de tu PC y lo deja todo como estaba al terminar el horario.

Qué hace de verdad (nada de magia):
  • Limita el máximo del procesador en tu plan de energía (p. ej. al 80 %): menos calor y ventiladores más lentos. Se nota sobre todo en la CPU.
  • En gráficas NVIDIA, baja el límite de potencia (con nvidia-smi; necesita administrador).
  • Guarda los valores originales en un archivo y los devuelve al acabar el horario, al pulsar «Restaurar» o al cerrar HellOP.
Solo funciona mientras HellOP está abierto (puede estar minimizado).
"""
import json
import re
import time

from mando import _indice
from util import APP_DIR, DEMO, IS_WIN, nvsmi, run_cmd

ARCHIVO = APP_DIR / ("noche_demo.json" if DEMO else "noche.json")
CPU_SUB, CPU_SET = "54533251-82be-4824-96c1-47b60b740d00", "bc5038f7-23e0-4960-96da-33abaf5935ec"      # máximo del procesador
NIVELES = {"suave": 90, "medio": 80, "fuerte": 70}
DEFECTO = {"activo_horario": False, "ini": "23:00", "fin": "08:00", "nivel": "medio", "aplicado": None}


def cargar():
    try:
        d = json.loads(ARCHIVO.read_text("utf-8"))
        return {**DEFECTO, **d}
    except Exception:  # noqa: BLE001
        return dict(DEFECTO)


def guardar(d):
    try:
        APP_DIR.mkdir(parents=True, exist_ok=True)
        ARCHIVO.write_text(json.dumps(d), "utf-8")
    except OSError:
        pass


def _min(hhmm):
    m = re.fullmatch(r"\s*(\d{1,2}):(\d{2})\s*", hhmm or "")
    if not m or int(m.group(1)) > 23 or int(m.group(2)) > 59:
        return None
    return int(m.group(1)) * 60 + int(m.group(2))


def hora_valida(hhmm):
    return _min(hhmm) is not None


def en_horario(ini, fin, ahora=None):
    a, b = _min(ini), _min(fin)
    if a is None or b is None or a == b:
        return False
    t = ahora if ahora is not None else time.localtime().tm_hour * 60 + time.localtime().tm_min
    return a <= t < b if a < b else (t >= a or t < b)       # el horario puede cruzar la medianoche


def _gpu():
    exe = nvsmi()
    if not exe:
        return None
    rc, o, _ = run_cmd([exe, "--query-gpu=power.limit,power.default_limit,power.min_limit", "--format=csv,noheader,nounits"], timeout=10)
    try:
        act, dfl, mn = (float(x.strip()) for x in o.splitlines()[0].split(","))
        return {"exe": exe, "actual": act, "defecto": dfl, "min": mn}
    except Exception:  # noqa: BLE001
        return None


def aplicar(nivel="medio"):
    """Devuelve (texto de lo hecho, lista de avisos)."""
    d = cargar()
    if d.get("aplicado"):
        return "Ya estaba activo", []
    pct = NIVELES.get(nivel, 80)
    hecho, avisos, guard = [], [], {}
    if DEMO:
        d["aplicado"] = {"demo": True}
        guardar(d)
        return f"(Demo) procesador al {pct} %, gráfica al {pct} %", []
    if IS_WIN:
        guard["cpu"] = [_indice(CPU_SUB, CPU_SET, True), _indice(CPU_SUB, CPU_SET, False)]
        for modo in ("setacvalueindex", "setdcvalueindex"):
            run_cmd(["powercfg", f"/{modo}", "SCHEME_CURRENT", CPU_SUB, CPU_SET, str(pct)], timeout=15)
        run_cmd(["powercfg", "/setactive", "SCHEME_CURRENT"], timeout=15)
        hecho.append(f"procesador al {pct} %")
    g = _gpu()
    if g:
        objetivo = max(g["min"], round(g["defecto"] * pct / 100))
        rc, _o, err = run_cmd([g["exe"], "-pl", str(int(objetivo))], timeout=15)
        if rc == 0:
            guard["gpu"] = {"exe": g["exe"], "antes": g["actual"]}
            hecho.append(f"gráfica a {int(objetivo)} W")
        else:
            avisos.append("No pude bajar la potencia de la gráfica (hace falta ejecutar HellOP como administrador).")
    d["aplicado"] = guard
    guardar(d)
    return ", ".join(hecho) or "nada que ajustar", avisos


def restaurar():
    d = cargar()
    g = d.get("aplicado")
    if not g:
        return False
    if not DEMO:
        cpu = g.get("cpu")
        if cpu:
            for modo, v in zip(("setacvalueindex", "setdcvalueindex"), cpu):
                run_cmd(["powercfg", f"/{modo}", "SCHEME_CURRENT", CPU_SUB, CPU_SET, str(v if v is not None else 100)], timeout=15)
            run_cmd(["powercfg", "/setactive", "SCHEME_CURRENT"], timeout=15)
        gp = g.get("gpu")
        if gp:
            run_cmd([gp["exe"], "-pl", str(int(gp["antes"]))], timeout=15)
    d["aplicado"] = None
    guardar(d)
    return True


def revisa():
    """Se llama cada minuto: aplica o restaura según el horario. Devuelve un aviso (texto) si cambió algo."""
    d = cargar()
    if not d["activo_horario"]:
        return None
    dentro = en_horario(d["ini"], d["fin"])
    if dentro and not d["aplicado"]:
        txt, avisos = aplicar(d["nivel"])
        return "Modo noche activado: " + txt + (" · " + avisos[0] if avisos else "")
    if not dentro and d["aplicado"]:
        restaurar()
        return "Modo noche terminado: todo vuelve a como estaba"
    return None
