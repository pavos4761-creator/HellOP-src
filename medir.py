"""Mediciones REALES del sistema (antes/después de optimizar) y limpieza de la memoria en caché («standby»).

Nada aquí inventa números: cada valor sale de Windows. En el modo demo devuelve datos de ejemplo."""
import ctypes
import statistics
import time

import psutil

from util import DEMO, IS_WIN

_PAG = 4096


def _privilegio():
    """Activa SeProfileSingleProcessPrivilege (hace falta ser administrador)."""
    old = ctypes.c_ubyte()
    return ctypes.WinDLL("ntdll").RtlAdjustPrivilege(20, True, False, ctypes.byref(old)) == 0


def standby_mb():
    """MB de memoria en caché reutilizable (lista standby) o None."""
    if DEMO:
        return 5200.0
    if not IS_WIN:
        return None
    try:
        buf = (ctypes.c_size_t * 40)()
        r = ctypes.WinDLL("ntdll").NtQuerySystemInformation(0x50, buf, ctypes.sizeof(buf), None)
        if r != 0:
            return None
        # ZeroPage, FreePage, ModifiedPage, ModifiedNoReserve, BadPage, luego PageCountByPriority[8]
        return sum(buf[5:13]) * _PAG / 1024 ** 2
    except Exception:  # noqa: BLE001
        return None


def purgar_standby(solo_baja_prioridad=True):
    """Vacía la caché de memoria. Devuelve MB liberados, o None si no se pudo (sin administrador)."""
    antes = standby_mb()
    if DEMO:
        return antes
    if not IS_WIN or antes is None:
        return None
    try:
        if not _privilegio():
            return None
        cmd = ctypes.c_int(5 if solo_baja_prioridad else 4)   # 5 = solo prioridad baja, 4 = toda
        if ctypes.WinDLL("ntdll").NtSetSystemInformation(0x50, ctypes.byref(cmd), 4) != 0:
            return None
    except Exception:  # noqa: BLE001
        return None
    despues = standby_mb()
    return max(0.0, antes - (despues or 0))


def sleep_jitter(n=120):
    """Cuánto se pasa Windows al dormir 1 ms: mide la precisión del reloj (15 ms por defecto, ~1 ms si está afinado)."""
    if DEMO:
        return 14.9, 16.1
    xs = []
    for _ in range(n):
        t = time.perf_counter()
        time.sleep(0.001)
        xs.append((time.perf_counter() - t) * 1000)
    xs.sort()
    return statistics.mean(xs), xs[int(len(xs) * 0.99) - 1]


def instantanea():
    """Foto del sistema ahora mismo. Claves: ram, libre, procs, standby, cpu, sleep, p99."""
    s = standby_mb()
    vm = psutil.virtual_memory()
    d = {"ram": vm.used / 1024 ** 3, "libre": vm.available / 1024 ** 3, "procs": len(psutil.pids()), "standby": s,
         "cpu": psutil.cpu_percent(interval=0.6)}
    d["sleep"], d["p99"] = sleep_jitter()
    return d


FILAS = [   # clave, título, unidad, formato, «menos es mejor»
    ("sleep", "Precisión del reloj (dormir 1 ms)", "ms", "{:.1f}", True),
    ("p99", "Peor caso del reloj (1 % más lento)", "ms", "{:.1f}", True),
    ("procs", "Procesos en marcha", "", "{:.0f}", True),
    ("ram", "RAM en uso", "GB", "{:.1f}", True),
    ("cpu", "CPU en reposo", "%", "{:.0f}", True),
    ("standby", "Memoria en caché (standby)", "MB", "{:.0f}", False),
]


def comparar(antes, despues):
    """Lista de (título, antes, después, unidad, veredicto) con veredicto mejor/igual/peor."""
    out = []
    for k, t, u, fmt, menos in FILAS:
        a, b = antes.get(k), despues.get(k)
        if a is None or b is None:
            continue
        tol = max(abs(a) * 0.05, 0.05)
        v = "igual" if abs(b - a) <= tol else ("mejor" if (b < a) == menos else "peor")
        if k == "standby":
            v = "igual" if abs(b - a) <= 200 else ("mejor" if b < a else "igual")
        out.append((t, fmt.format(a), fmt.format(b), u, v))
    return out
