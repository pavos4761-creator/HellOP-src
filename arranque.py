"""Gestor de arranque: todo lo que Windows abre al encender, con su impacto, para desactivarlo (y reactivarlo) con deshacer.

Reutiliza la lectura de programas de inicio de `actions` (claves Run y carpetas Inicio) y añade:
  · reactivar un programa (la otra mitad de «No abrir al iniciar»),
  · lo que Windows ha MEDIDO en tu último arranque (registro de eventos Diagnostics-Performance), si está disponible,
  · una estimación del impacto cuando no hay medición (marcada como estimación).
Desactivar NO desinstala nada: el programa sigue ahí y se abrirá cuando tú lo lances.
"""
import re

import actions
from actions import Action, REG_BINARY, reg_delete, reg_read, reg_write
from util import DEMO, IS_WIN, as_list, run_ps_json

_ALTO = re.compile(r"teams|adobe|creative cloud|wallpaper|skype|epic|battle\.net|blizzard|ubisoft|uplay|origin|ea ?desktop|eadesktop", re.I)
_MEDIO = re.compile(r"steam|discord|spotify|onedrive|dropbox|google ?drive|zoom|itunes|apple|java|jusched", re.I)
_MEJOR_DEJAR = re.compile(r"realtek|rthd|waves|nvidia|nvcpl|nvtray|radeon|amd|intel|logi|razer|corsair|icue|steelseries|synapse", re.I)


class StartupEnableAction(Action):
    """Vuelve a activar un programa de inicio que estaba desactivado."""
    group = "startup"
    reversible = True
    effect = "mínimo"

    def __init__(self, item):
        self.item = item
        self.id = f"startup-on:{item['hive']}:{item['name']}"
        self.needs_admin = item["admin"]
        self.title = f"Volver a abrir «{item['name']}» al iniciar Windows"
        self.desc = "Se vuelve a iniciar con Windows."

    def apply(self):
        it = self.item
        prev = reg_read(it["hive"], it["approved"], it["name"])
        reg_write(it["hive"], it["approved"], it["name"], bytes([2, 0, 0, 0]) + b"\x00" * 8, REG_BINARY)
        return {"hive": it["hive"], "approved": it["approved"], "name": it["name"],
                "prev": prev[0].hex() if prev and isinstance(prev[0], (bytes, bytearray)) else None}

    @classmethod
    def undo_data(cls, data):
        if data.get("prev"):
            reg_write(data["hive"], data["approved"], data["name"], bytes.fromhex(data["prev"]), REG_BINARY)
        else:
            reg_delete(data["hive"], data["approved"], data["name"])


# --------------------------------------------------------------------------
# Lectura
# --------------------------------------------------------------------------
def boot_report():
    """(segundos del último arranque | None, {nombre_en_minúsculas: ms que Windows midió de retraso}).
    Lee el registro de rendimiento de Windows; si no está disponible devuelve (None, {})."""
    if DEMO:
        return 41.0, {"discord": 3400.0, "teams": 5200.0, "onedrive": 1800.0, "spotify": 1200.0}
    if not IS_WIN:
        return None, {}
    script = r"""
$log = 'Microsoft-Windows-Diagnostics-Performance/Operational'
$boot = $null
$e = Get-WinEvent -FilterHashtable @{LogName=$log;Id=100} -MaxEvents 1 -ErrorAction SilentlyContinue
if ($e) { $x = [xml]$e.ToXml(); $boot = ($x.Event.EventData.Data | Where-Object { $_.Name -eq 'BootTime' }).'#text' }
$apps = @(Get-WinEvent -FilterHashtable @{LogName=$log;Id=101} -MaxEvents 60 -ErrorAction SilentlyContinue | ForEach-Object {
  $x = [xml]$_.ToXml(); $d = @{}; $x.Event.EventData.Data | ForEach-Object { $d[$_.Name] = $_.'#text' }
  [pscustomobject]@{Name=[string]$d['FriendlyName'];File=[string]$d['Name'];Total=[double]$d['TotalTime']} })
ConvertTo-Json -InputObject ([pscustomobject]@{Boot=$boot;Apps=$apps}) -Compress -Depth 4
"""
    data = run_ps_json(script, timeout=60, default=None)
    if not isinstance(data, dict):
        return None, {}
    try:
        boot = float(data.get("Boot")) / 1000.0
    except (TypeError, ValueError):
        boot = None
    slow = {}
    for a in as_list(data.get("Apps")):
        for key in (a.get("Name"), a.get("File")):
            if key:
                slow[str(key).lower()] = max(slow.get(str(key).lower(), 0.0), float(a.get("Total") or 0))
    return boot, slow


def _demo_entries():
    mk = lambda n, c, en=True, adm=False: {"name": n, "command": c, "hive": "HKCU", "approved": "x", "admin": adm, "enabled": en}  # noqa: E731
    return [mk("Discord", r"C:\Users\Tú\AppData\Local\Discord\Update.exe --processStart Discord.exe"),
            mk("MicrosoftTeams", r"C:\Users\Tú\AppData\Local\Microsoft\Teams\Update.exe --processStart Teams.exe"),
            mk("OneDrive", r"C:\Program Files\Microsoft OneDrive\OneDrive.exe /background"),
            mk("Spotify", r"C:\Users\Tú\AppData\Roaming\Spotify\Spotify.exe --autostart"),
            mk("RtkAudUService", r"C:\Windows\System32\DriverStore\RtkAudUService64.exe", adm=True),
            mk("SecurityHealth", r"C:\Windows\System32\SecurityHealthSystray.exe", adm=True),
            mk("Steam", r"C:\Program Files (x86)\Steam\steam.exe -silent", en=False),
            mk("EpicGamesLauncher", r"C:\Program Files (x86)\Epic Games\Launcher\EpicGamesLauncher.exe", en=False)]


def entries():
    """Todos los programas de inicio (activos y desactivados) con explicación, impacto y si están protegidos."""
    raw = _demo_entries() if DEMO else actions.startup_entries()
    boot, slow = boot_report()
    out = []
    for it in raw:
        text = f"{it['name']} {it['command']}"
        desc, keep = actions.describe_startup(it["name"], it["command"])
        measured = None
        for k, ms in slow.items():
            if k and (k in it["name"].lower() or k in it["command"].lower()):
                measured = ms
                break
        if measured is not None:
            impact = "alto" if measured >= 3000 else "medio" if measured >= 1000 else "bajo"
            how = f"medido por Windows: {measured / 1000:.1f} s"
        elif _MEJOR_DEJAR.search(text):
            impact, how = "bajo", "estimado"
        elif _ALTO.search(text):
            impact, how = "alto", "estimado"
        elif _MEDIO.search(text):
            impact, how = "medio", "estimado"
        else:
            impact, how = "medio", "estimado"
        out.append({**it, "desc": desc, "keep": keep, "impact": impact, "how": how,
                    "protected": any(p in it["name"].lower() for p in actions.PROTECTED_STARTUP)})
    out.sort(key=lambda i: (not i["enabled"], {"alto": 0, "medio": 1, "bajo": 2}[i["impact"]], i["name"].lower()))
    return out, boot


def disable(item):
    if DEMO:
        return actions.Result(True, "(Demo) no se ha tocado nada")
    return actions.execute(actions.StartupAction({k: item[k] for k in ("name", "command", "hive", "approved", "admin")}))


def enable(item):
    if DEMO:
        return actions.Result(True, "(Demo) no se ha tocado nada")
    return actions.execute(StartupEnableAction({k: item[k] for k in ("name", "command", "hive", "approved", "admin")}))
