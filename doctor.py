"""Doctor de síntomas: eliges qué te pasa y HellOP mira TU PC (temperaturas, latencia de drivers, errores de Windows, batería, RAM…)
y te dice las causas más probables, ordenadas, con su arreglo. No inventa: cada causa sale de un dato leído en tu equipo."""
import re
import time
from concurrent.futures import ThreadPoolExecutor

import psutil

from util import DEMO, IS_WIN, as_list, run_cmd, run_ps_json

SINTOMAS = [   # (clave, icono, título, descripción)
    ("tirones", "≋", "Tirones o microcortes", "Va bien y de repente se para un instante."),
    ("fps", "▤", "FPS bajos", "Va fluido pero a pocas imágenes por segundo."),
    ("cierra", "✖", "Se cierra o se reinicia", "El juego se cae, Windows se reinicia o sale pantalla azul."),
    ("audio", "♪", "Audio con crujidos", "Chasquidos, cortes o zumbidos al jugar."),
    ("input", "⌖", "Retraso al pulsar", "El ratón, teclado o mando responden tarde."),
    ("lento", "◔", "Todo va lento", "Windows tarda en abrir cosas aunque no juegues."),
]
NOMBRES = {k: t for k, _i, t, _d in SINTOMAS}
OVERLAYS = {"gameoverlayui.exe": "Steam", "discordoverlay.exe": "Discord", "rtss.exe": "RivaTuner (MSI Afterburner)", "msiafterburner.exe": "MSI Afterburner",
            "wallpaper32.exe": "Wallpaper Engine", "wallpaper64.exe": "Wallpaper Engine", "gamebarpresencewriter.exe": "Xbox Game Bar",
            "nvidia overlay.exe": "Overlay de NVIDIA", "nvcontainer.exe": "NVIDIA (ShadowPlay)"}

DEMO_HECHOS = {"temps": [{"label": "CPU · Package", "value": 91.0, "kind": "cpu", "level": "bad"}, {"label": "GPU", "value": 72.0, "kind": "gpu", "level": "ok"}],
               "dpc": {"dpc": 9.4, "int": 2.1, "max": 17.0}, "ev": {"app": ["chrome.exe", "Game.exe", "Game.exe", "Game.exe"], "bsod": 0, "kp": 1, "tdr": 2},
               "pend": True, "bateria": None, "ram": 91.0, "libre": 12.0, "overlays": ["Discord", "Steam", "Wallpaper Engine"],
               "gpus": 1, "driver_dias": 410, "findings": [
                   {"key": "hz", "sev": "bad", "title": "Tu monitor va a 60 Hz y soporta 280 Hz", "fix": ("goto", "tweaks", "Ir a Tweaks")},
                   {"key": "ramspeed", "sev": "bad", "title": "Tu RAM va a 2133 MHz y tu kit es capaz de 3200 MHz", "fix": ("goto", "bios", "Ver guía de BIOS")},
                   {"key": "hdd", "sev": "bad", "title": "1 juego(s) instalados en un disco duro mecánico", "fix": None},
                   {"key": "bg", "sev": "warn", "title": "Programas de fondo que gastan recursos: chrome.exe (22 % CPU)", "fix": ("goto", "booster", "Ir a Modo Extremo")},
                   {"key": "plan", "sev": "warn", "title": "Plan de energía: «Equilibrado»", "fix": ("goto", "tweaks", "Ir a Tweaks")}]}


# --------------------------------------------------------------------------- lectura de datos
def _dpc():
    if not IS_WIN:
        return None
    rc, o, _ = run_cmd(["typeperf", r"\Processor(_Total)\% DPC Time", r"\Processor(_Total)\% Interrupt Time", "-sc", "6"], timeout=40)
    d, i = [], []
    for ln in o.splitlines():
        p = [x.strip().strip('"').replace(",", ".") for x in re.split(r'","', ln.strip())]
        if len(p) >= 3:
            try:
                d.append(float(p[1]))
                i.append(float(p[2]))
            except ValueError:
                continue
    return {"dpc": sum(d) / len(d), "int": sum(i) / len(i), "max": max(d)} if d else None


