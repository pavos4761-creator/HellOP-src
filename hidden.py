"""Rendimiento oculto: busca los problemas que más FPS/fluidez cuestan de verdad y que casi nadie ve.

Cada hallazgo dice cuánto puede costar con honestidad (rangos de pruebas públicas, no promesas) y cómo arreglarlo.
Solo LEE, salvo la frecuencia del monitor, que se puede arreglar con un clic y se deshace desde el Historial.
"""
import ctypes
import re
import time

import psutil

import actions
from actions import Action
from util import DEMO, IS_WIN, as_list, fmt_gb, run_cmd, run_ps, run_ps_json

SEV = {"bad": 0, "warn": 1, "info": 2, "ok": 3}


# --------------------------------------------------------------------------
# Frecuencia del monitor (Windows) — de lo que más se nota
# --------------------------------------------------------------------------
if IS_WIN:
    class DEVMODEW(ctypes.Structure):
        _fields_ = [("dmDeviceName", ctypes.c_wchar * 32), ("dmSpecVersion", ctypes.c_uint16),
                    ("dmDriverVersion", ctypes.c_uint16), ("dmSize", ctypes.c_uint16), ("dmDriverExtra", ctypes.c_uint16),
                    ("dmFields", ctypes.c_uint32), ("dmPositionX", ctypes.c_int32), ("dmPositionY", ctypes.c_int32),
                    ("dmDisplayOrientation", ctypes.c_uint32), ("dmDisplayFixedOutput", ctypes.c_uint32),
                    ("dmColor", ctypes.c_int16), ("dmDuplex", ctypes.c_int16), ("dmYResolution", ctypes.c_int16),
                    ("dmTTOption", ctypes.c_int16), ("dmCollate", ctypes.c_int16), ("dmFormName", ctypes.c_wchar * 32),
                    ("dmLogPixels", ctypes.c_uint16), ("dmBitsPerPel", ctypes.c_uint32), ("dmPelsWidth", ctypes.c_uint32),
                    ("dmPelsHeight", ctypes.c_uint32), ("dmDisplayFlags", ctypes.c_uint32),
                    ("dmDisplayFrequency", ctypes.c_uint32), ("dmICMMethod", ctypes.c_uint32), ("dmICMIntent", ctypes.c_uint32),
                    ("dmMediaType", ctypes.c_uint32), ("dmDitherType", ctypes.c_uint32), ("dmReserved1", ctypes.c_uint32),
                    ("dmReserved2", ctypes.c_uint32), ("dmPanningWidth", ctypes.c_uint32), ("dmPanningHeight", ctypes.c_uint32)]

_ENUM_CURRENT = -1
_DM_FREQ = 0x400000
_CDS_UPDATEREGISTRY, _CDS_TEST = 0x1, 0x2


def _devmode(i=_ENUM_CURRENT):
    dm = DEVMODEW()
    dm.dmSize = ctypes.sizeof(DEVMODEW)
    return dm if ctypes.windll.user32.EnumDisplaySettingsW(None, i, ctypes.byref(dm)) else None


def display_info():
    """(ancho, alto, Hz_ahora, Hz_máximos_a_esa_resolución) del monitor principal, o None."""
    if DEMO:
        return 1920, 1080, 60, 280
    if not IS_WIN:
        return None
    cur = _devmode()
    if not cur:
        return None
    best, i = cur.dmDisplayFrequency, 0
    while True:
        dm = _devmode(i)
        if not dm:
            break
        i += 1
        if dm.dmPelsWidth == cur.dmPelsWidth and dm.dmPelsHeight == cur.dmPelsHeight and dm.dmBitsPerPel == cur.dmBitsPerPel:
            best = max(best, dm.dmDisplayFrequency)
        if i > 4000:
            break
    return cur.dmPelsWidth, cur.dmPelsHeight, cur.dmDisplayFrequency, best


def _set_hz(hz):
    dm = _devmode()
    if not dm:
        raise RuntimeError("No pude leer el modo del monitor")
    dm.dmDisplayFrequency = int(hz)
    dm.dmFields |= _DM_FREQ
    u = ctypes.windll.user32
    if u.ChangeDisplaySettingsExW(None, ctypes.byref(dm), None, _CDS_TEST, None) != 0:
        raise RuntimeError(f"Windows no acepta {hz} Hz con esta resolución (¿cable o puerto?)")
    if u.ChangeDisplaySettingsExW(None, ctypes.byref(dm), None, _CDS_UPDATEREGISTRY, None) != 0:
        raise RuntimeError("Windows no pudo cambiar la frecuencia")


