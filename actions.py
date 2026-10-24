"""Optimizaciones. Cada acción:
  · se detecta antes (check) y solo se ofrece si tiene sentido en tu PC,
  · se aplica solo si tú dices que sí (apply),
  · guarda cómo deshacerla (historial) para poder volver atrás (undo_data).
"""
import concurrent.futures as cf
import fnmatch
import json
import os
import random
import re
import socket
import struct
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import psutil

from util import (APP_DIR, DEMO, IS_WIN, fmt_bytes, is_admin, ps_quote, run_cmd,
                  run_ps, run_ps_json, as_list)

if IS_WIN:
    import winreg
    HIVES = {"HKCU": winreg.HKEY_CURRENT_USER, "HKLM": winreg.HKEY_LOCAL_MACHINE}
    REG_SZ, REG_DWORD, REG_BINARY = winreg.REG_SZ, winreg.REG_DWORD, winreg.REG_BINARY
    _VIEW = winreg.KEY_WOW64_64KEY
else:
    HIVES = {}
    REG_SZ, REG_DWORD, REG_BINARY = 1, 4, 3
    _VIEW = 0

LOG_FILE = APP_DIR / ("historial_demo.json" if DEMO else "historial.json")

GROUPS = [
    ("power", "Energía"),
    ("speed", "Respuesta del sistema"),
    ("gaming", "Juegos"),
    ("latency", "Latencia extrema (núcleo, energía y registro)"),
    ("gpu", "Gráfica y procesador (ajustes específicos)"),
    ("deep", "Limpieza profunda de Windows"),
    ("tradeoff", "Rendimiento a cambio de seguridad"),
    ("startup", "Programas de inicio"),
    ("services", "Servicios de Windows"),
    ("bloat", "Apps innecesarias"),
    ("procs", "Procesos pesados en segundo plano"),
    ("network", "Red"),
]
GROUP_NAMES = dict(GROUPS)


# --------------------------------------------------------------------------
# Registro de Windows
# --------------------------------------------------------------------------
def reg_read(hive, path, name):
    if not IS_WIN:
        return None
    try:
        with winreg.OpenKey(HIVES[hive], path, 0, winreg.KEY_READ | _VIEW) as k:
            return winreg.QueryValueEx(k, name)
    except OSError:
        return None


def reg_write(hive, path, name, value, typ):
    with winreg.CreateKeyEx(HIVES[hive], path, 0, winreg.KEY_SET_VALUE | _VIEW) as k:
        winreg.SetValueEx(k, name, 0, typ, value)


def reg_delete(hive, path, name):
    try:
        with winreg.OpenKey(HIVES[hive], path, 0, winreg.KEY_SET_VALUE | _VIEW) as k:
            winreg.DeleteValue(k, name)
    except OSError:
        pass


def reg_values(hive, path):
    out = []
    try:
        with winreg.OpenKey(HIVES[hive], path, 0, winreg.KEY_READ | _VIEW) as k:
            i = 0
            while True:
                try:
                    out.append(winreg.EnumValue(k, i))
                except OSError:
                    break
                i += 1
    except OSError:
        pass
    return out


def _norm(v):
    if isinstance(v, int):
        return v & 0xFFFFFFFF
    return str(v)


# --------------------------------------------------------------------------
# Base y registro de acciones (para poder deshacer desde el historial)
# --------------------------------------------------------------------------
REGISTRY = {}


@dataclass
class Result:
    ok: bool
    msg: str = ""


class Action:
    id = ""
    group = ""
    title = ""
    desc = ""
    needs_admin = False
    reversible = True
    risk = "bajo"            # bajo | medio | alto
    reboot = False           # necesita reiniciar / cerrar sesión
    profiles = ("gaming", "work")
    effect = ""              # real | pequeño | depende | mínimo  (honestidad sobre el efecto)
    warning = ""             # texto rojo extra para ajustes delicados

    def __init_subclass__(cls, **kw):
        super().__init_subclass__(**kw)
        REGISTRY[cls.__name__] = cls

    def check(self) -> Optional[str]:
        """None = no aplica / ya está hecho. Texto = estado actual a mostrar."""
        return ""

    def apply(self) -> dict:
        raise NotImplementedError

    @classmethod
    def undo_data(cls, data):
        raise NotImplementedError


# --------------------------------------------------------------------------
# Historial y deshacer
# --------------------------------------------------------------------------
def load_log():
    try:
        return json.loads(LOG_FILE.read_text("utf-8"))
    except Exception:  # noqa: BLE001
        return []


def save_log(entries):
    LOG_FILE.write_text(json.dumps(entries, ensure_ascii=False, indent=1), "utf-8")


def log_action(action, data):
    entries = load_log()
    entries.append({"id": int(time.time() * 1000) + random.randint(0, 999),
                    "ts": time.strftime("%Y-%m-%d %H:%M:%S"),
                    "cls": type(action).__name__, "title": action.title,
                    "reversible": action.reversible, "reboot": action.reboot,
                    "data": data, "undone": False})
    save_log(entries)


def execute(action) -> Result:
    try:
        if action.needs_admin and not is_admin():
            return Result(False, "Necesita ejecutar la app como administrador")
        data = action.apply() or {}
        msg = data.pop("_msg", "Hecho")
        log_action(action, data)
        return Result(True, msg)
    except Exception as e:  # noqa: BLE001
        return Result(False, f"{type(e).__name__}: {e}")


def _load_registry():
    """Asegura que las clases de acciones extremas estén registradas para poder deshacerlas."""
    try:
        import extreme  # noqa: F401
        import gameprofiles  # noqa: F401
        import hidden  # noqa: F401
    except Exception:  # noqa: BLE001
        pass


def undo_entry(entry_id) -> Result:
    _load_registry()
    entries = load_log()
    for e in entries:
        if e["id"] == entry_id and not e["undone"] and e["reversible"]:
            try:
                REGISTRY[e["cls"]].undo_data(e["data"])
            except Exception as ex:  # noqa: BLE001
                return Result(False, f"{type(ex).__name__}: {ex}")
            e["undone"] = True
            save_log(entries)
            return Result(True, "Deshecho")
    return Result(False, "No se puede deshacer")


def undo_all():
    done = fail = 0
    for e in reversed(load_log()):
        if e["reversible"] and not e["undone"]:
            r = undo_entry(e["id"])
            done += r.ok
            fail += (not r.ok)
    return done, fail


# --------------------------------------------------------------------------
# Punto de restauración
# --------------------------------------------------------------------------
_SR_KEY = r"SOFTWARE\Microsoft\Windows NT\CurrentVersion\SystemRestore"


