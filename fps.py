"""FPS reales: mide los fotogramas de tu juego con PresentMon (herramienta oficial gratuita de Intel) y calcula
FPS medios, 1 % low, 0,1 % low y latencia de fotogramas. Sirve para comprobar con números si un cambio ayudó.

PresentMon lee los eventos de Windows (ETW): no se mete dentro del juego ni toca su memoria.
Se descarga una sola vez de GitHub (versión fijada) y se comprueba su huella SHA256 antes de usarlo.
"""
import csv
import json
import math
import os
import random
import statistics
import subprocess
import threading
import time
import urllib.request
from pathlib import Path

import psutil

from util import APP_DIR, DEMO, IS_WIN

PM_VERSION = "2.5.1"
PM_URL = f"https://github.com/GameTechDev/PresentMon/releases/download/v{PM_VERSION}/PresentMon-{PM_VERSION}-x64.exe"
PM_SHA256 = "9bec3083069f58f911e6a512f4806db51a27bd096103087bc1d05ef54c80a191"
TOOLS = APP_DIR / "herramientas"
PM_EXE = TOOLS / f"PresentMon-{PM_VERSION}-x64.exe"
HISTORY = APP_DIR / ("fps_demo.json" if DEMO else "fps_runs.json")

KNOWN_GAMES = ["VALORANT-Win64-Shipping.exe", "FortniteClient-Win64-Shipping.exe", "League of Legends.exe", "cs2.exe", "javaw.exe",
               "eFootball.exe"]
_FT_COLS = ("MsBetweenPresents", "msBetweenPresents", "FrameTime", "frameTime")
_GPU_COLS = ("MsGPUBusy", "msGPUBusy", "GPUBusy")
_CPU_COLS = ("MsCPUBusy", "msCPUBusy", "CPUBusy")


class FpsError(Exception):
    pass


# --------------------------------------------------------------------------
# PresentMon
# --------------------------------------------------------------------------
def have_presentmon():
    return DEMO or PM_EXE.exists()


def ensure_presentmon(progress=lambda p, m: None):
    """Descarga PresentMon la primera vez y comprueba su huella. Devuelve la ruta."""
    if DEMO:
        return PM_EXE
    if PM_EXE.exists():
        import hashlib
        if hashlib.sha256(PM_EXE.read_bytes()).hexdigest() == PM_SHA256:
            return PM_EXE
        PM_EXE.unlink(missing_ok=True)           # alterado o dañado: se vuelve a bajar
    import hashlib
    TOOLS.mkdir(parents=True, exist_ok=True)
    tmp = PM_EXE.with_suffix(".part")
    h = hashlib.sha256()
    try:
        req = urllib.request.Request(PM_URL, headers={"User-Agent": "HellOP"})
        with urllib.request.urlopen(req, timeout=30) as r, open(tmp, "wb") as f:
            total = int(r.headers.get("Content-Length") or 0)
            got = 0
            while True:
                chunk = r.read(65536)
                if not chunk:
                    break
                f.write(chunk)
                h.update(chunk)
                got += len(chunk)
                if total:
                    progress(got / total, "Descargando PresentMon…")
    except Exception as e:  # noqa: BLE001
        tmp.unlink(missing_ok=True)
        raise FpsError(f"No pude descargar PresentMon ({e}). Revisa tu conexión o que GitHub no esté bloqueado.")
    if h.hexdigest() != PM_SHA256:
        tmp.unlink(missing_ok=True)
        raise FpsError("La descarga de PresentMon no coincide con su huella oficial. No lo instalo.")
    os.replace(tmp, PM_EXE)
    return PM_EXE