class RefreshRateAction(Action):
    id, group = "refresh_rate", "gaming"
    reversible = True
    effect = "real"
    risk, reboot, needs_admin, profiles = "bajo", False, False, ("gaming",)

    def __init__(self, current, best):
        self.cur, self.best = current, best
        self.title = f"Poner el monitor a {best} Hz (ahora va a {current} Hz)"
        self.desc = ("Windows deja a veces el monitor a una frecuencia menor de la que soporta. Con más Hz ves el juego más fluido "
                     "y el ratón responde antes. Si la pantalla se queda en negro, espera 15 s: Windows vuelve solo.")

    def check(self):
        return f"Ahora {self.cur} Hz  →  {self.best} Hz" if self.best - self.cur >= 5 else None

    def apply(self):
        if DEMO:
            return {"prev": self.cur, "_msg": f"(Demo) monitor a {self.best} Hz"}
        _set_hz(self.best)
        return {"prev": self.cur, "_msg": f"Monitor a {self.best} Hz"}

    @classmethod
    def undo_data(cls, d):
        if not DEMO:
            _set_hz(d["prev"])


# --------------------------------------------------------------------------
# Otras lecturas
# --------------------------------------------------------------------------
def pcie_link():
    """(gen_actual, gen_max, ancho_actual, ancho_max, uso_gpu) de la gráfica NVIDIA, o None."""
    if DEMO:
        return 3, 3, 16, 16, 40
    from util import nvsmi
    exe = nvsmi()
    if not exe:
        return None
    rc, out, _ = run_cmd([exe, "--query-gpu=pcie.link.gen.current,pcie.link.gen.max,pcie.link.width.current,"
                                "pcie.link.width.max,utilization.gpu", "--format=csv,noheader,nounits"], timeout=15)
    try:
        return tuple(int(float(x)) for x in out.splitlines()[0].split(","))
    except (ValueError, IndexError):
        return None


def vbs_on():
    if DEMO:
        return True
    if not IS_WIN:
        return None
    out = run_ps("(Get-CimInstance -ClassName Win32_DeviceGuard -Namespace root\\Microsoft\\Windows\\DeviceGuard "
                 "-ErrorAction SilentlyContinue).VirtualizationBasedSecurityStatus")[1].strip()
    return None if not out else out == "2"


def games_on_hdd():
    """Nombres de juegos de Steam/Epic instalados en un disco duro mecánico."""
    import games
    if DEMO:
        return ["Cyberpunk 2077 (D:)"]
    found = []
    try:
        found = games.scan_steam() + games.scan_epic()
    except Exception:  # noqa: BLE001
        pass
    letters = sorted({(g.get("path") or "")[:1].upper() for g in found if (g.get("path") or "")[1:2] == ":"})
    if not letters or not IS_WIN:
        return []
    script = ("$r=@(); foreach($l in @(" + ",".join(f"'{x}'" for x in letters) + ")){ try{ $m=(Get-Partition -DriveLetter $l | Get-Disk | "
              "Get-PhysicalDisk).MediaType; $r += [pscustomobject]@{L=$l;M=[string]$m} }catch{} }; ConvertTo-Json -InputObject @($r) -Compress")
    media = {d["L"]: d["M"] for d in as_list(run_ps_json(script, timeout=40, default=[]))}
    hdd = {l for l, m in media.items() if m.upper() == "HDD"}
    return [f"{g['name']} ({g['path'][:2]})" for g in found if (g.get("path") or "")[:1].upper() in hdd]