def create_restore_point():
    """Crea un punto de restauración de Windows. Devuelve (ok, mensaje)."""
    if DEMO:
        time.sleep(1.2)
        return True, "Punto de restauración creado (demo)"
    if not is_admin():
        return False, "Para crear el punto de restauración hay que ejecutar como administrador"
    prev = reg_read("HKLM", _SR_KEY, "SystemRestorePointCreationFrequency")
    try:   # por defecto Windows solo permite 1 punto cada 24 h: lo desactivamos un momento
        reg_write("HKLM", _SR_KEY, "SystemRestorePointCreationFrequency", 0, REG_DWORD)
    except OSError:
        pass
    script = ("$ErrorActionPreference='Stop'; try { "
              "Enable-ComputerRestore -Drive ($env:SystemDrive + '\\'); "
              "Checkpoint-Computer -Description 'HellOP' -RestorePointType 'MODIFY_SETTINGS'; "
              "'OK' } catch { 'ERR: ' + $_.Exception.Message }")
    rc, out, err = run_ps(script, timeout=240)
    try:
        if prev is None:
            reg_delete("HKLM", _SR_KEY, "SystemRestorePointCreationFrequency")
        else:
            reg_write("HKLM", _SR_KEY, "SystemRestorePointCreationFrequency", prev[0], REG_DWORD)
    except OSError:
        pass
    if out.strip().endswith("OK"):
        return True, "Punto de restauración creado"
    return False, (out or err or "No se pudo crear (¿protección del sistema desactivada?)")[:300]


# --------------------------------------------------------------------------
# Ajustes de registro (retrasos, juegos, red…)
# --------------------------------------------------------------------------
class RegTweak(Action):
    def __init__(self, id, group, title, desc, changes, needs_admin=False,
                 profiles=("gaming", "work"), risk="bajo", reboot=False, require_existing=False,
                 effect="", warning=""):
        self.id, self.group, self.title, self.desc = id, group, title, desc
        self.effect, self.warning = effect, warning
        self.changes = changes          # [(hive, path, name, valor, tipo)]
        self.needs_admin, self.profiles, self.risk = needs_admin, profiles, risk
        self.reboot, self.require_existing = reboot, require_existing

    def check(self):
        applied, shown = True, []
        for h, p, n, val, _t in self.changes:
            cur = reg_read(h, p, n)
            if self.require_existing and cur is None:
                return None
            if cur is None or _norm(cur[0]) != _norm(val):
                applied = False
            shown.append((n, cur[0] if cur else "por defecto", val))
        if applied:
            return None
        if len(shown) == 1:
            n, c, v = shown[0]
            return f"Ahora: {n} = {c}  →  nuevo: {v}"
        return f"Modifica {len(shown)} ajustes del registro"

    def apply(self):
        prev = []
        for h, p, n, val, t in self.changes:
            cur = reg_read(h, p, n)
            old = None
            if cur:
                v = cur[0]
                old = [{"__hex__": bytes(v).hex()} if isinstance(v, (bytes, bytearray)) else v, cur[1]]
            prev.append({"h": h, "p": p, "n": n, "old": old})
            reg_write(h, p, n, val, t)
        return {"prev": prev}

    @classmethod
    def undo_data(cls, data):
        for e in reversed(data["prev"]):
            if e["old"] is None:
                reg_delete(e["h"], e["p"], e["n"])
            else:
                v = e["old"][0]
                if isinstance(v, dict) and "__hex__" in v:
                    v = bytes.fromhex(v["__hex__"])
                reg_write(e["h"], e["p"], e["n"], v, e["old"][1])


_EXPL = r"Software\Microsoft\Windows\CurrentVersion\Explorer"
_DESK = r"Control Panel\Desktop"
_PROF = r"SOFTWARE\Microsoft\Windows NT\CurrentVersion\Multimedia\SystemProfile"