# --------------------------------------------------------------------------
# Elegir el juego
# --------------------------------------------------------------------------
def running_candidates():
    """Procesos .exe en marcha: primero los juegos conocidos, luego por memoria."""
    if DEMO:
        return ["VALORANT-Win64-Shipping.exe", "javaw.exe", "chrome.exe"]
    agg = {}
    for p in psutil.process_iter(["name", "memory_info"]):
        try:
            n = p.info["name"] or ""
            if n.lower().endswith(".exe"):
                agg[n] = agg.get(n, 0) + p.info["memory_info"].rss
        except (psutil.Error, OSError, AttributeError, TypeError):
            continue
    skip = {"svchost.exe", "system", "registry", "dwm.exe", "explorer.exe", "csrss.exe", "services.exe", "lsass.exe", "winlogon.exe",
            "fontdrvhost.exe", "conhost.exe", "searchhost.exe", "runtimebroker.exe", "sihost.exe", "ctfmon.exe", "hellop.exe", "python.exe",
            "presentmon-2.5.1-x64.exe", "audiodg.exe", "msmpeng.exe"}
    names = [n for n in agg if n.lower() not in skip]
    names.sort(key=lambda n: (n not in KNOWN_GAMES, -agg[n]))
    return names[:25]


# --------------------------------------------------------------------------
# Captura
# --------------------------------------------------------------------------
def _demo_frametimes(seconds, variant):
    rnd = random.Random(1000 + variant)
    base = 3.9 - 0.25 * variant                  # la segunda medición «mejora» un poco
    out, t = [], 0.0
    while t < seconds * 1000:
        ft = max(1.5, rnd.gauss(base, 0.35))
        if rnd.random() < 0.004 - 0.0015 * variant:
            ft *= rnd.uniform(3, 7)               # tirón
        out.append(ft)
        t += ft
    return out, [ft * 0.55 for ft in out], [ft * 0.6 for ft in out]


def capture(process, seconds, progress=lambda p, m: None, stop=None, variant=0):
    """Mide `seconds` s el proceso. Devuelve (frametimes_ms, gpu_busy_ms|None, cpu_busy_ms|None)."""
    stop = stop or threading.Event()
    if DEMO:
        for i in range(10):
            if stop.is_set():
                raise FpsError("Medición cancelada")
            progress((i + 1) / 10, "Midiendo (demo)…")
            time.sleep(0.15)
        return _demo_frametimes(seconds, variant)
    if not IS_WIN:
        raise FpsError("La medición de FPS solo funciona en Windows.")
    exe = ensure_presentmon(lambda p, m: progress(p * 0.0, m))
    out = APP_DIR / "fps_captura.csv"
    out.unlink(missing_ok=True)
    cmd = [str(exe), "--process_name", process, "--timed", str(int(seconds)), "--terminate_after_timed",
           "--output_file", str(out), "--no_console_stats"]
    p = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, creationflags=0x08000000)
    t0 = time.time()
    while p.poll() is None:
        if stop.is_set():
            p.terminate()
            raise FpsError("Medición cancelada")
        el = time.time() - t0
        progress(min(1.0, el / (seconds + 2)), f"Midiendo… {int(min(el, seconds))}/{int(seconds)} s")
        if el > seconds + 25:
            p.terminate()
            raise FpsError("PresentMon no terminó a tiempo.")
        time.sleep(0.3)
    err = (p.stderr.read() or b"").decode("utf-8", "replace").strip()[:300] if p.stderr else ""
    if not out.exists():
        raise FpsError("PresentMon no creó resultados." + (f" Dice: {err}" if err else " ¿Estás ejecutando HellOP como administrador?"))
    return _read_csv(out)


def _read_csv(path):
    ft, gpu, cpu = [], [], []
    with open(path, newline="", encoding="utf-8", errors="replace") as f:
        rd = csv.DictReader(f)
        cols = rd.fieldnames or []
        c_ft = next((c for c in _FT_COLS if c in cols), None)
        c_gpu = next((c for c in _GPU_COLS if c in cols), None)
        c_cpu = next((c for c in _CPU_COLS if c in cols), None)
        if not c_ft:
            raise FpsError("No reconozco el formato de PresentMon (falta la columna de tiempo entre fotogramas).")
        for row in rd:
            try:
                v = float(row[c_ft])
            except (TypeError, ValueError):
                continue
            if v <= 0:
                continue
            ft.append(v)
            for lst, c in ((gpu, c_gpu), (cpu, c_cpu)):
                try:
                    lst.append(float(row[c]) if c else None)
                except (TypeError, ValueError):
                    lst.append(None)
    if len(ft) < 60:
        raise FpsError("Casi no vi fotogramas. El juego debe estar abierto, visible en pantalla y con la partida en marcha "
                       "(y HellOP como administrador).")
    g = [x for x in gpu if x is not None]
    c = [x for x in cpu if x is not None]
    return ft, (g if len(g) == len(ft) else None), (c if len(c) == len(ft) else None)