def _eventos():
    ps = ("$ini=(Get-Date).AddDays(-7); "
          "$app=@(Get-WinEvent -FilterHashtable @{LogName='Application';Id=1000;StartTime=$ini} -MaxEvents 60 -ErrorAction SilentlyContinue | ForEach-Object { [string]$_.Properties[0].Value }); "
          "$bsod=@(Get-WinEvent -FilterHashtable @{LogName='System';Id=1001;StartTime=$ini} -MaxEvents 20 -ErrorAction SilentlyContinue).Count; "
          "$kp=@(Get-WinEvent -FilterHashtable @{LogName='System';Id=41;StartTime=$ini} -MaxEvents 20 -ErrorAction SilentlyContinue).Count; "
          "$tdr=@(Get-WinEvent -FilterHashtable @{LogName='System';Id=4101;StartTime=$ini} -MaxEvents 20 -ErrorAction SilentlyContinue).Count; "
          "ConvertTo-Json -Compress -InputObject @{app=$app;bsod=$bsod;kp=$kp;tdr=$tdr}")
    d = run_ps_json(ps, timeout=50, default=None)
    if isinstance(d, dict):
        d["app"] = [str(x) for x in as_list(d.get("app"))]
        return d
    return None


def _reinicio_pendiente():
    if not IS_WIN:
        return False
    ps = ("(Test-Path 'HKLM:\\SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\Component Based Servicing\\RebootPending') -or "
          "(Test-Path 'HKLM:\\SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\WindowsUpdate\\Auto Update\\RebootRequired')")
    from util import run_ps
    return run_ps(ps, timeout=20)[1].strip().lower() == "true"


def recoger():
    """Lee todo lo necesario de una vez (en paralelo). Tarda unos 10-15 s."""
    if DEMO:
        time.sleep(1.4)
        return dict(DEMO_HECHOS)
    import hidden
    import sysinfo
    h = {}
    with ThreadPoolExecutor(max_workers=4) as ex:
        f_scan, f_temp = ex.submit(hidden.scan), ex.submit(sysinfo.read_temps)
        f_dpc, f_ev, f_pend = ex.submit(_dpc), ex.submit(_eventos), ex.submit(_reinicio_pendiente)
        h["findings"] = [f for f in (f_scan.result() or [])]
        for fn, k in ((f_temp, "temps"), (f_dpc, "dpc"), (f_ev, "ev"), (f_pend, "pend")):
            try:
                h[k] = fn.result()
            except Exception:  # noqa: BLE001
                h[k] = None
    bat = psutil.sensors_battery()
    h["bateria"] = None if bat is None else {"enchufado": bool(bat.power_plugged), "pct": bat.percent}
    h["ram"] = psutil.virtual_memory().percent
    try:
        import sysinfo
        vols = [(f / t * 100) for _m, f, t in sysinfo.volumes() if t]
        h["libre"] = min(vols) if vols else None
        hw = sysinfo.collect_hardware()
        gp = as_list(hw.get("gpu"))
        h["gpus"] = len(gp)
        fecha = (gp[0].get("DriverDate") or "")[:10] if gp else ""
        h["driver_dias"] = int((time.time() - time.mktime(time.strptime(fecha, "%Y-%m-%d"))) / 86400) if fecha else None
    except Exception:  # noqa: BLE001
        h["libre"], h["gpus"], h["driver_dias"] = None, 1, None
    try:
        nombres = {(p.info["name"] or "").lower() for p in psutil.process_iter(["name"])}
        h["overlays"] = sorted({v for k, v in OVERLAYS.items() if k in nombres})
    except Exception:  # noqa: BLE001
        h["overlays"] = []
    return h


# --------------------------------------------------------------------------- razonamiento (puro: se puede probar con datos de ejemplo)
def _c(sev, pesos, titulo, detalle, fix=None):
    return {"sev": sev, "pesos": pesos, "titulo": titulo, "detalle": detalle, "fix": fix}


