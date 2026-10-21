"""Diagnóstico de juego: ¿qué te frena (CPU, GPU, RAM, disco, calor) y qué causa los tirones?

Se mide MIENTRAS juegas durante unos segundos y se analiza con reglas sencillas.
Nada de esto cambia ajustes: solo lee y te dice qué hacer.
"""
import json
import math
import random
import re
import statistics
import threading
import time

import psutil

from util import APP_DIR, DEMO, IS_WIN, nvsmi, run_cmd, run_ps, run_ps_json

HISTORY = APP_DIR / "diag_historial.json"

# bits de «clocks_throttle_reasons» que nos interesan (el 0x1 reposo y el 0x2 relojes fijados no son problema)
THROTTLE_BITS = {0x4: "límite de potencia (SW power cap)", 0x8: "freno por hardware (HW slowdown)",
                 0x20: "freno por temperatura (SW thermal)", 0x40: "freno por temperatura (HW thermal)",
                 0x80: "freno por energía (HW power brake)"}


# --------------------------------------------------------------------------
# Lecturas
# --------------------------------------------------------------------------
_PS_COUNTERS = r"""
$ErrorActionPreference='SilentlyContinue'
$n=%d; $out=@(); $sw=[Diagnostics.Stopwatch]::StartNew()
while($sw.Elapsed.TotalSeconds -lt $n){
  $d=Get-CimInstance Win32_PerfFormattedData_PerfDisk_PhysicalDisk -Filter "Name='_Total'"
  $m=Get-CimInstance Win32_PerfFormattedData_PerfOS_Memory
  $p=Get-CimInstance Win32_PerfFormattedData_Counters_ProcessorInformation -Filter "Name='_Total'"
  $out+=[pscustomobject]@{disk=[double]$d.PercentDiskTime;q=[double]$d.CurrentDiskQueueLength;pin=[double]$m.PagesInputPersec;
                          dpc=[double]$p.PercentDPCTime;irq=[double]$p.PercentInterruptTime}
  Start-Sleep -Milliseconds 500
}
ConvertTo-Json -InputObject @($out) -Compress
"""


def _gpu_sample():
    """Una lectura de la gráfica NVIDIA con nvidia-smi (None si no hay)."""
    exe = nvsmi()
    if not exe:
        return None
    base = "utilization.gpu,clocks.sm,clocks.max.sm,temperature.gpu,power.draw,power.limit"
    for reasons in ("clocks_throttle_reasons.active", "clocks_event_reasons.active"):
        rc, out, _ = run_cmd([exe, f"--query-gpu={base},{reasons}", "--format=csv,noheader,nounits"], timeout=5)
        if rc == 0 and out:
            break
    else:
        return None
    parts = [p.strip() for p in out.splitlines()[0].split(",")]
    if len(parts) < 7:
        return None

    def num(x):
        try:
            return float(x)
        except ValueError:
            return None
    try:
        mask = int(parts[6], 16)
    except ValueError:
        mask = 0
    return {"util": num(parts[0]), "clk": num(parts[1]), "clk_max": num(parts[2]), "temp": num(parts[3]),
            "pw": num(parts[4]), "pl": num(parts[5]), "mask": mask}


def _jitter_test(seconds, stop):
    """Pide dormir 1 ms muchas veces y mide cuánto tarda de más: son los «microparones» del sistema."""
    over = []
    winmm = None
    if IS_WIN:
        try:
            import ctypes
            winmm = ctypes.windll.winmm
            winmm.timeBeginPeriod(1)
        except Exception:  # noqa: BLE001
            winmm = None
    end = time.perf_counter() + seconds
    try:
        while time.perf_counter() < end and not stop.is_set():
            t0 = time.perf_counter()
            time.sleep(0.001)
            over.append((time.perf_counter() - t0) * 1000 - 1.0)
    finally:
        if winmm:
            try:
                winmm.timeEndPeriod(1)
            except Exception:  # noqa: BLE001
                pass
    return over


