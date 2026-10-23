"""Salud del PC: temperaturas, drivers y red. Solo lee: no cambia nada."""
import re
import socket
import statistics
import subprocess
import time
from datetime import datetime

from util import DEMO, IS_WIN, as_list, nvsmi, run_ps_json

_NO_WINDOW = 0x08000000 if IS_WIN else 0


# --------------------------------------------------------------------------
# Temperaturas
# --------------------------------------------------------------------------
def gpu_temps():
    """Datos de la gráfica NVIDIA con nvidia-smi, o None."""
    if DEMO:
        return {"name": "NVIDIA GeForce RTX 2060 SUPER", "temp": 74, "fan": 61, "clock": 1815, "max_clock": 2100,
                "power": 148, "util": 97}
    exe = nvsmi()
    if not exe:
        return None
    q = "name,temperature.gpu,fan.speed,clocks.sm,clocks.max.sm,power.draw,utilization.gpu"
    try:
        out = subprocess.run([exe, f"--query-gpu={q}", "--format=csv,noheader,nounits"], capture_output=True, timeout=10,
                             creationflags=_NO_WINDOW).stdout.decode("utf-8", "replace").strip().splitlines()[0]
        p = [x.strip() for x in out.split(",")]

        def num(s):
            try:
                return float(s)
            except ValueError:
                return None
        return {"name": p[0], "temp": num(p[1]), "fan": num(p[2]), "clock": num(p[3]), "max_clock": num(p[4]),
                "power": num(p[5]), "util": num(p[6])}
    except Exception:  # noqa: BLE001
        return None


def cpu_temp():
    """Temperatura de CPU en °C si Windows la da (muchas placas no la exponen), o None."""
    if DEMO:
        return 68.0
    if not IS_WIN:
        return None
    data = run_ps_json("ConvertTo-Json -InputObject @(Get-CimInstance -Namespace root/wmi -ClassName MSAcpi_ThermalZoneTemperature "
                       "-ErrorAction SilentlyContinue | Select-Object -ExpandProperty CurrentTemperature) -Compress",
                       timeout=20, default=[])
    vals = [(v / 10.0) - 273.15 for v in as_list(data) if isinstance(v, (int, float))]
    vals = [v for v in vals if 10 < v < 120]
    return max(vals) if vals else None


def temp_report():
    """Devuelve (filas, consejos). Cada fila: (título, valor, estado) con estado green/yellow/red/muted."""
    rows, tips = [], []
    g = gpu_temps()
    if g and g.get("temp") is not None:
        t = g["temp"]
        st = "green" if t < 72 else "yellow" if t < 83 else "red"
        rows.append(("Gráfica (temperatura)", f"{t:.0f} °C", st))
        if g.get("fan") is not None:
            rows.append(("Ventiladores de la gráfica", f"{g['fan']:.0f} %", "muted"))
        if g.get("clock") and g.get("max_clock"):
            ratio = g["clock"] / g["max_clock"]
            rows.append(("Velocidad de la gráfica", f"{g['clock']:.0f} MHz de {g['max_clock']:.0f} MHz",
                         "green" if ratio > 0.85 or (g.get("util") or 0) < 50 else "yellow"))
        if st == "red":
            tips.append("Tu gráfica pasa de 83 °C: probablemente baja su velocidad por calor y pierdes FPS. Limpia el polvo "
                        "de los ventiladores, mejora la entrada de aire de la caja y valora cambiar la pasta térmica.")
        elif st == "yellow":
            tips.append("Tu gráfica está caliente (72-83 °C). Es normal jugando, pero si pasa de 80 limpia el polvo y revisa "
                        "que los ventiladores de la caja saquen el aire caliente.")
        else:
            tips.append("La temperatura de tu gráfica es buena. Mide de nuevo mientras juegas: en reposo siempre sale más baja.")
    else:
        rows.append(("Gráfica", "No se puede leer (solo funciona con NVIDIA)", "muted"))
    c = cpu_temp()
    if c is not None:
        st = "green" if c < 75 else "yellow" if c < 88 else "red"
        rows.append(("Procesador (temperatura)", f"{c:.0f} °C", st))
        if st == "red":
            tips.append("Tu procesador está muy caliente: el disipador puede estar sucio o mal puesto. Limpia el polvo y "
                        "revisa la pasta térmica; si no, sube de frecuencia a mitad de partida y baja de golpe (tirones).")
    else:
        rows.append(("Procesador (temperatura)", "Windows no la da en tu equipo", "muted"))
        tips.append("Windows no deja leer la temperatura del procesador sin un driver externo. Para verla, "
                    "usa HWiNFO (gratis) mientras juegas.")
    tips.append("Cada 6-12 meses: sopla el polvo (con la PC apagada) y comprueba que todos los ventiladores giran. "
                "Una PC con calor pierde más FPS que cualquier ajuste de Windows.")
    return rows, tips


# --------------------------------------------------------------------------
# Drivers
# --------------------------------------------------------------------------
LINKS = {
    "NVIDIA": "https://www.nvidia.com/Download/index.aspx",
    "AMD": "https://www.amd.com/en/support",
    "Intel": "https://www.intel.com/content/www/us/en/download-center/home.html",
}


def _nvidia_version(raw):
    """31.0.15.5123 -> 551.23"""
    parts = re.findall(r"\d+", raw or "")
    if len(parts) >= 4:
        digits = (parts[-2] + parts[-1]).zfill(5)[-5:]
        return f"{int(digits[:3])}.{digits[3:]}"
    return raw


def _age_days(dt):
    try:
        return (datetime.now() - datetime.fromisoformat(dt[:10])).days
    except Exception:  # noqa: BLE001
        return None