def causas(h):
    out = []
    F = {f["key"]: f for f in h.get("findings") or []}
    # batería
    b = h.get("bateria")
    if b and not b["enchufado"]:
        out.append(_c("bad", {"fps": 5, "tirones": 4, "lento": 4, "input": 2}, "Estás con el portátil sin enchufar",
                      "Con batería Windows limita CPU y gráfica a propósito. Enchúfalo al cargador y pon el plan de energía en «Alto rendimiento»: es la causa nº 1 de FPS bajos en portátiles."))
    # temperaturas
    t = [x for x in h.get("temps") or [] if isinstance(x, dict) and x.get("kind") in ("cpu", "gpu")]
    cal = [x for x in t if x["value"] >= 88]
    if cal:
        n = ", ".join(f"{x['label']} {x['value']:.0f} °C" for x in cal[:2])
        out.append(_c("bad", {"fps": 4, "tirones": 4, "cierra": 4, "lento": 3}, f"Está pasando calor: {n}",
                      "Por encima de ~88 °C la pieza baja su velocidad para no quemarse (se llama throttling) y se nota como tirones y FPS bajos; si sigue subiendo, el PC puede apagarse. "
                      "Limpia el polvo, revisa que los ventiladores giren y que la pasta térmica no esté seca. De momento, el Modo noche baja el calor.", ("goto", "noche", "Abrir Modo noche")))
    # latencia de drivers
    d = h.get("dpc")
    if d and (d["dpc"] >= 5 or d["max"] >= 15):
        out.append(_c("bad", {"tirones": 5, "audio": 5, "input": 3}, f"Tus drivers pierden mucho tiempo (latencia DPC {d['dpc']:.1f} %, pico {d['max']:.0f} %)",
                      "Cuando un driver (red, audio, USB, gráfica) acapara la CPU, el audio crepita y el juego da microtirones. Lo normal es menos de un 2-3 %. "
                      "Culpables habituales: driver de Wi-Fi o Bluetooth, tarjeta de sonido y un driver de gráfica reciente con fallo. Prueba a actualizar o a volver a una versión anterior de ese driver.",
                      ("goto", "diag", "Medir mientras juego")))
    # eventos
    ev = h.get("ev") or {}
    if ev.get("bsod") or ev.get("kp"):
        n = (ev.get("bsod") or 0) + (ev.get("kp") or 0)
        out.append(_c("bad", {"cierra": 5}, f"Windows se apagó o se reinició solo {n} vez/veces esta semana",
                      "Eso suele ser fuente de alimentación justa, temperatura, RAM con perfil XMP inestable o un driver. Si empezó tras activar un perfil de memoria o un overclock, desactívalo en la BIOS.", ("goto", "bios", "Ver guía de BIOS")))
    if ev.get("tdr"):
        out.append(_c("bad", {"cierra": 4, "tirones": 3}, f"El driver de la gráfica se cayó y se recuperó {ev['tdr']} vez/veces",
                      "Windows lo llama TDR. Casi siempre: gráfica demasiado exigida, overclock inestable, driver con fallos o temperatura. Quita el overclock, prueba otro driver y vigila la temperatura.", ("goto", "health", "Salud del PC")))
    apps = ev.get("app") or []
    if apps:
        top = max(set(apps), key=apps.count)
        if apps.count(top) >= 2:
            out.append(_c("warn", {"cierra": 4}, f"«{top}» se ha cerrado con error {apps.count(top)} veces esta semana",
                          "Si es tu juego: verifica los archivos desde Steam/Epic, actualiza el driver de la gráfica y desactiva overlays (Discord, Steam, Afterburner). "
                          "Si cae en varios juegos, mira la temperatura y la RAM."))
    # reinicio pendiente
    if h.get("pend"):
        out.append(_c("warn", {"lento": 3, "tirones": 2, "cierra": 2}, "Windows tiene un reinicio pendiente",
                      "Hay actualizaciones a medio instalar. Hasta que reinicies, Windows puede estar trabajando en segundo plano y algunos drivers no están cargados bien. Reinicia cuando puedas."))
    # RAM y disco
    if h.get("ram") and h["ram"] >= 85:
        out.append(_c("warn", {"tirones": 3, "fps": 2, "lento": 4}, f"La RAM está al {h['ram']:.0f} %",
                      "Con la memoria casi llena, Windows tira de disco y se nota en tirones y lentitud. Cierra navegadores con muchas pestañas y programas de fondo.", ("goto", "booster", "Ir a Modo Extremo")))
    if h.get("libre") is not None and h["libre"] < 12:
        out.append(_c("warn", {"lento": 3, "tirones": 2, "cierra": 1}, f"Un disco tiene solo {h['libre']:.0f} % libre",
                      "Un disco casi lleno va más lento y Windows no tiene sitio para archivos temporales ni memoria virtual. Libera espacio.", ("goto", "clean", "Ir a Limpieza")))
    # hallazgos del análisis
    if "bg" in F and F["bg"]["sev"] != "ok":
        out.append(_c("warn", {"fps": 3, "tirones": 4, "lento": 4}, F["bg"]["title"], "Estos programas gastan CPU y RAM mientras juegas. Ciérralos antes de jugar o usa el Modo Extremo para que se pausen solos.", F["bg"].get("fix")))
    if "hz" in F and F["hz"]["sev"] == "bad":
        out.append(_c("bad", {"fps": 3, "tirones": 2, "input": 4}, F["hz"]["title"], "A 60 Hz no verás más de 60 imágenes por segundo y el retraso es mayor. Es lo más visible y se arregla en Windows.", F["hz"].get("fix")))
    if "ramspeed" in F and F["ramspeed"]["sev"] in ("bad", "warn"):
        out.append(_c("warn", {"fps": 3, "tirones": 2}, F["ramspeed"]["title"], "Tu memoria no usa su perfil XMP/EXPO. Activarlo en la BIOS da fluidez gratis, sobre todo en procesadores Ryzen.", F["ramspeed"].get("fix")))
    if "hdd" in F:
        out.append(_c("bad", {"tirones": 4, "lento": 3, "fps": 1}, F["hdd"]["title"], "Los juegos grandes en un disco mecánico dan tirones al cargar texturas. Muévelos a un SSD.", None))
    if "plan" in F and F["plan"]["sev"] != "ok":
        out.append(_c("warn", {"fps": 2, "tirones": 3, "input": 3, "lento": 2}, F["plan"]["title"], "La CPU tarda en subir de velocidad con este plan y se nota en mínimos y tirones. Cámbialo en Tweaks.", F["plan"].get("fix")))
    if "channel" in F:
        out.append(_c("warn", {"fps": 4, "tirones": 2}, F["channel"]["title"], "Con un solo módulo, la memoria va a la mitad de ancho de banda. Un segundo módulo igual da FPS en muchos juegos.", F["channel"].get("fix")))
    if "vbs" in F and F["vbs"]["sev"] == "warn":
        out.append(_c("info", {"fps": 2, "tirones": 1}, F["vbs"]["title"], "Aislamiento de memoria: pierde unos pocos % de FPS. Ojo: algunos anti-cheat lo piden activado.", F["vbs"].get("fix")))
    # overlays
    ov = h.get("overlays") or []
    if len(ov) >= 2:
        out.append(_c("warn", {"tirones": 3, "input": 3, "fps": 2, "cierra": 2}, "Hay varios overlays activos: " + ", ".join(ov),
                      "Cada overlay engancha el juego para dibujar encima. Dos o más a la vez se pisan: tirones, retraso y a veces cierres. Deja solo el que uses."))
    # driver viejo / portátil con dos gráficas
    if h.get("driver_dias") and h["driver_dias"] > 365:
        out.append(_c("info", {"fps": 2, "cierra": 2, "tirones": 1}, f"El driver de tu gráfica tiene {h['driver_dias'] // 30} meses",
                      "Los juegos nuevos suelen traer mejoras en drivers recientes. Actualízalo desde la web del fabricante (NVIDIA, AMD o Intel)."))
    if h.get("gpus", 1) >= 2 and h.get("bateria") is not None:
        out.append(_c("warn", {"fps": 4, "tirones": 2}, "Tu portátil tiene dos gráficas",
                      "Si el juego arranca con la integrada irá a 20-30 FPS. En Configuración > Sistema > Pantalla > Gráficos, pon el juego en «Alto rendimiento»."))
    # audio
    out.append(_c("info", {"audio": 2}, "Formato de audio y «mejoras» de Windows",
                  "En Configuración > Sonido > tu dispositivo > Propiedades: apaga «Mejorar audio» y pon el formato en 24 bits 48000 Hz. Un formato distinto al del juego obliga a convertir y puede crepitar."))
    out.append(_c("info", {"audio": 2}, "Auriculares o altavoces por Bluetooth o USB",
                  "El Bluetooth usa un códec básico y comparte radio con el Wi-Fi: cortes y chasquidos. Prueba por cable. Si es USB, que no vaya por un hub y revisa el ahorro de energía USB (Mando lo apaga).", ("goto", "mando", "Abrir Mando")))
    # retraso al pulsar
    out.append(_c("info", {"input": 3}, "Mando o ratón: ahorro de energía y capas de más",
                  "El ahorro de energía de USB/Bluetooth y los overlays añaden retraso. Hay un apartado entero para ello.", ("goto", "mando", "Abrir Mando")))
    return out


def para(sintoma, lista):
    """Las causas que importan para ese síntoma, de la más a la menos probable."""
    rel = [(c["pesos"][sintoma] + (2 if c["sev"] == "bad" else 1 if c["sev"] == "warn" else 0), c) for c in lista if sintoma in c["pesos"]]
    rel.sort(key=lambda x: -x[0])
    return [c for _p, c in rel][:6]
