"""Test de rendimiento antes/después con medidas reales."""
import hashlib
import json
import os
import random
import socket
import statistics
import tempfile
import time

import psutil

from util import APP_DIR, DEMO, IS_WIN, run_ps

BENCH_FILE = APP_DIR / ("rendimiento_demo.json" if DEMO else "rendimiento.json")

# clave, nombre, unidad, ¿menos es mejor?
METRICS = [
    ("boot_s", "Último arranque de Windows", "s", True),
    ("cpu_ms", "Velocidad de CPU (tarea fija)", "ms", True),
    ("ram_mbs", "Velocidad de memoria RAM", "MB/s", False),
    ("disk_mbs", "Escritura en disco", "MB/s", False),
    ("files_ms", "Crear y borrar 200 archivos pequeños", "ms", True),
    ("idle_cpu", "Uso de CPU en reposo", "%", True),
    ("ram_used", "RAM en uso", "%", True),
    ("procs", "Procesos en marcha", "", True),
    ("services", "Servicios en ejecución", "", True),
    ("startup", "Programas de inicio activos", "", True),
    ("dns_ms", "Respuesta del DNS", "ms", True),
    ("ping_ms", "Latencia a Internet (1.1.1.1)", "ms", True),
]
LABELS = {k: (n, u, lower) for k, n, u, lower in METRICS}


def _cpu():
    best = 1e9
    blob = b"x" * (1024 * 1024)
    for _ in range(5):
        t = time.perf_counter()
        x = 0
        for i in range(1_200_000):
            x = (x * 31 + i) % 1000003
        h = hashlib.sha256()
        for _ in range(30):
            h.update(blob)
        best = min(best, (time.perf_counter() - t) * 1000)
    return best


def _ram():
    size = 96 * 1024 * 1024
    src = bytearray(size)
    dst = bytearray(size)
    best = 1e9
    for _ in range(5):
        t = time.perf_counter()
        dst[:] = src
        best = min(best, time.perf_counter() - t)
    del src, dst
    return (size / 1024 / 1024) / best


