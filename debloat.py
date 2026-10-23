"""Desinstalador de bloatware: apps de Windows y programas de fabricante que sobran.

Reglas de seguridad:
  · Nunca se muestran componentes de Windows, drivers (NVIDIA, AMD, Intel, Realtek…) ni la Microsoft Store.
  · Nada va marcado de antemano: tú eliges qué quitar.
  · Las apps de Windows se pueden volver a instalar desde la Microsoft Store. Los programas se desinstalan con
    su propio desinstalador (verás sus pantallas).
"""
import fnmatch
import re
import subprocess

import actions
from actions import Action
from util import DEMO, IS_WIN, as_list, ps_quote, run_ps, run_ps_json

# ---------- Lo que NUNCA se enseña ----------
PROTECTED_APPX = [
    "Microsoft.Windows*", "MicrosoftWindows.*", "Microsoft.UI.*", "Microsoft.VCLibs*", "Microsoft.NET*",
    "Microsoft.WindowsStore", "Microsoft.StorePurchaseApp", "Microsoft.DesktopAppInstaller", "Microsoft.SecHealthUI",
    "Microsoft.Xbox*", "Microsoft.GamingApp", "Microsoft.AAD*", "Microsoft.AccountsControl", "Microsoft.LockApp",
    "Microsoft.Win32WebViewHost", "Microsoft.*Extension*", "Microsoft.*Extensions", "Microsoft.MicrosoftEdge*",
    "Microsoft.Edge*", "Microsoft.WebView2*", "Microsoft.CredDialogHost", "Microsoft.ECApp", "Microsoft.AsyncTextService",
    "Microsoft.BioEnrollment", "Microsoft.Services.Store*", "Microsoft.StorePurchaseApp", "windows.*",
    "*NVIDIA*", "*Realtek*", "*AdvancedMicroDevices*", "*AMD*", "*Intel*", "*Dolby*", "*Waves*", "*Nahimic*", "*Razer*",
    "*Logitech*", "*Corsair*", "*SteelSeries*", "*ASUS*", "*Armoury*", "*MSI*", "*Lenovo*Vantage*", "*Synaptics*",
]

PROTECTED_WIN32 = re.compile(
    r"visual c\+\+|\.net|windows (driver|sdk|software development)|nvidia|amd |radeon|intel\(r\)|intel |realtek|"
    r"microsoft (edge|update health|windows desktop runtime)|vulkan|directx|physx|java|webview2|steam$|epic games launcher|"
    r"battle\.net|riot|ea app|origin|ubisoft|hellop|pcoptimizer", re.I)

# ---------- Lo que se recomienda quitar (solo se destaca; nunca se marca solo) ----------
OEM_APPX = [
    ("*HPSupportAssistant*", "HP Support Assistant", "Asistente de HP: corre en segundo plano y muestra avisos."),
    ("*HPJumpStarts*", "HP JumpStart", "Promociones y consejos de HP."),
    ("*HPPrivacySettings*", "HP Privacy Settings", "Ajustes de privacidad de HP, no necesarios."),
    ("*HPQuickDrop*", "HP QuickDrop", "Compartir archivos con el móvil (innecesario si no lo usas)."),
    ("*DellSupportAssist*", "Dell SupportAssist", "Diagnóstico de Dell: consume en segundo plano."),
    ("*DellDigitalDelivery*", "Dell Digital Delivery", "Instalador de software de Dell."),
    ("*DellCustomerConnect*", "Dell Customer Connect", "Encuestas y avisos de Dell."),
    ("*McAfee*", "McAfee (prueba)", "Antivirus de prueba que ralentiza el PC. Windows ya trae Defender."),
    ("*Norton*", "Norton (prueba)", "Antivirus de prueba que ralentiza el PC."),
    ("*WildTangent*", "WildTangent Games", "Juegos con anuncios preinstalados."),
    ("*Booking*", "Booking.com", "App patrocinada."),
    ("*ExpressVPN*", "ExpressVPN (prueba)", "VPN de prueba preinstalada."),
]
OEM_WIN32 = re.compile(
    r"mcafee|norton|wildtangent|hp support assistant|hp wolf|hp documentation|hp connection optimizer|dell supportassist|"
    r"dell digital delivery|dell customer connect|acer care center|acer collection|candy crush|booking\.com|"
    r"expressvpn|bing bar|ask toolbar|conduit|babylon", re.I)


def _matches(name, patterns):
    low = name.lower()
    return any(fnmatch.fnmatch(low, p.lower()) for p in patterns)


def is_protected_appx(name):
    return _matches(name, PROTECTED_APPX)


def _recommend_appx(name):
    for pat, title, desc in actions.BLOAT:
        if fnmatch.fnmatch(name.lower(), pat.lower()):
            return title, desc
    for pat, title, desc in OEM_APPX:
        if fnmatch.fnmatch(name.lower(), pat.lower()):
            return title, desc
    return None