def background_hogs():
    """[(nombre, cpu%, ram_bytes)] de lo que más gasta de fondo (sin sistema ni voz/streaming)."""
    import booster
    if DEMO:
        return [("chrome.exe", 6.0, 2.1 * 1024 ** 3), ("OneDrive.exe", 4.0, 0.3 * 1024 ** 3), ("wallpaper64.exe", 7.5, 0.6 * 1024 ** 3)]
    agg = {}
    procs = []
    for p in psutil.process_iter(["name", "memory_info"]):
        try:
            p.cpu_percent(None)
            procs.append(p)
        except (psutil.Error, OSError):
            pass
    time.sleep(1.5)
    n = psutil.cpu_count() or 1
    for p in procs:
        try:
            nm = (p.info["name"] or "")
            if not nm.lower().endswith(".exe") or nm.lower() in booster.NEVER_TOUCH:
                continue
            e = agg.setdefault(nm, [0.0, 0])
            e[0] += p.cpu_percent(None) / n
            e[1] += p.info["memory_info"].rss
        except (psutil.Error, OSError, AttributeError, TypeError):
            continue
    rows = [(k, v[0], v[1]) for k, v in agg.items() if v[0] >= 3 or v[1] >= 700 * 1024 ** 2]
    rows.sort(key=lambda r: -(r[1] * 20 + r[2] / 1024 ** 2 / 50))
    return rows[:6]


# --------------------------------------------------------------------------
# Informe
# --------------------------------------------------------------------------
def F(key, sev, title, impact, detail, fix=None):
    """fix = ('action', Action, 'texto del botón') | ('goto', 'pagina', 'texto del botón') | None"""
    return {"key": key, "sev": sev, "title": title, "impact": impact, "detail": detail, "fix": fix}