def _disk():
    path = os.path.join(tempfile.gettempdir(), "pcopt_bench.tmp")
    chunk = os.urandom(4 * 1024 * 1024)
    total = 128 * 1024 * 1024
    try:
        t = time.perf_counter()
        with open(path, "wb") as f:
            for _ in range(total // len(chunk)):
                f.write(chunk)
            f.flush()
            os.fsync(f.fileno())
        dt = time.perf_counter() - t
        mbs = (total / 1024 / 1024) / dt
    finally:
        try:
            os.remove(path)
        except OSError:
            pass
    d = tempfile.mkdtemp(prefix="pcopt_")
    t = time.perf_counter()
    for i in range(200):
        with open(os.path.join(d, f"f{i}.tmp"), "wb") as f:
            f.write(b"0" * 4096)
    for i in range(200):
        os.remove(os.path.join(d, f"f{i}.tmp"))
    files_ms = (time.perf_counter() - t) * 1000
    try:
        os.rmdir(d)
    except OSError:
        pass
    return mbs, files_ms


def _ping():
    vals = []
    for _ in range(5):
        try:
            t = time.perf_counter()
            s = socket.create_connection(("1.1.1.1", 443), timeout=1.5)
            vals.append((time.perf_counter() - t) * 1000)
            s.close()
        except OSError:
            pass
    return statistics.median(vals) if vals else None


def _boot_seconds():
    if not IS_WIN:
        return None
    script = ("$e = Get-WinEvent -FilterHashtable @{LogName='Microsoft-Windows-Diagnostics-Performance/Operational';Id=100} "
              "-MaxEvents 1 -ErrorAction SilentlyContinue; if($e){ $x=[xml]$e.ToXml(); "
              "($x.Event.EventData.Data | Where-Object Name -eq 'BootTime').'#text' }")
    rc, out, _ = run_ps(script, timeout=30)
    try:
        return int(out.strip()) / 1000
    except ValueError:
        return None


def _services_running():
    try:
        return sum(1 for s in psutil.win_service_iter() if s.status() == "running")
    except Exception:  # noqa: BLE001
        return None


def run_benchmark(progress=lambda pct, msg: None, improved=False):
    """Ejecuta el test (≈ 15-20 s). `improved` solo se usa en modo demo."""
    if DEMO:
        return _demo(progress, improved)
    import actions
    res = {}
    progress(3, "Midiendo CPU…")
    res["cpu_ms"] = _cpu()
    progress(25, "Midiendo memoria RAM…")
    res["ram_mbs"] = _ram()
    progress(40, "Midiendo disco…")
    res["disk_mbs"], res["files_ms"] = _disk()
    progress(65, "Midiendo reposo (2 s sin tocar nada)…")
    res["idle_cpu"] = psutil.cpu_percent(interval=2.0)
    res["ram_used"] = psutil.virtual_memory().percent
    res["procs"] = len(psutil.pids())
    res["services"] = _services_running()
    res["startup"] = actions.count_enabled_startup()
    progress(80, "Midiendo red…")
    res["dns_ms"] = actions.measure_current_dns()
    res["ping_ms"] = _ping()
    progress(95, "Leyendo tiempo de arranque…")
    res["boot_s"] = _boot_seconds()
    progress(100, "Listo")
    return {k: (round(v, 2) if isinstance(v, float) else v) for k, v in res.items()}


def _demo(progress, improved):
    for i, msg in enumerate(["Midiendo CPU…", "Midiendo memoria RAM…", "Midiendo disco…", "Midiendo reposo…", "Midiendo red…"]):
        progress(10 + i * 20, msg)
        time.sleep(0.35)
    progress(100, "Listo")
    base = {"boot_s": 38.2, "cpu_ms": 612.0, "ram_mbs": 7420.0, "disk_mbs": 910.0, "files_ms": 148.0, "idle_cpu": 6.4,
            "ram_used": 61.0, "procs": 214, "services": 118, "startup": 17, "dns_ms": 31.0, "ping_ms": 19.0}
    if not improved:
        return {k: round(v * random.uniform(0.99, 1.01), 2) if k not in ("procs", "services", "startup") else v
                for k, v in base.items()}
    gain = {"boot_s": 0.97, "cpu_ms": 0.93, "ram_mbs": 1.34, "disk_mbs": 1.04, "files_ms": 0.82, "idle_cpu": 0.45,
            "ram_used": 0.78, "procs": 0.83, "services": 0.86, "startup": 0.47, "dns_ms": 0.3, "ping_ms": 0.97}
    return {k: round(v * gain[k] * random.uniform(0.99, 1.01), 2) if k not in ("procs", "services", "startup")
            else int(round(v * gain[k])) for k, v in base.items()}


# --------------------------------------------------------------------------
# Instantáneas y comparación
# --------------------------------------------------------------------------
def load_snaps():
    try:
        return json.loads(BENCH_FILE.read_text("utf-8"))
    except Exception:  # noqa: BLE001
        return {}


def save_snap(kind, metrics):
    snaps = load_snaps()
    snaps[kind] = {"ts": time.strftime("%Y-%m-%d %H:%M"), "metrics": metrics}
    BENCH_FILE.write_text(json.dumps(snaps, ensure_ascii=False, indent=1), "utf-8")


def fmt_val(key, v):
    if v is None:
        return "—"
    unit = LABELS[key][1]
    if isinstance(v, float):
        v = f"{v:,.0f}".replace(",", ".") if v >= 100 else f"{v:.1f}"
    return f"{v} {unit}".strip()


def compare(before, after):
    """Filas: nombre, antes, después, mejora % (positivo = mejor) y estado."""
    rows = []
    for key, name, _u, lower in METRICS:
        b = (before or {}).get(key)
        a = (after or {}).get(key)
        pct, state = None, "na"
        if b not in (None, 0) and a is not None:
            raw = (b - a) / b * 100 if lower else (a - b) / b * 100
            pct = raw
            state = "better" if raw >= 3 else "worse" if raw <= -3 else "same"
        rows.append({"key": key, "name": name, "before": fmt_val(key, b), "after": fmt_val(key, a), "pct": pct, "state": state})
    return rows