# --------------------------------------------------------------------------
# Lectura
# --------------------------------------------------------------------------
def _demo():
    appx = [
        {"name": "Microsoft.BingNews", "title": "Noticias de Microsoft", "why": "App de noticias con anuncios.", "rec": True},
        {"name": "king.com.CandyCrushSaga", "title": "Juegos de King (Candy Crush…)", "why": "Juegos patrocinados preinstalados.", "rec": True},
        {"name": "Microsoft.549981C3F5F10", "title": "Cortana", "why": "Asistente antiguo de Windows.", "rec": True},
        {"name": "Microsoft.ZuneVideo", "title": "Películas y TV", "why": "Reproductor de vídeo de Microsoft.", "rec": True},
        {"name": "Microsoft.Todos", "title": "Microsoft.Todos", "why": "", "rec": False},
        {"name": "Microsoft.YourPhone", "title": "Microsoft.YourPhone", "why": "", "rec": False},
    ]
    win32 = [
        {"name": "McAfee LiveSafe", "publisher": "McAfee, LLC", "size": 410.0, "rec": True},
        {"name": "HP Support Assistant", "publisher": "HP Inc.", "size": 95.0, "rec": True},
        {"name": "7-Zip 23.01", "publisher": "Igor Pavlov", "size": 5.5, "rec": False},
        {"name": "Discord", "publisher": "Discord Inc.", "size": 380.0, "rec": False},
    ]
    return appx, win32


def scan():
    """Devuelve (apps_de_windows, programas). Cada elemento es un dict; 'rec' = lo recomendamos quitar."""
    if DEMO:
        return _demo()
    if not IS_WIN:
        return [], []
    raw = as_list(run_ps_json(
        "ConvertTo-Json -InputObject @(Get-AppxPackage | Where-Object { -not $_.IsFramework -and -not $_.NonRemovable -and "
        "$_.SignatureKind -ne 'System' } | ForEach-Object { [pscustomobject]@{Name=[string]$_.Name} }) -Compress",
        timeout=90, default=[]))
    appx, seen = [], set()
    for d in raw:
        n = str(d.get("Name", ""))
        if not n or n in seen or is_protected_appx(n):
            continue
        seen.add(n)
        r = _recommend_appx(n)
        appx.append({"name": n, "title": r[0] if r else n, "why": r[1] if r else "", "rec": bool(r)})
    appx.sort(key=lambda a: (not a["rec"], a["title"].lower()))

    script = r"""
$k = 'HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\*','HKLM:\SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall\*','HKCU:\SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\*'
$r = @(Get-ItemProperty $k -ErrorAction SilentlyContinue | Where-Object { $_.DisplayName -and $_.UninstallString -and -not $_.SystemComponent -and -not $_.ParentKeyName } |
  ForEach-Object { [pscustomobject]@{Name=[string]$_.DisplayName;Publisher=[string]$_.Publisher;Size=[double]($_.EstimatedSize)} })
ConvertTo-Json -InputObject $r -Compress
"""
    win32, seen = [], set()
    for d in as_list(run_ps_json(script, timeout=90, default=[])):
        n = str(d.get("Name", "")).strip()
        if not n or n.lower() in seen or PROTECTED_WIN32.search(n):
            continue
        seen.add(n.lower())
        size = (d.get("Size") or 0) / 1024.0
        win32.append({"name": n, "publisher": d.get("Publisher", ""), "size": size, "rec": bool(OEM_WIN32.search(n))})
    win32.sort(key=lambda a: (not a["rec"], a["name"].lower()))
    return appx, win32


# --------------------------------------------------------------------------
# Acciones (aparecen en el Historial; no se pueden deshacer desde HellOP)
# --------------------------------------------------------------------------
class AppxRemoveAction(Action):
    group = "bloat"
    reversible = False
    effect = "pequeño"

    def __init__(self, pkg, title=""):
        self.pkg = pkg
        self.id = f"debloat:appx:{pkg}"
        self.title = f"Quitar app de Windows «{title or pkg}»"
        self.desc = "Se puede volver a instalar desde la Microsoft Store."

    def apply(self):
        if DEMO:
            return {"_msg": "(Demo) no se ha quitado nada"}
        if not re.fullmatch(r"[A-Za-z0-9._-]+", self.pkg) or is_protected_appx(self.pkg):
            raise ValueError("Esa app está protegida o su nombre no es válido")
        rc, out, err = run_ps(f"Get-AppxPackage -Name {ps_quote(self.pkg)} | Remove-AppxPackage", timeout=180)
        if rc != 0 and err:
            raise RuntimeError(err[:200])
        return {"pkg": self.pkg}


class Win32UninstallAction(Action):
    group = "bloat"
    reversible = False
    effect = "pequeño"

    def __init__(self, name):
        self.name = name
        self.id = f"debloat:win32:{name}"
        self.title = f"Desinstalar programa «{name}»"
        self.desc = "Se abre el desinstalador del propio programa."

    def apply(self):
        if DEMO:
            return {"_msg": "(Demo) no se ha desinstalado nada"}
        if PROTECTED_WIN32.search(self.name):
            raise ValueError("Ese programa está protegido")
        script = (
            "$k = 'HKLM:\\SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\*','HKLM:\\SOFTWARE\\WOW6432Node\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\*',"
            "'HKCU:\\SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\*'; "
            f"$p = Get-ItemProperty $k -ErrorAction SilentlyContinue | Where-Object {{ $_.DisplayName -eq {ps_quote(self.name)} }} | Select-Object -First 1; "
            "if ($p) { $p.UninstallString } else { '' }")
        rc, out, err = run_ps(script, timeout=30)
        cmd = out.strip()
        if not cmd:
            raise RuntimeError("No encuentro el desinstalador de ese programa")
        subprocess.Popen(cmd, shell=True)       # interactivo: el usuario ve y confirma las pantallas del desinstalador
        return {"name": self.name, "_msg": "Se abrió el desinstalador. Sigue sus pasos para terminar."}