def scan(progress=lambda m: None):
    out = []

    progress("Mirando la frecuencia de tu monitor…")
    di = display_info()
    if di:
        w, h, cur, best = di
        if best - cur >= 5:
            out.append(F("hz", "bad", f"Tu monitor va a {cur} Hz y soporta {best} Hz", "MUY ALTO: es la mejora más visible de todas",
                         f"A {w}×{h} tu monitor puede dar {best} Hz pero Windows lo tiene en {cur} Hz. Si lo usas así, nunca verás más de "
                         f"{cur} imágenes por segundo aunque tu PC dé muchas más. Se arregla con un clic. Si no sale la opción en Windows, "
                         "revisa que uses un cable DisplayPort (o HDMI 2.1) y que el monitor tenga activada la frecuencia alta en su menú.",
                         ("action", RefreshRateAction(cur, best), f"Poner a {best} Hz")))
        else:
            out.append(F("hz", "ok", f"Monitor a {cur} Hz (su máximo a {w}×{h})", "", "Bien configurado en Windows. "
                         "Comprueba también que el juego use esa frecuencia en sus ajustes de vídeo."))

    progress("Mirando tu RAM…")
    try:
        import sysinfo
        ra = sysinfo.ram_advice(sysinfo.collect_hardware())
    except Exception:  # noqa: BLE001
        ra = None
    if ra:
        single = [n for n in ra["notes"] if "canal único" in n[1]]
        if single:
            out.append(F("channel", "bad", "Tu RAM está en canal único (1 solo módulo)", "ALTO: 10-25 % en juegos limitados por el procesador (Ryzen lo nota mucho)",
                         single[0][2] + " Es de lo que más FPS da por poco dinero: un segundo módulo igual al que tienes.",
                         ("goto", "analysis", "Ver mi RAM")))
        if ra["level"] == "warn":
            out.append(F("ramspeed", "bad", ra["headline"], "ALTO: 5-15 % en juegos limitados por el procesador",
                         "Tu memoria no está usando su perfil XMP/EXPO. Es un ajuste de BIOS de 2 minutos y no cuesta nada.",
                         ("goto", "bios", "Ver guía de BIOS")))
        elif ra["level"] == "info":
            out.append(F("ramspeed", "warn", ra["headline"], "MEDIO: hasta 5-10 % si tu kit es más rápido que la velocidad base",
                         "Si tu kit es más rápido de lo que muestra, falta activar su perfil en la BIOS.", ("goto", "bios", "Ver guía de BIOS")))
        else:
            out.append(F("ramspeed", "ok", ra["headline"], "", ""))

    progress("Mirando dónde están tus juegos…")
    hdd = games_on_hdd()
    if hdd:
        out.append(F("hdd", "bad", f"{len(hdd)} juego(s) instalados en un disco duro mecánico", "ALTO en juegos grandes: tirones al cargar texturas y pantallas de carga muy largas",
                     "Un HDD no sigue el ritmo de juegos de mundo abierto: ves tirones cuando entra terreno nuevo. Mueve esos juegos a un SSD "
                     "(en Steam: Propiedades → Instalados → Mover carpeta de instalación). Afectados: " + ", ".join(hdd[:5]) + ".", None))

    progress("Mirando VBS y el plan de energía…")
    v = vbs_on()
    if v:
        out.append(F("vbs", "warn", "VBS / Integridad de memoria está activo", "MEDIO: ≈4-5 % de media (hasta ~8 % en algún juego) en pruebas de Tom's Hardware",
                     "Windows 11 ejecuta tu sistema dentro de un mini-hipervisor de seguridad. Desactivarlo devuelve FPS pero baja la protección frente "
                     "a malware de bajo nivel. Está en Tweaks, nivel EXTREMO. Si juegas a algo con anti-cheat estricto, déjalo como está.",
                     ("goto", "tweaks", "Ir a Tweaks")))
    elif v is False:
        out.append(F("vbs", "ok", "VBS desactivado", "", ""))
    try:
        guid, name = actions.active_scheme()
        if guid and guid not in (actions.GUID_HIGH, actions.GUID_ULTIMATE) and not re.search(r"ultimate|m[aá]x|alto rendimiento|high perf", name or "", re.I) \
                and psutil.sensors_battery() is None:
            out.append(F("plan", "warn", f"Plan de energía: «{name}»", "BAJO-MEDIO: la CPU tarda en subir de frecuencia; se nota en mínimos y tirones",
                         "En un PC de sobremesa no tiene sentido ahorrar energía mientras juegas. Está en Tweaks, nivel SEGURO.",
                         ("goto", "tweaks", "Ir a Tweaks")))
    except Exception:  # noqa: BLE001
        pass

    progress("Mirando Resizable BAR y el enlace PCIe…")
    try:
        import bios
        fw = bios.firmware_status()
        if fw.get("rebar") is False:
            out.append(F("rebar", "info", "Resizable BAR desactivado", "BAJO-MEDIO: 0-10 % según el juego; en RTX serie 20 requiere vBIOS oficial",
                         "Permite a la CPU usar toda la memoria de la gráfica de una vez. En tu equipo puede no estar disponible. Mira la guía de BIOS.",
                         ("goto", "bios", "Ver guía de BIOS")))
        elif fw.get("rebar"):
            out.append(F("rebar", "ok", "Resizable BAR activado", "", ""))
    except Exception:  # noqa: BLE001
        pass
    pl = pcie_link()
    if pl:
        gen, gmax, wd, wmax, util = pl
        if wd < wmax and util >= 30:
            out.append(F("pcie", "bad", f"Tu gráfica va en PCIe x{wd} y soporta x{wmax}", "ALTO si es x4 o menos: puede restar 5-20 % de FPS",
                         "La gráfica no está usando todas sus líneas. Revisa que esté bien insertada en la ranura grande (la de arriba) y limpia los contactos.", None))
        elif wd < wmax:
            out.append(F("pcie", "info", f"Enlace PCIe x{wd} (soporta x{wmax})", "Informativo: en reposo baja solo para ahorrar energía",
                         "Para comprobarlo bien, ejecuta esto con un juego abierto (Alt+Tab).", None))
        else:
            out.append(F("pcie", "ok", f"Gráfica en PCIe x{wd} a pleno ancho", "", ""))

    progress("Midiendo qué gasta de fondo (2 s)…")
    hogs = background_hogs()
    if hogs:
        lines = ", ".join(f"{n} ({c:.0f} % CPU, {fmt_gb(r)})" for n, c, r in hogs[:4])
        out.append(F("bg", "warn", "Programas de fondo que gastan recursos", "BAJO-MEDIO: se nota en tirones, sobre todo con 8-16 GB de RAM o procesador justo",
                     "Cierra esto antes de jugar: " + lines + ". El Modo Extremo / modo automático los baja de prioridad por ti.",
                     ("goto", "booster", "Ir a Modo Extremo")))
    else:
        out.append(F("bg", "ok", "Sin programas pesados de fondo", "", ""))

    out.sort(key=lambda f: SEV[f["sev"]])
    return out