def _pct(values, p):
    if not values:
        return 0.0
    s = sorted(values)
    return s[min(len(s) - 1, int(math.ceil(p / 100 * len(s))) - 1)]


# --------------------------------------------------------------------------
# Medición
# --------------------------------------------------------------------------
def _demo_measure(seconds, progress):
    rnd = random.Random(7)
    n = max(8, seconds // 2)
    for i in range(n):
        progress(int(100 * i / n), f"Midiendo (demo)… {n - i} s")
        time.sleep(0.25)
    return {
        "seconds": seconds, "samples": n,
        "cpu_total": [38 + rnd.random() * 8 for _ in range(n)],
        "cpu_hot": [93 + rnd.random() * 6 for _ in range(n)],
        "ram": [67.0] * n,
        "gpu": [{"util": 58 + rnd.random() * 6, "clk": 1860, "clk_max": 1950, "temp": 71, "pw": 120, "pl": 170, "mask": 1} for _ in range(n)],
        "ctr": [{"disk": 6 + rnd.random() * 5, "q": 0.1, "pin": 4, "dpc": 0.6 + rnd.random() * 0.5, "irq": 0.3} for _ in range(n - 1)]
               + [{"disk": 8, "q": 0.1, "pin": 3, "dpc": 6.8, "irq": 0.4}],
        "jitter": [abs(rnd.gauss(0.08, 0.12)) for _ in range(900)] + [6.5, 9.0, 12.4, 7.1],
        "top": [("Juego.exe", 31.0), ("chrome.exe", 6.5), ("Discord.exe", 3.2), ("MsMpEng.exe", 2.4), ("OneDrive.exe", 1.1)],
    }


def measure(seconds, progress):
    """Mide `seconds` segundos. progress(pct, texto). Devuelve el diccionario de muestras."""
    if DEMO:
        return _demo_measure(seconds, progress)
    ncpu = psutil.cpu_count() or 1
    procs = {}
    for p in psutil.process_iter(["name"]):
        try:
            p.cpu_percent(None)
            procs[p.pid] = p
        except (psutil.Error, OSError):
            pass
    box = {}
    stop = threading.Event()

    def counters():
        res = run_ps_json(_PS_COUNTERS % seconds, timeout=seconds + 40, default=[])
        box["ctr"] = res if isinstance(res, list) else [res]

    def jitter():
        box["jitter"] = _jitter_test(seconds, stop)

    threads = [threading.Thread(target=counters, daemon=True), threading.Thread(target=jitter, daemon=True)]
    if IS_WIN:
        threads[0].start()
    threads[1].start()
    cpu_total, cpu_hot, ram, gpu = [], [], [], []
    psutil.cpu_percent(None, percpu=True)
    t0 = time.time()
    while time.time() - t0 < seconds:
        time.sleep(1.0)
        per = psutil.cpu_percent(None, percpu=True)
        if per:
            cpu_total.append(sum(per) / len(per))
            cpu_hot.append(max(per))
        ram.append(psutil.virtual_memory().percent)
        g = _gpu_sample()
        if g:
            gpu.append(g)
        left = max(0, int(seconds - (time.time() - t0)))
        progress(int(100 * (time.time() - t0) / seconds), f"Midiendo… {left} s")
    stop.set()
    for t in threads:
        t.join(timeout=45)
    top = []
    for pid, p in procs.items():
        try:
            c = p.cpu_percent(None) / ncpu
            nm = p.info.get("name") or "?"
            if c >= 0.5 and nm.lower() != "system idle process" and pid != 0:
                top.append((nm, round(c, 1)))
        except (psutil.Error, OSError):
            pass
    merged = {}
    for nm, c in top:
        merged[nm] = merged.get(nm, 0) + c
    top = sorted(merged.items(), key=lambda x: -x[1])[:6]
    return {"seconds": seconds, "samples": len(cpu_total), "cpu_total": cpu_total, "cpu_hot": cpu_hot, "ram": ram,
            "gpu": gpu, "ctr": box.get("ctr") or [], "jitter": box.get("jitter") or [], "top": top}


# --------------------------------------------------------------------------
# Análisis
# --------------------------------------------------------------------------
def _avg(v):
    v = [x for x in v if x is not None]
    return sum(v) / len(v) if v else 0.0


def analyze(m):
    """Devuelve {'bottleneck', 'color', 'headline', 'stats', 'findings', 'top', 'jitter'}.
    Cada hallazgo: (nivel, título, explicación, qué hacer). nivel: 'mal' | 'ojo' | 'bien' | 'info'."""
    gpu = m.get("gpu") or []
    ctr = m.get("ctr") or []
    cpu_t, cpu_h = _avg(m["cpu_total"]), _avg(m["cpu_hot"])
    cpu_h90 = _pct(m["cpu_hot"], 90)
    ram = _avg(m["ram"])
    gpu_u = _avg([g["util"] for g in gpu]) if gpu else None
    gtemp = max([g["temp"] for g in gpu if g["temp"] is not None], default=None)
    clk_ratio = None
    if gpu:
        cl = _avg([g["clk"] for g in gpu if g["clk"]])
        cm = max([g["clk_max"] for g in gpu if g["clk_max"]], default=0)
        clk_ratio = cl / cm if cm and cl else None
    mask_or = 0
    thr_samples = 0
    for g in gpu:
        bad = g["mask"] & sum(THROTTLE_BITS)
        if bad:
            thr_samples += 1
            mask_or |= bad
    disk, dq = _avg([c.get("disk") for c in ctr]), _avg([c.get("q") for c in ctr])
    pin = _avg([c.get("pin") for c in ctr])
    dpc, dpc_max = _avg([c.get("dpc") for c in ctr]), max([c.get("dpc") or 0 for c in ctr], default=0)
    jit = m.get("jitter") or []
    j99, jmax = _pct(jit, 99), max(jit, default=0)
    spikes = sum(1 for x in jit if x > 5)

    f = []
    bottleneck, color, headline = "Equilibrado", "bien", "No veo un cuello de botella claro"
    # ---- ¿se está jugando?
    idle = cpu_t < 15 and (gpu_u is None or gpu_u < 25)
    if idle:
        bottleneck, color, headline = "Sin datos de juego", "ojo", "No parece que estuvieras jugando durante la medición"
        f.append(("info", "No parece que estuvieras jugando",
                  f"Durante la medición la CPU estuvo al {cpu_t:.0f} % y la gráfica casi sin uso.",
                  "Repite la prueba: pulsa «Empezar», espera la cuenta atrás y vuelve a tu juego, con una partida en marcha."))

    # ---- cuello de botella principal
    if not idle:
        bottleneck, color, headline = "Equilibrado", "bien", "No veo un cuello de botella claro"
        if gpu_u is not None and gpu_u >= 93:
            bottleneck, color = "GPU", "bien"
            headline = "Tu gráfica va al límite: es el comportamiento ideal"
            f.append(("bien", f"La gráfica está al {gpu_u:.0f} %",
                      "Es lo normal y lo deseable: tu gráfica es lo que marca los FPS. Para ganar más hay que aligerar la carga gráfica o subir el rendimiento de la tarjeta.",
                      "Baja sombras, efectos y resolución de renderizado; activa DLSS/FSR si el juego lo tiene; mira la guía de overclock."))
        elif cpu_h90 >= 85 and (gpu_u is None or gpu_u < 90):
            bottleneck, color = "CPU (un solo hilo)", "mal"
            headline = "Un núcleo de tu procesador va al límite y frena la gráfica"
            f.append(("mal", f"Un núcleo al {cpu_h90:.0f} % mientras la CPU total está al {cpu_t:.0f} %"
                      + (f" y la gráfica al {gpu_u:.0f} %" if gpu_u is not None else ""),
                      "El juego depende de un hilo principal que ya no da más. La gráfica se queda esperando, por eso los FPS no suben aunque la tarjeta tenga potencia de sobra.",
                      "Activa XMP/EXPO en la BIOS, cierra programas de fondo, baja ajustes que usan CPU (distancia de visión, multitud, física) y aplica el perfil Extremo."))
        elif cpu_t >= 90:
            bottleneck, color = "CPU (toda)", "mal"
            headline = "Tu procesador está saturado"
            f.append(("mal", f"CPU total al {cpu_t:.0f} %", "Todos los núcleos están muy ocupados: el juego y otros programas se pelean por el procesador.",
                      "Cierra navegador, grabadores y apps de fondo; revisa la lista de programas que más CPU gastan abajo."))
        elif disk >= 80 or dq >= 2:
            bottleneck, color = "Disco", "mal"
            headline = "Tu disco está saturado"
        elif ram >= 92:
            bottleneck, color = "Memoria RAM", "mal"
            headline = "Te estás quedando sin RAM"
        else:
            f.append(("info", "Ni la CPU ni la gráfica están al límite",
                      f"CPU {cpu_t:.0f} %, núcleo más cargado {cpu_h:.0f} %" + (f", GPU {gpu_u:.0f} %" if gpu_u is not None else "") + ".",
                      "Puede que el juego tenga un límite de FPS, V-Sync activado, o que el cuello sea un tirón puntual. Revisa los resultados de tirones abajo."))

    # ---- RAM / disco
    if ram >= 90:
        f.append(("mal", f"RAM al {ram:.0f} %", "Cuando se llena la RAM Windows usa el disco y aparecen tirones fuertes.",
                  "Cierra Chrome y otros programas pesados; con 16 GB o menos plantéate ampliar."))
    if pin >= 200:
        f.append(("mal", f"Lecturas de disco por falta de RAM: {pin:.0f}/s", "Windows está leyendo del archivo de paginación en pleno juego.",
                  "Cierra programas y comprueba que el archivo de paginación está en un SSD y no desactivado."))
    if (disk >= 80 or dq >= 2) and bottleneck != "Disco":
        f.append(("ojo", f"Disco ocupado ({disk:.0f} %)", "Algo está usando mucho el disco mientras juegas (Windows Update, antivirus, un launcher).",
                  "Pausa descargas y actualizaciones, y usa un SSD para el juego."))
    elif bottleneck == "Disco":
        f.append(("mal", f"Disco al {disk:.0f} % con cola de {dq:.1f}", "El juego espera datos del disco: pantallas de carga y tirones al cruzar zonas.",
                  "Instala el juego en un SSD (mejor NVMe) y pausa lo que descargue en segundo plano."))

    # ---- temperatura / throttling
    if gpu:
        if mask_or & (0x20 | 0x40) or (gtemp is not None and gtemp >= 84):
            f.append(("mal", "Tu gráfica se calienta y baja de velocidad" + (f" ({gtemp:.0f} °C)" if gtemp else ""),
                      "Cuando se pasa de temperatura, la GPU reduce los relojes y pierdes FPS justo cuando más juegas.",
                      "Limpia el polvo, mejora el flujo de aire de la caja y sube la curva de ventiladores. Un undervolt también ayuda (guía de overclock)."))
        elif gtemp is not None and gtemp >= 78:
            f.append(("ojo", f"Gráfica a {gtemp:.0f} °C", "Está caliente pero aún no frena. Mejor vigilarlo.", "Mejora la ventilación de la caja."))
        elif gtemp is not None:
            f.append(("bien", f"Temperatura de la gráfica correcta ({gtemp:.0f} °C)", "No hay riesgo de freno por calor.", ""))
        if mask_or & 0x4:
            f.append(("ojo", "La gráfica choca con su límite de potencia",
                      f"En el {100 * thr_samples // max(1, len(gpu))} % de las lecturas estaba topada por vatios.",
                      "Es normal en juegos exigentes. Puedes subir el límite de potencia si tu modelo lo permite (Optimizar → Extremo)."))
        if clk_ratio is not None and gpu_u and gpu_u >= 90 and clk_ratio < 0.85:
            f.append(("ojo", f"Relojes de la gráfica al {100 * clk_ratio:.0f} % de su máximo", "Bajo carga alta, la GPU no mantiene sus relojes.",
                      "Revisa temperatura y límite de potencia; prueba el ajuste «relojes siempre altos» del perfil Extremo."))

    # ---- tirones
    if dpc_max >= 5 or dpc >= 2:
        sev = "mal" if (dpc >= 4 or dpc_max >= 10) else "ojo"
        f.append((sev, f"Carga de DPC alta (media {dpc:.1f} %, pico {dpc_max:.1f} %)",
                  "Los DPC son tareas de los drivers que interrumpen al juego. Si son altos, aparecen microparones en el audio, el ratón y los FPS. Suelen venir del driver de red, audio, USB o gráfica.",
                  "Actualiza los drivers de red, audio y chipset; prueba con cable de red en vez de WiFi; aplica «sin ahorro de energía en la tarjeta de red» del perfil Extremo."))
    else:
        f.append(("bien", f"Carga de DPC baja (media {dpc:.1f} %)", "Los drivers no están interrumpiendo al juego.", ""))
    if jit:
        if j99 > 4 or spikes >= 3:
            f.append(("mal" if j99 > 8 else "ojo", f"Picos de latencia del sistema: {spikes} de más de 5 ms (peor: {jmax:.1f} ms)",
                      "Pedí al sistema 1 ms de espera repetidas veces y tardó mucho más en varias. Eso son microparones reales, aunque la media de FPS sea buena.",
                      "Cierra programas de fondo, actualiza drivers, desactiva el antivirus en la carpeta del juego solo si confías en él y aplica el perfil Extremo."))
        else:
            f.append(("bien", f"Latencia del sistema estable (99 % de las esperas bajo {j99 + 1:.1f} ms)", "El sistema responde de forma constante, sin saltos.", ""))

    order = {"mal": 0, "ojo": 1, "info": 2, "bien": 3}
    f.sort(key=lambda x: order[x[0]])
    stats = [("CPU media / núcleo más cargado", f"{cpu_t:.0f} % / {cpu_h:.0f} %")]
    if gpu_u is not None:
        stats.append(("GPU", f"{gpu_u:.0f} % de uso" + (f" · {gtemp:.0f} °C" if gtemp is not None else "")
                      + (f" · reloj {100 * clk_ratio:.0f} % del máx." if clk_ratio else "")))
    else:
        stats.append(("GPU", "No pude leerla (solo se mide en gráficas NVIDIA con nvidia-smi)"))
    stats += [("RAM en uso", f"{ram:.0f} %"), ("Disco ocupado", f"{disk:.0f} %"),
              ("DPC / interrupciones", f"{dpc:.1f} % / {_avg([c.get('irq') for c in ctr]):.1f} %"),
              ("Latencia del sistema", f"percentil 99 = {j99:.2f} ms · peor = {jmax:.1f} ms")]
    return {"bottleneck": bottleneck, "color": color, "headline": headline, "stats": stats, "findings": f,
            "top": m.get("top") or [], "kpi": {"j99": round(j99, 2), "dpc": round(dpc, 2), "hot": round(cpu_h90, 1),
                                               "gpu": round(gpu_u, 1) if gpu_u is not None else None, "ts": time.strftime("%d/%m %H:%M")}}


# --------------------------------------------------------------------------
# Comprobaciones fijas de causas de tirones
# --------------------------------------------------------------------------
_PS_CHECKS = r"""
$ErrorActionPreference='SilentlyContinue'
$o=@{}
$cs=Get-CimInstance Win32_ComputerSystem
$o.autopf=[bool]$cs.AutomaticManagedPagefile
$o.pf=@(Get-CimInstance Win32_PageFileUsage | ForEach-Object { [pscustomobject]@{n=$_.Name;mb=[int]$_.AllocatedBaseSize} })
$since=(Get-Date).AddDays(-7)
$o.tdr=@(Get-WinEvent -FilterHashtable @{LogName='System';ProviderName='Display';Id=4101;StartTime=$since} -MaxEvents 50).Count
$o.whea=@(Get-WinEvent -FilterHashtable @{LogName='System';ProviderName='Microsoft-Windows-WHEA-Logger';StartTime=$since} -MaxEvents 50).Count
$o.dvr=(Get-ItemProperty 'HKCU:\System\GameConfigStore' -Name GameDVR_Enabled).GameDVR_Enabled
$o.cap=(Get-ItemProperty 'HKCU:\Software\Microsoft\Windows\CurrentVersion\GameDVR' -Name AppCaptureEnabled).AppCaptureEnabled
$o.plan=(powercfg /getactivescheme) -join ' '
ConvertTo-Json -InputObject $o -Compress -Depth 4
"""


def static_checks(ram_info=None):
    """Lista de (nivel, título, detalle, solución) con causas habituales de tirones."""
    out = []
    if DEMO:
        time.sleep(0.6)
        d = {"autopf": True, "pf": [{"n": "C:\\pagefile.sys", "mb": 4096}], "tdr": 0, "whea": 0, "dvr": 1, "cap": 0,
             "plan": "GUID: 381b4222 (Equilibrado)"}
    else:
        d = run_ps_json(_PS_CHECKS, timeout=60, default={}) or {}
    if not d:
        return out
    if not d.get("pf"):
        out.append(("mal", "No hay archivo de paginación", "Sin él, muchos juegos se cierran o dan tirones fuertes cuando falta RAM.",
                    "Windows → Rendimiento → Memoria virtual: déjalo en «Administrar automáticamente»."))
    if d.get("tdr"):
        out.append(("mal", f"El driver de la gráfica se reinició {d['tdr']} veces esta semana", "Son los «TDR»: la pantalla parpadea o el juego se cierra porque la gráfica dejó de responder.",
                    "Reinstala el driver con DDU, quita overclocks y revisa la temperatura."))
    if d.get("whea"):
        out.append(("mal", f"{d['whea']} errores de hardware (WHEA) esta semana", "Windows registró fallos físicos del procesador, la RAM o el bus. Suele ser inestabilidad por overclock o XMP.",
                    "Quita overclocks, prueba la RAM sin XMP unos días y actualiza la BIOS."))
    if d.get("dvr") == 1 or d.get("cap") == 1:
        out.append(("ojo", "La grabación de fondo de Xbox Game Bar está activa", "Graba o prepara clips mientras juegas y gasta GPU y disco.",
                    "Configuración → Juegos → Capturas: desactiva «Grabar en segundo plano»."))
    plan = (d.get("plan") or "").lower()
    if plan and not re.search(r"alto rendimiento|high performance|ultimate|máximo|maximo|rendimiento|hellop|ryzen", plan):
        out.append(("ojo", "El plan de energía no es de alto rendimiento", "El plan equilibrado deja bajar la frecuencia de la CPU entre cargas, y eso causa tirones.",
                    "Optimizar → Gaming: aplica el plan de máximo rendimiento."))
    if ram_info and ram_info.get("running") and ram_info.get("kit") and ram_info["running"] + 100 < ram_info["kit"]:
        out.append(("mal", f"Tu RAM va a {ram_info['running']} MHz y tu kit puede dar {ram_info['kit']} MHz",
                    "Sin XMP/EXPO activado pierdes FPS (sobre todo en Ryzen) y tienes peores mínimos.", "Pestaña BIOS: activa XMP/EXPO."))
    if not out:
        out.append(("bien", "No encontré causas habituales de tirones", "Paginación, errores de hardware, grabación de fondo y plan de energía están bien.", ""))
    return out


# --------------------------------------------------------------------------
# Historial (para comparar con la medición anterior)
# --------------------------------------------------------------------------
def load_history():
    try:
        return json.loads(HISTORY.read_text("utf-8"))
    except Exception:  # noqa: BLE001
        return []


def save_run(kpi):
    h = load_history()[-9:] + [kpi]
    try:
        HISTORY.write_text(json.dumps(h), "utf-8")
    except OSError:
        pass
    return h