def driver_report():
    """Lista de dicts: nombre, tipo, version, fecha, dias, estado, vendor."""
    if DEMO:
        return [
            {"kind": "Gráfica", "name": "NVIDIA GeForce RTX 2060 SUPER", "version": "551.23", "date": "2024-02-23", "days": 970,
             "vendor": "NVIDIA"},
            {"kind": "Red", "name": "Realtek PCIe GbE Family Controller", "version": "10.62.0714.2022", "date": "2022-07-14",
             "days": 1560, "vendor": "Realtek"},
            {"kind": "Sonido", "name": "Realtek High Definition Audio", "version": "6.0.9361.1", "date": "2025-09-02",
             "days": 50, "vendor": "Realtek"},
        ]
    if not IS_WIN:
        return []
    script = r"""
$r = @()
Get-CimInstance Win32_VideoController | ForEach-Object { $r += [pscustomobject]@{Kind='Gráfica';Name=[string]$_.Name;Ver=[string]$_.DriverVersion;Date=if($_.DriverDate){$_.DriverDate.ToString('yyyy-MM-dd')}else{''}} }
Get-CimInstance Win32_PnPSignedDriver | Where-Object { $_.DeviceClass -in 'NET','MEDIA' -and $_.DeviceName -and $_.DriverDate -and $_.DeviceName -notmatch 'Virtual|Miniport|WAN|Bluetooth|Hyper-V|VPN|TAP|Loopback' } |
  ForEach-Object { $r += [pscustomobject]@{Kind=$(if($_.DeviceClass -eq 'NET'){'Red'}else{'Sonido'});Name=[string]$_.DeviceName;Ver=[string]$_.DriverVersion;Date=$_.DriverDate.ToString('yyyy-MM-dd')} }
ConvertTo-Json -InputObject $r -Depth 3 -Compress
"""
    out, seen = [], set()
    for d in as_list(run_ps_json(script, timeout=60, default=[])):
        name = str(d.get("Name", ""))
        if name in seen or not name:
            continue
        seen.add(name)
        low = name.lower()
        vendor = "NVIDIA" if "nvidia" in low else "AMD" if ("amd" in low or "radeon" in low) else \
            "Intel" if "intel" in low else "Realtek" if "realtek" in low else ""
        ver = d.get("Ver", "")
        if vendor == "NVIDIA" and d.get("Kind") == "Gráfica":
            ver = _nvidia_version(ver)
        out.append({"kind": d.get("Kind", ""), "name": name, "version": ver, "date": d.get("Date", ""),
                    "days": _age_days(d.get("Date", "")), "vendor": vendor})
    return out


def driver_state(item):
    """('green'|'yellow'|'red', texto) según la antigüedad del driver."""
    d = item.get("days")
    if d is None:
        return "muted", "Fecha desconocida"
    limit_ok, limit_old = (120, 270) if item["kind"] == "Gráfica" else (540, 1100)
    if d <= limit_ok:
        return "green", f"Reciente ({_human(d)})"
    if d <= limit_old:
        return "yellow", f"Con {_human(d)}: mira si hay uno nuevo"
    return "red", f"Antiguo ({_human(d)}): conviene actualizarlo"


def _human(days):
    if days < 60:
        return f"{days} días"
    if days < 700:
        return f"{round(days / 30)} meses"
    return f"{days / 365:.1f} años"


# --------------------------------------------------------------------------
# Red
# --------------------------------------------------------------------------
PING_HOSTS = [("Cloudflare", "1.1.1.1", 443), ("Google", "8.8.8.8", 443), ("Quad9", "9.9.9.9", 443)]


def _tcp_ms(host, port, timeout=1.5):
    t = time.perf_counter()
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return (time.perf_counter() - t) * 1000
    except OSError:
        return None


def ping_report(rounds=10, progress=None):
    """Mide la conexión con tres servidores. Devuelve lista de dicts y un veredicto."""
    if DEMO:
        rows = [{"name": "Cloudflare", "avg": 14.0, "jitter": 2.1, "loss": 0}, {"name": "Google", "avg": 17.0, "jitter": 3.0, "loss": 0},
                {"name": "Quad9", "avg": 22.0, "jitter": 9.5, "loss": 10}]
    else:
        rows = []
        for n, (name, host, port) in enumerate(PING_HOSTS):
            vals = []
            for _ in range(rounds):
                v = _tcp_ms(host, port)
                if v is not None:
                    vals.append(v)
                time.sleep(0.05)
            if progress:
                progress((n + 1) / len(PING_HOSTS))
            rows.append({"name": name, "avg": statistics.mean(vals) if vals else None,
                         "jitter": statistics.pstdev(vals) if len(vals) > 1 else 0.0,
                         "loss": round(100 * (rounds - len(vals)) / rounds)})
    ok = [r for r in rows if r["avg"] is not None]
    if not ok:
        return rows, ("red", "Sin conexión: no he podido llegar a ningún servidor.")
    avg = statistics.mean(r["avg"] for r in ok)
    jit = max(r["jitter"] for r in ok)
    loss = max(r["loss"] for r in rows)
    if loss >= 10 or jit > 15 or avg > 80:
        return rows, ("red", "Tu conexión tiene problemas: pérdida de paquetes o saltos de ping. Prueba con cable en vez de Wi-Fi, "
                             "reinicia el router y cierra descargas en segundo plano.")
    if jit > 6 or avg > 40:
        return rows, ("yellow", "Conexión aceptable pero no perfecta. Con cable de red (en vez de Wi-Fi) suele bajar el ping y la variación.")
    return rows, ("green", "Tu conexión va muy bien para jugar online.")