# --------------------------------------------------------------------------
# Métricas
# --------------------------------------------------------------------------
def _low(ft, frac):
    """FPS «low»: media de los fotogramas más lentos (la fracción dada) pasada a FPS."""
    worst = sorted(ft, reverse=True)[:max(1, int(math.ceil(len(ft) * frac)))]
    return 1000.0 / statistics.mean(worst)


def analyze(ft, gpu=None, cpu=None):
    n = len(ft)
    mean = statistics.mean(ft)
    med = statistics.median(ft)
    s = sorted(ft)
    m = {
        "frames": n, "seconds": round(sum(ft) / 1000, 1),
        "avg": round(1000.0 / mean, 1), "low1": round(_low(ft, 0.01), 1), "low01": round(_low(ft, 0.001), 1),
        "ft_med": round(med, 2), "ft_p99": round(s[min(n - 1, int(n * 0.99))], 2), "ft_p999": round(s[min(n - 1, int(n * 0.999))], 2),
        "ft_max": round(s[-1], 1),
        "stutters": sum(1 for v in ft if v > max(2.5 * med, med + 8)),    # fotogramas mucho más lentos de lo normal
    }
    m["stutter_per_min"] = round(m["stutters"] / max(0.1, m["seconds"] / 60), 1)
    m["verdict"] = None
    if gpu and cpu:
        g, c = statistics.mean(gpu), statistics.mean(cpu)
        if g >= 0.9 * mean:
            m["verdict"] = "Tu gráfica va al límite: baja sombras/efectos o la resolución para ganar FPS."
        elif g <= 0.65 * mean:
            m["verdict"] = ("La gráfica va sobrada: lo que limita es el procesador (o el propio juego). Bajar gráficos casi no ayuda; "
                            "sí ayudan cerrar programas de fondo, RAM con XMP y la prioridad del juego.")
    if m["low1"] < 0.6 * m["avg"]:
        extra = "Tus FPS medios son buenos pero hay tirones marcados (el 1 % low es mucho más bajo que la media)."
        m["verdict"] = (m["verdict"] + " " if m["verdict"] else "") + extra
    return m


def compare(a, b):
    """(texto, color, deltas) entre la medición A (antes) y B (después)."""
    def d(k):
        return round((b[k] - a[k]) / a[k] * 100, 1) if a[k] else 0.0
    dl = {"avg": d("avg"), "low1": d("low1"), "low01": d("low01"), "stutters": b["stutters"] - a["stutters"]}
    better = dl["avg"] >= 4 or dl["low1"] >= 6
    worse = dl["avg"] <= -4 or dl["low1"] <= -6
    if better and not worse:
        return "MEJORA REAL: el cambio ayudó de forma medible.", "green", dl
    if worse and not better:
        return "EMPEORÓ: este cambio te quita rendimiento. Deshazlo desde el Historial.", "red", dl
    return ("SIN DIFERENCIA APRECIABLE: la variación entra en el margen de error (≈3-4 % entre mediciones iguales). "
            "Ese cambio no te ayuda en este juego."), "yellow", dl


# --------------------------------------------------------------------------
# Historial
# --------------------------------------------------------------------------
def load_history():
    try:
        return json.loads(HISTORY.read_text("utf-8"))
    except Exception:  # noqa: BLE001
        return []


def save_run(process, m, label=""):
    h = load_history()
    h.append({"ts": time.strftime("%Y-%m-%d %H:%M"), "process": process, "label": label,
              **{k: m[k] for k in ("avg", "low1", "low01", "stutters", "ft_p99", "ft_max", "seconds")}})
    HISTORY.write_text(json.dumps(h[-40:], ensure_ascii=False, indent=1), "utf-8")