def reg_tweaks():
    return [
        RegTweak("ui_startup_delay", "speed", "Quitar el retraso de las apps de inicio",
                 "Windows espera unos segundos antes de abrir tus programas de inicio tras iniciar sesión. "
                 "Se pone a 0 para que estén listos al instante.",
                 [("HKCU", _EXPL + r"\Serialize", "StartupDelayInMSec", 0, REG_DWORD)]),
        RegTweak("ui_menu_delay", "speed", "Menús instantáneos",
                 "Los menús tardan 400 ms en desplegarse por defecto. Con 0 aparecen al momento.",
                 [("HKCU", _DESK, "MenuShowDelay", "0", REG_SZ)]),
        RegTweak("ui_fast_close", "speed", "Cierre de apps y apagado más rápido",
                 "Reduce a 2 segundos la espera de Windows para cerrar apps y servicios colgados al apagar o reiniciar.",
                 [("HKCU", _DESK, "WaitToKillAppTimeout", "2000", REG_SZ),
                  ("HKCU", _DESK, "HungAppTimeout", "2000", REG_SZ),
                  ("HKCU", _DESK, "AutoEndTasks", "1", REG_SZ),
                  ("HKLM", r"SYSTEM\CurrentControlSet\Control", "WaitToKillServiceTimeout", "2000", REG_SZ)],
                 needs_admin=True),
        RegTweak("ui_visual_lite", "speed", "Efectos visuales ligeros",
                 "Quita transparencias y animaciones de ventanas y barra de tareas. Menos carga para CPU/GPU y "
                 "sensación más ágil. Se nota tras cerrar sesión.",
                 [("HKCU", r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize", "EnableTransparency", 0, REG_DWORD),
                  ("HKCU", _EXPL + r"\Advanced", "TaskbarAnimations", 0, REG_DWORD),
                  ("HKCU", _DESK + r"\WindowMetrics", "MinAnimate", "0", REG_SZ)],
                 reboot=True),
        RegTweak("game_mode", "gaming", "Activar el Modo Juego de Windows",
                 "Windows prioriza el juego en primer plano y evita tareas de fondo (actualizaciones, drivers) mientras juegas.",
                 [("HKCU", r"Software\Microsoft\GameBar", "AutoGameModeEnabled", 1, REG_DWORD),
                  ("HKCU", r"Software\Microsoft\GameBar", "AllowAutoGameMode", 1, REG_DWORD)],
                 profiles=("gaming",)),
        RegTweak("game_dvr", "gaming", "Desactivar la grabación en segundo plano (Xbox Game Bar)",
                 "Game Bar graba clips en segundo plano y consume GPU y CPU. Puedes seguir usando otros grabadores.",
                 [("HKCU", r"System\GameConfigStore", "GameDVR_Enabled", 0, REG_DWORD),
                  ("HKCU", r"Software\Microsoft\Windows\CurrentVersion\GameDVR", "AppCaptureEnabled", 0, REG_DWORD)]),
        RegTweak("game_mouse", "gaming", "Ratón sin aceleración (movimiento 1:1)",
                 "Desactiva «Mejorar precisión del puntero»: el cursor se mueve exactamente lo que mueves la mano. "
                 "Se aplica al volver a iniciar sesión.",
                 [("HKCU", r"Control Panel\Mouse", "MouseSpeed", "0", REG_SZ),
                  ("HKCU", r"Control Panel\Mouse", "MouseThreshold1", "0", REG_SZ),
                  ("HKCU", r"Control Panel\Mouse", "MouseThreshold2", "0", REG_SZ)],
                 profiles=("gaming",), reboot=True),
        RegTweak("game_priority", "gaming", "Prioridad máxima para juegos (menos latencia)",
                 "Da más tiempo de CPU y prioridad de GPU a los juegos y reduce la reserva para tareas multimedia (de 20% a 0%).",
                 [("HKLM", _PROF, "SystemResponsiveness", 0, REG_DWORD),
                  ("HKLM", _PROF + r"\Tasks\Games", "GPU Priority", 8, REG_DWORD),
                  ("HKLM", _PROF + r"\Tasks\Games", "Priority", 6, REG_DWORD),
                  ("HKLM", _PROF + r"\Tasks\Games", "Scheduling Category", "High", REG_SZ),
                  ("HKLM", _PROF + r"\Tasks\Games", "SFIO Priority", "High", REG_SZ)],
                 needs_admin=True, profiles=("gaming",)),
        RegTweak("game_hags", "gaming", "Programación de GPU acelerada por hardware",
                 "Deja que la gráfica gestione su propia memoria: menos latencia y carga de CPU en gráficas compatibles. "
                 "Requiere reiniciar.",
                 [("HKLM", r"SYSTEM\CurrentControlSet\Control\GraphicsDrivers", "HwSchMode", 2, REG_DWORD)],
                 needs_admin=True, profiles=("gaming",), reboot=True, require_existing=True),
        RegTweak("net_throttle", "network", "Quitar el límite de red de Windows",
                 "Windows limita por defecto el tráfico de red mientras reproduces multimedia. Se desactiva para menos "
                 "latencia y más velocidad estable en juegos y descargas.",
                 [("HKLM", _PROF, "NetworkThrottlingIndex", 0xFFFFFFFF, REG_DWORD)],
                 needs_admin=True, profiles=("gaming",)),
    ]


# --------------------------------------------------------------------------
# Plan de energía
# --------------------------------------------------------------------------
GUID_RE = r"([0-9a-fA-F]{8}-(?:[0-9a-fA-F]{4}-){3}[0-9a-fA-F]{12})"
GUID_HIGH = "8c5e7fda-e8bf-4a96-9a85-a6e23a8c635c"
GUID_ULTIMATE = "e9a42b02-d5df-448d-aa00-03f14749eb61"


def active_scheme():
    rc, out, _ = run_cmd(["powercfg", "/getactivescheme"])
    m = re.search(GUID_RE + r"\s*\(([^)]*)\)", out)
    return (m.group(1).lower(), m.group(2)) if m else (None, None)


class PowerPlanAction(Action):
    id, group = "power_plan", "power"
    needs_admin = True
    profiles = ("gaming",)

    def __init__(self):
        self.desktop = psutil.sensors_battery() is None
        self.title = "Plan de energía: máximo rendimiento"
        self.desc = ("La CPU deja de bajar su frecuencia para ahorrar energía: respuesta inmediata, menos 'tirones' al "
                     "abrir cosas. " + ("Es un PC de sobremesa: no gasta batería." if self.desktop else
                                         "OJO: es un portátil, gastará más batería y generará más calor."))
        if not self.desktop:
            self.risk = "medio"

    def check(self):
        guid, name = active_scheme()
        if not guid:
            return None
        if guid in (GUID_HIGH, GUID_ULTIMATE) or re.search(r"ultimate|m[aá]x|alto rendimiento|high perf", name or "", re.I):
            return None
        return f"Plan actual: {name}"

    def apply(self):
        prev, _ = active_scheme()
        target = GUID_HIGH
        rc, out, _ = run_cmd(["powercfg", "/list"])
        existing = None
        for line in out.splitlines():
            if re.search(r"ultimate|rendimiento m[aá]ximo|m[aá]ximo rendimiento", line, re.I):
                m = re.search(GUID_RE, line)
                existing = m.group(1) if m else None
        if self.desktop:
            if existing:
                target = existing
            else:
                rc, out, _ = run_cmd(["powercfg", "-duplicatescheme", GUID_ULTIMATE])
                m = re.search(GUID_RE, out)
                if rc == 0 and m:
                    target = m.group(1)
        rc, out, err = run_cmd(["powercfg", "/setactive", target])
        if rc != 0:
            raise RuntimeError(err or out or "powercfg falló")
        return {"prev": prev}

    @classmethod
    def undo_data(cls, data):
        if data.get("prev"):
            run_cmd(["powercfg", "/setactive", data["prev"]])


# --------------------------------------------------------------------------
# Programas de inicio (uno por uno)
# --------------------------------------------------------------------------
_APPROVED = r"Software\Microsoft\Windows\CurrentVersion\Explorer\StartupApproved"
_RUN = r"Software\Microsoft\Windows\CurrentVersion\Run"
STARTUP_SOURCES = [   # (hive, clave Run, clave StartupApproved, necesita admin)
    ("HKCU", _RUN, _APPROVED + r"\Run", False),
    ("HKLM", r"SOFTWARE\Microsoft\Windows\CurrentVersion\Run", _APPROVED + r"\Run", True),
    ("HKLM", r"SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Run", _APPROVED + r"\Run32", True),
]
PROTECTED_STARTUP = ("securityhealth", "windows defender", "windowsdefender", "pcoptimizer", "pc optimizer", "hellop")

STARTUP_HINTS = [   # (patrón, explicación, ¿conviene dejarlo?)
    (r"discord", "Chat de voz. Se abrirá igual cuando lo lances tú.", False),
    (r"steam", "Tienda y launcher de juegos. Ábrelo cuando vayas a jugar.", False),
    (r"spotify", "Música. Puedes abrirlo tú cuando quieras.", False),
    (r"teams", "Reuniones de Microsoft Teams. Si lo usas a diario, déjalo.", False),
    (r"onedrive", "Sincroniza tus archivos con la nube. Si usas OneDrive, déjalo.", True),
    (r"epic", "Launcher de Epic Games. Ábrelo cuando juegues.", False),
    (r"battle\.net|blizzard", "Launcher de Blizzard. Ábrelo cuando juegues.", False),
    (r"ubisoft|uplay", "Launcher de Ubisoft. Ábrelo cuando juegues.", False),
    (r"origin|ea ?desktop|eadesktop", "Launcher de EA. Ábrelo cuando juegues.", False),
    (r"adobe|creative cloud|acrobat", "Servicios de Adobe en segundo plano. No hacen falta hasta abrir Adobe.", False),
    (r"dropbox|google ?drive|googledrive", "Sincronización en la nube. Si la usas, déjala.", True),
    (r"zoom", "Videollamadas. Se abre solo cuando lo necesites.", False),
    (r"skype", "Skype se inicia con Windows. Ábrelo solo si lo usas.", False),
    (r"itunes|ipod|apple", "Servicios de Apple en segundo plano.", False),
    (r"java|jusched", "Comprobador de actualizaciones de Java. Se puede quitar.", False),
    (r"realtek|rthd|waves", "Audio (Realtek). Si dejas de oír los ajustes de sonido, vuelve a activarlo.", True),
    (r"nvidia|nvcpl|nvtray", "Panel o servicios de tu gráfica NVIDIA. Mejor dejarlo.", True),
    (r"radeon|amd", "Software de tu gráfica AMD. Mejor dejarlo.", True),
    (r"intel", "Componente de Intel. Mejor dejarlo si no estás seguro.", True),
    (r"logi|razer|corsair|icue|steelseries|synapse", "Software de periféricos (RGB, perfiles, macros). Si usas esos ajustes, déjalo.", True),
    (r"wallpaper", "Fondo animado: consume GPU/CPU constantemente.", False),
]


def describe_startup(name, command):
    text = f"{name} {command}".lower()
    for pat, desc, keep in STARTUP_HINTS:
        if re.search(pat, text):
            return desc, keep
    return ("Se abre solo al encender y se queda en segundo plano gastando RAM y CPU. "
            "Podrás abrirlo tú cuando lo necesites.", False)


def startup_entries():
    items = []
    for hive, run, approved, admin in STARTUP_SOURCES:
        for name, value, _t in reg_values(hive, run):
            items.append({"name": name, "command": str(value), "hive": hive, "approved": approved, "admin": admin})
    folders = [("HKCU", Path(os.environ.get("APPDATA", "")) / "Microsoft/Windows/Start Menu/Programs/Startup", False),
               ("HKLM", Path(os.environ.get("PROGRAMDATA", "")) / "Microsoft/Windows/Start Menu/Programs/StartUp", True)]
    for hive, folder, admin in folders:
        try:
            for f in folder.iterdir():
                if f.name.lower() != "desktop.ini":
                    items.append({"name": f.name, "command": str(f), "hive": hive,
                                  "approved": _APPROVED + r"\StartupFolder", "admin": admin})
        except OSError:
            pass
    for it in items:
        cur = reg_read(it["hive"], it["approved"], it["name"])
        it["enabled"] = not (cur and isinstance(cur[0], (bytes, bytearray)) and cur[0] and cur[0][0] % 2 == 1)
    return items


def count_enabled_startup():
    try:
        return sum(1 for i in startup_entries() if i["enabled"])
    except Exception:  # noqa: BLE001
        return None


def _filetime_now():
    return int((time.time() + 11644473600) * 10_000_000)


class StartupAction(Action):
    group = "startup"
    reversible = True

    def __init__(self, item):
        self.item = item
        self.id = f"startup:{item['hive']}:{item['name']}"
        self.needs_admin = item["admin"]
        desc, keep = describe_startup(item["name"], item["command"])
        self.title = f"No abrir «{item['name']}» al iniciar Windows"
        self.desc = desc
        self.risk = "medio" if keep else "bajo"
        self._cmd = item["command"]

    def check(self):
        c = self._cmd.strip()
        return "Ruta: " + (c if len(c) <= 90 else c[:87] + "…")

    def apply(self):
        it = self.item
        prev = reg_read(it["hive"], it["approved"], it["name"])
        value = bytes([3, 0, 0, 0]) + struct.pack("<Q", _filetime_now())
        reg_write(it["hive"], it["approved"], it["name"], value, REG_BINARY)
        return {"hive": it["hive"], "approved": it["approved"], "name": it["name"],
                "prev": prev[0].hex() if prev and isinstance(prev[0], (bytes, bytearray)) else None}

    @classmethod
    def undo_data(cls, data):
        if data.get("prev"):
            reg_write(data["hive"], data["approved"], data["name"], bytes.fromhex(data["prev"]), REG_BINARY)
        else:
            reg_delete(data["hive"], data["approved"], data["name"])


def startup_actions():
    acts = []
    for it in startup_entries():
        if not it["enabled"]:
            continue
        if any(p in it["name"].lower() for p in PROTECTED_STARTUP):
            continue
        acts.append(StartupAction(it))
    return acts


# --------------------------------------------------------------------------
# Servicios innecesarios (uno por uno)
# --------------------------------------------------------------------------
SERVICES = [   # (nombre, título, descripción, solo si el disco del sistema es SSD)
    ("DiagTrack", "Telemetría de Windows (Experiencias del usuario conectado)",
     "Envía datos de uso a Microsoft y consume CPU/disco en segundo plano. Desactivarlo no afecta a nada que uses.", False),
    ("dmwappushservice", "Mensajes push de telemetría (WAP)",
     "Servicio auxiliar de la telemetría. Se puede desactivar con seguridad.", False),
    ("SysMain", "SysMain (Superfetch)",
     "Precarga programas en RAM. En un SSD no aporta casi nada y genera escrituras y uso de memoria de más.", True),
    ("MapsBroker", "Mapas descargados",
     "Gestiona mapas sin conexión de la app Mapas. Solo hace falta si la usas.", False),
    ("Fax", "Fax", "Servicio de fax. Casi nadie lo usa.", False),
    ("RetailDemo", "Modo demo de tienda", "Es para equipos de exposición en tiendas. No hace falta en casa.", False),
    ("WerSvc", "Informe de errores de Windows",
     "Envía informes de fallos a Microsoft tras un cuelgue. Desactivarlo evita picos de disco tras errores.", False),
]
_START_NAMES = {2: "auto", 3: "demand", 4: "disabled"}


def system_drive_media():
    rc, out, _ = run_ps("$n=(Get-Partition -DriveLetter ($env:SystemDrive.TrimEnd(':'))).DiskNumber; "
                        "(Get-PhysicalDisk | Where-Object DeviceId -eq $n).MediaType")
    return out.strip().upper()


class ServiceAction(Action):
    group = "services"
    needs_admin = True

    def __init__(self, name, title, desc, profiles=None, risk="bajo", effect=""):
        self.name = name
        self.id = f"svc:{name}"
        self.title = f"Desactivar servicio: {title}"
        self.desc = desc
        if profiles:
            self.profiles = profiles
        self.risk, self.effect = risk, effect

    def check(self):
        cur = reg_read("HKLM", rf"SYSTEM\CurrentControlSet\Services\{self.name}", "Start")
        if cur is None or cur[0] == 4:
            return None
        return f"Servicio «{self.name}»: {'automático' if cur[0] == 2 else 'manual'}"

    def apply(self):
        key = rf"SYSTEM\CurrentControlSet\Services\{self.name}"
        start = reg_read("HKLM", key, "Start")
        delayed = reg_read("HKLM", key, "DelayedAutostart")
        mode = _START_NAMES.get(start[0] if start else 3, "demand")
        if mode == "auto" and delayed and delayed[0] == 1:
            mode = "delayed-auto"
        rc, out, err = run_cmd(["sc", "config", self.name, "start=", "disabled"])
        if rc != 0:
            raise RuntimeError(out or err or "sc config falló")
        run_cmd(["sc", "stop", self.name])
        return {"name": self.name, "mode": mode}

    @classmethod
    def undo_data(cls, data):
        run_cmd(["sc", "config", data["name"], "start=", data["mode"]])


def service_actions():
    media = system_drive_media()
    acts = []
    for name, title, desc, ssd_only in SERVICES:
        if ssd_only and media != "SSD":
            continue
        acts.append(ServiceAction(name, title, desc))
    return acts


# --------------------------------------------------------------------------
# Apps innecesarias de Windows (bloatware)
# --------------------------------------------------------------------------
BLOAT = [   # (patrón del paquete, nombre, descripción)
    ("Microsoft.BingNews", "Noticias de Microsoft", "App de noticias con anuncios."),
    ("Microsoft.BingWeather", "El Tiempo de Microsoft", "Solo quítala si no la usas."),
    ("Microsoft.GetHelp", "Obtener ayuda", "Atajo al soporte de Microsoft."),
    ("Microsoft.Getstarted", "Consejos de Windows", "Sugerencias y tutoriales de Windows."),
    ("Microsoft.MicrosoftOfficeHub", "Mi Office", "Anuncio/atajo de Microsoft 365."),
    ("Microsoft.MicrosoftSolitaireCollection", "Solitario y juegos de Microsoft", "Juegos con anuncios."),
    ("Microsoft.People", "Contactos", "App de contactos que casi nadie usa."),
    ("Microsoft.SkypeApp", "Skype", "Versión preinstalada de Skype."),
    ("Microsoft.WindowsFeedbackHub", "Centro de opiniones", "Envía comentarios a Microsoft."),
    ("Microsoft.MixedReality.Portal", "Portal de realidad mixta", "Solo para gafas de realidad mixta."),
    ("Microsoft.Microsoft3DViewer", "Visor 3D", "Visor de modelos 3D."),
    ("Microsoft.Print3D", "Print 3D", "Impresión 3D."),
    ("Microsoft.ZuneVideo", "Películas y TV", "Reproductor de vídeo de Microsoft."),
    ("Microsoft.WindowsMaps", "Mapas de Windows", "App de mapas."),
    ("Microsoft.549981C3F5F10", "Cortana", "Asistente antiguo de Windows."),
    ("Microsoft.PowerAutomateDesktop", "Power Automate", "Automatización de Microsoft."),
    ("Clipchamp.Clipchamp", "Clipchamp", "Editor de vídeo de Microsoft."),
    ("MicrosoftTeams", "Teams (versión personal)", "Chat de Teams preinstalado."),
    ("king.com.*", "Juegos de King (Candy Crush…)", "Juegos patrocinados preinstalados."),
    ("SpotifyAB.SpotifyMusic", "Spotify (preinstalado)", "Podrás volver a instalarlo cuando quieras."),
    ("Disney.*", "Disney+ (preinstalado)", "App patrocinada."),
    ("AmazonVideo.PrimeVideo", "Prime Video (preinstalado)", "App patrocinada."),
    ("*TikTok*", "TikTok (preinstalado)", "App patrocinada."),
    ("*Instagram*", "Instagram (preinstalado)", "App patrocinada."),
    ("*Facebook*", "Facebook (preinstalado)", "App patrocinada."),
]


class BloatAction(Action):
    group = "bloat"
    reversible = False

    def __init__(self, pkg, title, desc):
        self.pkg = pkg
        self.id = f"bloat:{pkg}"
        self.title = f"Quitar «{title}»"
        self.desc = desc + " Se puede volver a instalar desde la Microsoft Store."

    def check(self):
        return f"Paquete: {self.pkg}"

    def apply(self):
        if not re.fullmatch(r"[A-Za-z0-9._-]+", self.pkg):
            raise ValueError("Nombre de paquete no válido")
        rc, out, err = run_ps(f"Get-AppxPackage -Name {ps_quote(self.pkg)} | Remove-AppxPackage", timeout=180)
        if rc != 0 and err:
            raise RuntimeError(err[:200])
        return {}


def bloat_actions():
    names = as_list(run_ps_json("ConvertTo-Json -InputObject @(Get-AppxPackage | Select-Object -ExpandProperty Name) -Compress",
                                timeout=60, default=[]))
    acts, seen = [], set()
    for pattern, title, desc in BLOAT:
        for n in names:
            if fnmatch.fnmatch(n.lower(), pattern.lower()) and n not in seen:
                seen.add(n)
                acts.append(BloatAction(n, title, desc))
    return acts


# --------------------------------------------------------------------------
# Procesos pesados en segundo plano
# --------------------------------------------------------------------------
PROTECTED_PROCS = {
    "explorer.exe", "dwm.exe", "sihost.exe", "taskhostw.exe", "runtimebroker.exe", "ctfmon.exe",
    "searchhost.exe", "searchapp.exe", "startmenuexperiencehost.exe", "shellexperiencehost.exe",
    "textinputhost.exe", "securityhealthsystray.exe", "fontdrvhost.exe", "conhost.exe", "svchost.exe",
    "lsass.exe", "csrss.exe", "winlogon.exe", "services.exe", "wininit.exe", "smss.exe", "system",
    "registry", "memcompression", "msmpeng.exe", "audiodg.exe", "applicationframehost.exe",
    "msedgewebview2.exe", "widgets.exe", "lockapp.exe", "dllhost.exe", "backgroundtaskhost.exe",
    "systemsettings.exe", "taskmgr.exe", "python.exe", "pythonw.exe", "pcoptimizer.exe", "hellop.exe", "wmiprvse.exe",
}


class ProcessAction(Action):
    group = "procs"
    reversible = False
    risk = "medio"

    def __init__(self, name, pids, rss):
        self.name, self.pids, self.rss = name, pids, rss
        self.id = f"proc:{name}"
        n = len(pids)
        self.title = f"Cerrar «{name}» ({fmt_bytes(rss)} de RAM)"
        self.desc = (f"Está abierto con {n} proceso{'s' if n > 1 else ''} usando {fmt_bytes(rss)}. "
                     "Si lo cierras se libera esa memoria al instante. Guarda antes tu trabajo en esa app.")

    def check(self):
        return "Abierto ahora mismo"

    def apply(self):
        closed, freed = 0, 0
        procs = []
        for pid in self.pids:
            try:
                p = psutil.Process(pid)
                freed += p.memory_info().rss
                p.terminate()
                procs.append(p)
            except psutil.Error:
                continue
        _gone, alive = psutil.wait_procs(procs, timeout=4)
        for p in alive:
            try:
                p.kill()
            except psutil.Error:
                pass
        closed = len(procs)
        return {"_msg": f"Cerrados {closed} procesos · liberados {fmt_bytes(freed)}"}


def process_actions(min_total=150 * 1024 * 1024, limit=8):
    me = os.getpid()
    try:
        user = psutil.Process().username()
    except psutil.Error:
        user = None
    agg = {}
    for p in psutil.process_iter(["pid", "name", "memory_info", "username"]):
        try:
            i = p.info
            name = (i["name"] or "").lower()
            if i["pid"] == me or name in PROTECTED_PROCS or not name.endswith(".exe"):
                continue
            if user and i["username"] != user:
                continue
            e = agg.setdefault(name, [0, []])
            e[0] += i["memory_info"].rss
            e[1].append(i["pid"])
        except (psutil.NoSuchProcess, psutil.AccessDenied, AttributeError, TypeError):
            continue
    top = sorted(((rss, n, pids) for n, (rss, pids) in agg.items() if rss >= min_total), reverse=True)[:limit]
    return [ProcessAction(n, pids, rss) for rss, n, pids in top]


# --------------------------------------------------------------------------
# Red: DNS
# --------------------------------------------------------------------------
DNS_CANDIDATES = [
    ("Cloudflare", "1.1.1.1", "1.0.0.1"),
    ("Google", "8.8.8.8", "8.8.4.4"),
    ("Quad9", "9.9.9.9", "149.112.112.112"),
    ("OpenDNS", "208.67.222.222", "208.67.220.220"),
]
_TEST_DOMAINS = ["google.com", "wikipedia.org", "amazon.com", "microsoft.com", "cloudflare.com",
                 "github.com", "apple.com", "netflix.com"]


def build_dns_query(name):
    tid = random.randint(0, 65535)
    head = struct.pack(">HHHHHH", tid, 0x0100, 1, 0, 0, 0)
    body = b"".join(bytes([len(p)]) + p.encode() for p in name.split(".")) + b"\x00" + struct.pack(">HH", 1, 1)
    return head + body


def dns_query_ms(server, name, timeout=1.2):
    q = build_dns_query(name)
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.settimeout(timeout)
    try:
        t = time.perf_counter()
        s.sendto(q, (server, 53))
        data, _ = s.recvfrom(1024)
        dt = (time.perf_counter() - t) * 1000
        return dt if data[:2] == q[:2] else None
    except OSError:
        return None
    finally:
        s.close()


def dns_latency(server, rounds=6):
    vals = [v for v in (dns_query_ms(server, d) for d in _TEST_DOMAINS[:rounds]) if v is not None]
    if len(vals) < 3:
        return None
    vals.sort()
    return vals[len(vals) // 2]


_DNS_SCRIPT = r"""
$up = @(Get-NetAdapter -Physical | Where-Object Status -eq 'Up' | Select-Object -ExpandProperty ifIndex)
$r = @(Get-DnsClientServerAddress -AddressFamily IPv4 | Where-Object { $up -contains $_.InterfaceIndex } |
  ForEach-Object { [pscustomobject]@{Index=[int]$_.InterfaceIndex;Alias=[string]$_.InterfaceAlias;Servers=@($_.ServerAddresses)} })
ConvertTo-Json -InputObject $r -Depth 3 -Compress
"""
_dns_cache = {}


def current_dns_adapters():
    return as_list(run_ps_json(_DNS_SCRIPT, timeout=30, default=[]))


def measure_current_dns():
    """Latencia (ms) del DNS que usa ahora tu PC, o None."""
    if DEMO:
        return 18.0
    if "cur" not in _dns_cache:
        servers = [s for a in current_dns_adapters() for s in as_list(a.get("Servers"))]
        _dns_cache["cur"] = servers[0] if servers else None
    srv = _dns_cache["cur"]
    return dns_latency(srv, 5) if srv else None


class DnsAction(Action):
    group = "network"
    needs_admin = True
    id = "dns_fast"

    def __init__(self, provider, primary, secondary, cur_ms, new_ms, adapters):
        self.provider, self.primary, self.secondary = provider, primary, secondary
        self.adapters = adapters
        self.title = f"Cambiar el DNS a {provider} ({primary})"
        self.desc = ("El DNS traduce nombres de web a direcciones: uno más rápido hace que las páginas empiecen a cargar antes. "
                     "Es completamente reversible.")
        self._status = f"Tu DNS responde en {cur_ms:.0f} ms · {provider} en {new_ms:.0f} ms"

    def check(self):
        return self._status

    def apply(self):
        prev = {str(a["Index"]): as_list(a.get("Servers")) for a in self.adapters}
        idx = ",".join(str(a["Index"]) for a in self.adapters)
        script = (f"foreach($i in @({idx})){{ Set-DnsClientServerAddress -InterfaceIndex $i "
                  f"-ServerAddresses ({ps_quote(self.primary)},{ps_quote(self.secondary)}) }}; ipconfig /flushdns | Out-Null")
        rc, out, err = run_ps(script, timeout=60)
        if rc != 0:
            raise RuntimeError(err or out)
        return {"prev": prev}

    @classmethod
    def undo_data(cls, data):
        for idx, servers in data["prev"].items():
            if servers:
                addr = ",".join(ps_quote(s) for s in servers)
                run_ps(f"Set-DnsClientServerAddress -InterfaceIndex {int(idx)} -ServerAddresses ({addr})")
            else:
                run_ps(f"Set-DnsClientServerAddress -InterfaceIndex {int(idx)} -ResetServerAddresses")
        run_cmd(["ipconfig", "/flushdns"])


class FlushDnsAction(Action):
    id, group = "flush_dns", "network"
    reversible = False
    title = "Vaciar la caché DNS"
    desc = "Borra las direcciones web guardadas por si alguna está desactualizada. Inofensivo."

    def check(self):
        return ""

    def apply(self):
        run_cmd(["ipconfig", "/flushdns"])
        return {}


def network_actions():
    acts = [FlushDnsAction()]
    adapters = [a for a in current_dns_adapters() if a.get("Servers") is not None]
    if not adapters:
        return acts
    current = [s for a in adapters for s in as_list(a.get("Servers"))]
    cands = [c for c in DNS_CANDIDATES if c[1] not in current]
    with cf.ThreadPoolExecutor(max_workers=5) as ex:
        f_cur = ex.submit(dns_latency, current[0], 6) if current else None
        futs = {c: ex.submit(dns_latency, c[1], 6) for c in cands}
        cur_ms = f_cur.result() if f_cur else None
        res = {c: f.result() for c, f in futs.items()}
    res = {c: v for c, v in res.items() if v}
    if cur_ms and res:
        best = min(res, key=res.get)
        if res[best] < cur_ms * 0.85 and cur_ms - res[best] >= 3:
            acts.append(DnsAction(best[0], best[1], best[2], cur_ms, res[best], adapters))
    return acts


# --------------------------------------------------------------------------
# Modo demo (para ver la app sin tocar nada)
# --------------------------------------------------------------------------
class DemoAction(Action):
    reversible = True

    def __init__(self, id, group, title, desc, status="", reversible=True, risk="bajo", admin=False, reboot=False,
                 profiles=("gaming", "work"), effect="", warning=""):
        self.id, self.group, self.title, self.desc = id, group, title, desc
        self.effect, self.warning = effect, warning
        self._status, self.reversible, self.risk = status, reversible, risk
        self.needs_admin, self.reboot, self.profiles = admin, reboot, profiles

    def check(self):
        return self._status

    def apply(self):
        time.sleep(0.35)
        return {}

    @classmethod
    def undo_data(cls, data):
        time.sleep(0.1)


def demo_actions():
    return [
        DemoAction("d1", "power", "Plan de energía: máximo rendimiento", "La CPU deja de bajar su frecuencia para ahorrar energía.", "Plan actual: Equilibrado", admin=True, profiles=("gaming",)),
        DemoAction("d2", "speed", "Quitar el retraso de las apps de inicio", "Windows espera unos segundos antes de abrir tus programas de inicio.", "Ahora: StartupDelayInMSec = por defecto  →  nuevo: 0"),
        DemoAction("d3", "speed", "Menús instantáneos", "Los menús aparecen al momento en vez de a los 400 ms.", "Ahora: MenuShowDelay = 400  →  nuevo: 0"),
        DemoAction("d4", "gaming", "Ratón sin aceleración (movimiento 1:1)", "El cursor se mueve exactamente lo que mueves la mano.", "Modifica 3 ajustes del registro", reboot=True, profiles=("gaming",)),
        DemoAction("d5", "gaming", "Prioridad máxima para juegos (menos latencia)", "Más tiempo de CPU y prioridad de GPU para los juegos.", "Modifica 5 ajustes del registro", admin=True, profiles=("gaming",)),
        DemoAction("d6", "startup", "No abrir «Discord» al iniciar Windows", "Chat de voz. Se abrirá igual cuando lo lances tú.", r"Ruta: C:\Users\Tú\AppData\Local\Discord\Update.exe --processStart Discord.exe"),
        DemoAction("d7", "startup", "No abrir «RtkAudUService» al iniciar Windows", "Audio (Realtek). Si dejas de oír los ajustes de sonido, vuelve a activarlo.", r"Ruta: C:\Windows\System32\DriverStore\RtkAudUService64.exe", risk="medio"),
        DemoAction("d8", "services", "Desactivar servicio: Telemetría de Windows", "Envía datos de uso a Microsoft y consume CPU/disco.", "Servicio «DiagTrack»: automático", admin=True),
        DemoAction("d9", "bloat", "Quitar «Juegos de King (Candy Crush…)»", "Juegos patrocinados preinstalados. Se puede volver a instalar desde la Microsoft Store.", "Paquete: king.com.CandyCrushSaga", reversible=False),
        DemoAction("d10", "procs", "Cerrar «chrome.exe» (1.4 GB de RAM)", "Está abierto con 23 procesos usando 1.4 GB. Guarda antes tu trabajo.", "Abierto ahora mismo", reversible=False, risk="medio"),
        DemoAction("x1", "latency", "Procesador siempre al 100 % (sin bajar de frecuencia)", "La CPU nunca baja su estado mínimo: respuesta inmediata, algo más de consumo y calor.", "Valor actual: 5 → nuevo: 100", admin=True, profiles=("extreme",), effect="real"),
        DemoAction("x2", "latency", "Quitar el temporizador HPET forzado", "Tu Windows fuerza el reloj HPET, que añade latencia en cada lectura de tiempo.", "useplatformclock: yes → (quitar)", admin=True, reboot=True, profiles=("extreme",), effect="real"),
        DemoAction("x3", "latency", "Desactivar el ahorro de energía de la tarjeta de red (Realtek PCIe GbE)", "Quita EEE, Green Ethernet y moderación de interrupciones: menos latencia de red. Se corta la red 2 segundos.", "Ajustes: 3", admin=True, profiles=("extreme",), effect="pequeño"),
        DemoAction("x4", "latency", "Modo MSI en la gráfica (NVIDIA GeForce RTX 3060)", "Las interrupciones de la GPU pasan a MSI: menos latencia y carga de CPU.", "MSISupported = por defecto → 1", admin=True, reboot=True, risk="medio", profiles=("extreme",), effect="depende"),
        DemoAction("x5", "tradeoff", "Desactivar VBS / Integridad de memoria", "Windows ejecuta tu sistema dentro de un mini-hipervisor de seguridad que cuesta FPS en algunos juegos.", "VBS: activo", admin=True, reboot=True, risk="alto", profiles=("extreme",), effect="real", warning="Baja la protección contra malware que ataca el núcleo de Windows. Solo si juegas en un PC que usas con cuidado."),
        DemoAction("x6", "gpu", "Ryzen: preferencia de rendimiento al máximo (EPP = 0)", "Tu Ryzen sube de frecuencia al instante ante cualquier carga: mejores mínimos de FPS.", "Valor actual: 33 → nuevo: 0", admin=True, profiles=("extreme",), effect="depende"),
        DemoAction("x7", "gpu", "NVIDIA: relojes siempre altos, sin bajar de velocidad (NVIDIA GeForce RTX 3060)", "Modo «Preferir el máximo rendimiento» forzado desde el registro: la GPU no tarda en volver a subir de velocidad.", "Modifica 4 ajustes del registro", admin=True, reboot=True, risk="medio", profiles=("extreme",), effect="depende", warning="Más calor y ruido en reposo. Se deshace desde el Historial."),
        DemoAction("x8", "gpu", "NVIDIA: subir el límite de potencia al máximo permitido", "La GPU mantiene más tiempo sus relojes altos bajo carga. Se pierde al apagar el PC.", "Límite actual: 170 W  →  máximo permitido: 170 W", admin=True, risk="medio", profiles=("extreme",), effect="pequeño"),
        DemoAction("y1", "deep", "Desactivar las tareas de telemetría y compatibilidad de Windows", "Tareas que recogen datos de uso y aparecen de golpe consumiendo disco y CPU, a veces en plena partida.", "5 tarea(s) programada(s) activa(s)", admin=True, profiles=("deep",), effect="real"),
        DemoAction("y2", "deep", "Quitar publicidad, apps patrocinadas y sugerencias de Windows", "Windows instala apps patrocinadas y muestra consejos en Inicio y en la pantalla de bloqueo. Esto lo apaga todo.", "Modifica 21 ajustes del registro", profiles=("deep",), effect="pequeño"),
        DemoAction("y3", "deep", "Quitar el reparto de actualizaciones entre PCs (P2P)", "Windows puede usar tu conexión para subir actualizaciones a otros ordenadores: te roba ancho de banda jugando online.", "Ahora: DODownloadMode = por defecto  →  nuevo: 0", admin=True, profiles=("deep",), effect="real"),
        DemoAction("y4", "deep", "Edge: que no se ejecute en segundo plano", "Edge se queda cargado y precarga páginas aunque no lo uses. Esto lo detiene.", "Modifica 2 ajustes del registro", admin=True, profiles=("deep",), effect="real"),
        DemoAction("y5", "deep", "Desactivar Copilot y Recall (funciones de IA de Windows)", "Quita Copilot de la barra y evita que Recall capture tu pantalla para analizarla.", "Modifica 2 ajustes del registro", admin=True, profiles=("deep",), effect="pequeño"),
        DemoAction("y6", "deep", "Desactivar servicio: Telemetría de NVIDIA", "Envía datos de uso de tu driver a NVIDIA. Los juegos y el panel funcionan igual sin él.", "Servicio «NvTelemetryContainer»: automático", admin=True, profiles=("deep",), effect="pequeño"),
        DemoAction("y7", "latency", "Agrupar servicios de Windows en menos procesos (svchost)", "Se agrupan como en versiones antiguas: menos procesos, menos RAM y menos cambios de contexto.", "Ahora: SvcHostSplitThresholdInKB = por defecto  →  nuevo: 16777216", admin=True, reboot=True, profiles=("extreme",), effect="pequeño"),
        DemoAction("y8", "tradeoff", "Excluir tus carpetas de juegos del análisis en tiempo real del antivirus", "Defender no analiza cada archivo que el juego lee: menos tirones y cargas más rápidas.", "4 carpeta(s) de juegos sin excluir", admin=True, risk="medio", profiles=("extreme",), effect="depende", warning="Esas carpetas dejan de analizarse en busca de virus. Hazlo solo con juegos oficiales de Steam/Epic."),
        DemoAction("d11", "network", "Cambiar el DNS a Cloudflare (1.1.1.1)", "Un DNS más rápido hace que las páginas empiecen a cargar antes.", "Tu DNS responde en 31 ms · Cloudflare en 9 ms", admin=True),
    ]


# --------------------------------------------------------------------------
# Descubrir qué se puede hacer en ESTE equipo
# --------------------------------------------------------------------------
def discover(profile, progress=None):
    """profile: 'gaming' | 'work' | 'full'. Devuelve la lista ordenada de acciones aplicables."""
    if DEMO:
        time.sleep(1.5)
        acts = demo_actions()
    else:
        acts = []

        def step(msg, fn):
            if progress:
                progress(msg)
            try:
                acts.extend(fn())
            except Exception:  # noqa: BLE001
                pass
        step("Revisando plan de energía…", lambda: [PowerPlanAction()])
        step("Revisando ajustes del sistema…", reg_tweaks)
        step("Buscando programas de inicio…", startup_actions)
        step("Revisando servicios de Windows…", service_actions)
        step("Buscando apps innecesarias…", bloat_actions)
        step("Mirando qué consume tu RAM…", process_actions)
        step("Midiendo la velocidad de tu DNS…", network_actions)
        if profile == "extreme":
            import extreme
            step("Buscando ajustes extremos (registro, arranque, energía)…", extreme.extreme_actions)
            step("Revisando tarjeta de red y gráfica…", extreme.hardware_actions)
            import deepclean
            step("Buscando ajustes extra de rendimiento…", deepclean.extra_gaming_actions)
        if profile == "deep":
            import deepclean
            step("Revisando tareas programadas, telemetría y publicidad…", deepclean.deep_actions)
    chosen = []
    for a in acts:
        if profile == "full":
            if tuple(a.profiles) in (("extreme",), ("deep",)):
                continue            # lo extremo y la limpieza profunda solo se ofrecen si los eliges expresamente
        elif profile == "deep":
            if "deep" not in a.profiles and "work" not in a.profiles:
                continue
        elif profile == "extreme":
            if "gaming" not in a.profiles and "extreme" not in a.profiles:
                continue
        elif profile not in a.profiles:
            continue
        status = a.check()
        if status is None:
            continue
        a.status = status
        chosen.append(a)
    order = {g: i for i, (g, _n) in enumerate(GROUPS)}
    chosen.sort(key=lambda a: order.get(a.group, 99))
    return chosen
