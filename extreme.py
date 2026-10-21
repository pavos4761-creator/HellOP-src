"""Ajustes EXTREMOS para gaming y latencia mínima.

Todos son reversibles (se guarda el valor anterior) y cada uno dice con honestidad
qué efecto tiene de verdad:
    real     = se mide o se nota en la mayoría de equipos
    pequeño  = efecto real pero difícil de notar
    depende  = ayuda en unos equipos/juegos y no en otros
    mínimo   = prácticamente nulo en juegos modernos (se ofrece por completitud)
"""
import re

import psutil

import os

from actions import Action, RegTweak, active_scheme, reg_read, REG_BINARY, REG_DWORD, REG_SZ
from util import as_list, ps_quote, run_cmd, run_ps, run_ps_json

K_PRIO = r"SYSTEM\CurrentControlSet\Control\PriorityControl"
K_POWER_THR = r"SYSTEM\CurrentControlSet\Control\Power\PowerThrottling"
K_KERNEL = r"SYSTEM\CurrentControlSet\Control\Session Manager\kernel"
K_MEM = r"SYSTEM\CurrentControlSet\Control\Session Manager\Memory Management"
K_DEVGUARD = r"SYSTEM\CurrentControlSet\Control\DeviceGuard"
K_HVCI = K_DEVGUARD + r"\Scenarios\HypervisorEnforcedCodeIntegrity"


def windows_build():
    cur = reg_read("HKLM", r"SOFTWARE\Microsoft\Windows NT\CurrentVersion", "CurrentBuildNumber")
    try:
        return int(cur[0])
    except (TypeError, ValueError):
        return 0


def on_desktop():
    return psutil.sensors_battery() is None


# --------------------------------------------------------------------------
# Ajustes de energía avanzados (powercfg)
# --------------------------------------------------------------------------
class PowerSettingAction(Action):
    group = "latency"
    needs_admin = True
    profiles = ("extreme",)

    def __init__(self, id, title, desc, sub, setting, value, effect="", risk="bajo",
                 desktop_only=False, warning=""):
        self.id, self.title, self.desc = id, title, desc
        self.sub, self.setting, self.value = sub, setting, value
        self.effect, self.risk, self.desktop_only, self.warning = effect, risk, desktop_only, warning

    def _current(self, scheme="SCHEME_CURRENT"):
        rc, out, _ = run_cmd(["powercfg", "/q", scheme, self.sub, self.setting])
        nums = re.findall(r"0x[0-9a-fA-F]{8}", out)
        return int(nums[-2], 16) if rc == 0 and len(nums) >= 2 else None

    def check(self):
        if self.desktop_only and not on_desktop():
            return None
        cur = self._current()
        if cur is None or cur == self.value:
            return None
        return f"Valor actual: {cur}  →  nuevo: {self.value}"

    def apply(self):
        guid, _name = active_scheme()
        prev = self._current(guid or "SCHEME_CURRENT")
        target = guid or "SCHEME_CURRENT"
        desktop = on_desktop()
        for cmd in (["/setacvalueindex"] + ([] if not desktop else ["/setdcvalueindex"])):
            rc, out, err = run_cmd(["powercfg", cmd, target, self.sub, self.setting, str(self.value)])
            if rc != 0:
                raise RuntimeError(err or out or "powercfg falló")
        run_cmd(["powercfg", "/setactive", target])
        return {"scheme": target, "sub": self.sub, "setting": self.setting, "prev": prev, "dc": desktop}

    @classmethod
    def undo_data(cls, d):
        if d.get("prev") is None:
            return
        run_cmd(["powercfg", "/setacvalueindex", d["scheme"], d["sub"], d["setting"], str(d["prev"])])
        if d.get("dc"):
            run_cmd(["powercfg", "/setdcvalueindex", d["scheme"], d["sub"], d["setting"], str(d["prev"])])
        run_cmd(["powercfg", "/setactive", d["scheme"]])


SUB_PROC = "54533251-82be-4824-96c1-47b60b740d00"
SUB_PCIE = "501a4d13-42af-4429-9fd1-a8218c268e20"
SUB_USB = "2a737441-1930-4402-8d77-b2bebba308a3"


def power_actions():
    return [
        PowerSettingAction("pw_minproc", "Procesador siempre al 100 % (sin bajar de frecuencia)",
                           "El estado mínimo del procesador pasa de ~5 % a 100 %: la CPU no «despierta» de un modo de ahorro "
                           "cuando le pides trabajo. Menos micro-tirones y respuesta inmediata. A cambio gasta más energía y calienta algo más.",
                           SUB_PROC, "893dee8e-2bef-41e0-89c6-b55d0929964c", 100, effect="real", risk="medio", desktop_only=True),
        PowerSettingAction("pw_parking", "Sin aparcar núcleos de la CPU",
                           "Windows aparca (apaga) núcleos que cree inactivos y tarda en despertarlos. Con 100 % todos los núcleos están siempre listos.",
                           SUB_PROC, "0cc5b647-c1df-4637-891a-dec35c318583", 100, effect="depende", desktop_only=True),
        PowerSettingAction("pw_boost", "Boost del procesador agresivo",
                           "La CPU sube a su frecuencia turbo más rápido y con más frecuencia. Más rendimiento instantáneo, más calor.",
                           SUB_PROC, "be337238-0d82-4146-a960-4f3749d470c7", 2, effect="pequeño", risk="medio", desktop_only=True),
        PowerSettingAction("pw_idle", "Desactivar los estados de reposo de la CPU (C-states de Windows)",
                           "Impide que la CPU entre en reposo profundo entre tareas, así reacciona sin retardo de despertar. "
                           "LOCURA: aumenta consumo en reposo (30-60 W más) y temperatura. Solo para PC de sobremesa con buena refrigeración.",
                           SUB_PROC, "5d76a2ca-e8c0-402f-a133-2158492d58ad", 1, effect="pequeño", risk="medio", desktop_only=True,
                           warning="Más calor y consumo constantes. Revisa temperaturas después. Se deshace desde el Historial."),
        PowerSettingAction("pw_pcie", "Sin ahorro de energía en el bus PCIe (gráfica y NVMe)",
                           "Evita que el enlace PCI Express de tu gráfica y tu SSD NVMe baje de velocidad para ahorrar energía y luego tarde en volver.",
                           SUB_PCIE, "ee12f906-d277-404b-b6da-e5fa1a576df5", 0, effect="pequeño"),
        PowerSettingAction("pw_usb", "Sin suspensión selectiva de USB",
                           "Evita que Windows duerma puertos USB: tu ratón y teclado nunca tienen que «despertar» y no hay micro-cortes.",
                           SUB_USB, "48e6b7a6-50f5-4782-a5d4-53bb8f07e226", 0, effect="pequeño"),
    ]


# --------------------------------------------------------------------------
# Arranque (bcdedit)
# --------------------------------------------------------------------------
class BcdAction(Action):
    group = "latency"
    needs_admin = True
    reboot = True
    profiles = ("extreme",)

    def __init__(self, id, title, desc, key, value, only_if_present=False, effect="", risk="medio", warning=""):
        self.id, self.title, self.desc = id, title, desc
        self.key, self.value = key, value          # value None = quitar el valor
        self.only_if_present = only_if_present
        self.effect, self.risk, self.warning = effect, risk, warning

    def _get(self):
        rc, out, _ = run_cmd(["bcdedit", "/enum", "{current}"])
        m = re.search(rf"^{re.escape(self.key)}\s+(.+)$", out, re.M | re.I)
        if not m:
            return None
        v = m.group(1).strip().lower()
        return {"sí": "yes", "si": "yes"}.get(v, v)

    def check(self):
        cur = self._get()
        if self.value is None:
            return None if cur is None else f"{self.key}: {cur}  →  (quitar)"
        if self.only_if_present and cur is None:
            return None
        if cur == self.value.lower():
            return None
        return f"{self.key}: {cur or 'por defecto'}  →  {self.value}"

    def apply(self):
        prev = self._get()
        args = ["bcdedit", "/deletevalue", self.key] if self.value is None else ["bcdedit", "/set", self.key, self.value]
        rc, out, err = run_cmd(args)
        if rc != 0:
            raise RuntimeError(out or err or "bcdedit falló (¿Secure Boot o BitLocker lo bloquean?)")
        return {"key": self.key, "prev": prev}

    @classmethod
    def undo_data(cls, d):
        if d.get("prev") is None:
            run_cmd(["bcdedit", "/deletevalue", d["key"]])
        else:
            run_cmd(["bcdedit", "/set", d["key"], d["prev"]])


def bcd_actions():
    return [
        BcdAction("bcd_hpet", "Quitar el temporizador HPET forzado",
                  "Tu Windows tiene forzado el reloj HPET (useplatformclock), mucho más lento de leer que el reloj interno de la CPU. "
                  "Quitarlo baja la latencia de todo el sistema y mejora los mínimos de FPS.",
                  "useplatformclock", None, effect="real", risk="bajo"),
        BcdAction("bcd_dyntick", "Desactivar el «tick dinámico»",
                  "Windows apaga el reloj del sistema cuando no hace falta para ahorrar energía. Con el tick fijo el planificador "
                  "responde con más regularidad. En portátiles gasta algo más de batería.",
                  "disabledynamictick", "yes", effect="depende", risk="medio"),
    ]



# --------------------------------------------------------------------------
# Más ajustes de Windows (hibernación, NTFS)
# --------------------------------------------------------------------------
class HibernateAction(Action):
    group = "speed"
    needs_admin = True
    profiles = ("gaming", "work", "extreme")
    effect = "mínimo"
    id = "x_hibernate"
    title = "Desactivar la hibernación (libera el archivo hiberfil.sys)"
    desc = ("Windows reserva en tu disco un archivo del tamaño de ~40-75 % de tu RAM para hibernar (varios GB). Si no hibernas, "
            "desactivarlo libera ese espacio y también desactiva el inicio rápido. No cambia los FPS; sí te da espacio y arranques limpios.")

    def check(self):
        path = os.path.join(os.environ.get("SystemDrive", "C:") + os.sep, "hiberfil.sys")
        return "Archivo hiberfil.sys presente" if os.path.exists(path) else None

    def apply(self):
        rc, out, err = run_cmd(["powercfg", "/h", "off"])
        if rc != 0:
            raise RuntimeError(out or err or "powercfg /h off falló")
        return {}

    @classmethod
    def undo_data(cls, d):
        run_cmd(["powercfg", "/h", "on"])


class FsutilAction(Action):
    group = "speed"
    needs_admin = True
    profiles = ("gaming", "work", "extreme")
    effect = "mínimo"
    id = "x_lastaccess"
    title = "NTFS: no anotar la fecha de «último acceso» en cada archivo"
    desc = ("Cada vez que lees un archivo Windows puede escribir en el disco la fecha de acceso. Desactivarlo evita esas escrituras "
            "(útil sobre todo en discos mecánicos y con muchos archivos pequeños). Apenas se nota en un SSD moderno.")

    def _get(self):
        rc, out, _ = run_cmd(["fsutil", "behavior", "query", "disablelastaccess"])
        m = re.search(r"=\s*(\d)", out)
        return int(m.group(1)) if rc == 0 and m else None

    def check(self):
        cur = self._get()
        return None if cur is None or cur in (1, 3) else f"DisableLastAccess = {cur}  →  1"

    def apply(self):
        prev = self._get()
        rc, out, err = run_cmd(["fsutil", "behavior", "set", "disablelastaccess", "1"])
        if rc != 0:
            raise RuntimeError(out or err or "fsutil falló")
        return {"prev": prev}

    @classmethod
    def undo_data(cls, d):
        if d.get("prev") is not None:
            run_cmd(["fsutil", "behavior", "set", "disablelastaccess", str(d["prev"])])


# --------------------------------------------------------------------------
# Registro profundo
# --------------------------------------------------------------------------
class BuildGatedTweak(RegTweak):
    """Solo se ofrece en Windows 11 (compilación ≥ 22000)."""

    def check(self):
        return None if windows_build() < 22000 else super().check()


class VbsTweak(RegTweak):
    """Solo se ofrece si VBS está funcionando de verdad."""

    def check(self):
        out = run_ps("(Get-CimInstance -ClassName Win32_DeviceGuard -Namespace root\\Microsoft\\Windows\\DeviceGuard "
                     "-ErrorAction SilentlyContinue).VirtualizationBasedSecurityStatus")[1].strip()
        if out != "2":
            return None
        return "VBS / Integridad de memoria: ACTIVA"


def registry_actions():
    ex = ("extreme",)
    return [
        RegTweak("x_prio_sep", "latency", "Prioridad máxima al programa en primer plano",
                 "Cambia cómo Windows reparte el tiempo de CPU: tu juego en primer plano recibe porciones más largas y prioritarias "
                 "frente a lo que haya detrás (Win32PrioritySeparation = 38).",
                 [("HKLM", K_PRIO, "Win32PrioritySeparation", 38, REG_DWORD)],
                 needs_admin=True, profiles=ex, effect="pequeño"),
        RegTweak("x_power_throttle", "latency", "Desactivar el «throttling» de energía de procesos",
                 "Windows reduce la velocidad de procesos que cree de fondo (EcoQoS). En CPUs híbridas (Intel 12ª gen o más) "
                 "puede mandar tu juego a los núcleos eficientes. Esto lo evita.",
                 [("HKLM", K_POWER_THR, "PowerThrottlingOff", 1, REG_DWORD)],
                 needs_admin=True, profiles=ex, effect="depende", reboot=True),
        BuildGatedTweak("x_timer", "latency", "Resolución de temporizador global (Windows 11)",
                        "Desde Windows 11 los programas ya no comparten la resolución del reloj. Esto restaura el comportamiento "
                        "clásico: si un juego (o el Modo Extremo en vivo) pide 0,5 ms, vale para todo el sistema.",
                        [("HKLM", K_KERNEL, "GlobalTimerResolutionRequests", 1, REG_DWORD)],
                        needs_admin=True, profiles=ex, effect="real", reboot=True),
        RegTweak("x_fso", "latency", "Desactivar optimizaciones de pantalla completa",
                 "Quita la capa «fullscreen optimizations» de Windows para que los juegos controlen la pantalla directamente. "
                 "Ayuda en juegos antiguos y algunos con tirones; en juegos modernos puede no cambiar nada.",
                 [("HKCU", r"System\GameConfigStore", "GameDVR_FSEBehaviorMode", 2, REG_DWORD),
                  ("HKCU", r"System\GameConfigStore", "GameDVR_HonorUserFSEBehaviorMode", 1, REG_DWORD),
                  ("HKCU", r"System\GameConfigStore", "GameDVR_FSEBehavior", 2, REG_DWORD),
                  ("HKCU", r"System\GameConfigStore", "GameDVR_DXGIHonorFSEWindowsCompatible", 1, REG_DWORD)],
                 profiles=ex, effect="depende"),
        RegTweak("x_mpo", "latency", "Desactivar Multiplane Overlay (MPO)",
                 "Arregla tirones, parpadeos y pantallazos negros en algunas gráficas al usar varias ventanas con juegos. "
                 "Si no tienes esos problemas, no cambia nada.",
                 [("HKLM", r"SOFTWARE\Microsoft\Windows\Dwm", "OverlayTestMode", 5, REG_DWORD)],
                 needs_admin=True, profiles=ex, effect="depende", reboot=True, risk="medio"),
        RegTweak("x_bgapps", "latency", "Apps en segundo plano: apagadas",
                 "Impide que las apps de la Tienda sigan funcionando en segundo plano consumiendo CPU, RAM y red.",
                 [("HKCU", r"Software\Microsoft\Windows\CurrentVersion\BackgroundAccessApplications", "GlobalUserDisabled", 1, REG_DWORD),
                  ("HKCU", r"Software\Microsoft\Windows\CurrentVersion\Search", "BackgroundAppGlobalToggle", 0, REG_DWORD)],
                 profiles=ex, effect="pequeño"),

        RegTweak("x_visualfx", "speed", "Efectos visuales: «Ajustar para obtener el mejor rendimiento»",
                 "Equivale a marcar «Mejor rendimiento» en Opciones de rendimiento de Windows: sin animaciones, sombras, desvanecimientos ni "
                 "vista previa de ventanas. Interfaz seca pero más ágil y menos carga para la GPU/DWM. Mantiene el texto suave (ClearType). "
                 "Se aplica del todo al cerrar sesión.",
                 [("HKCU", r"Software\Microsoft\Windows\CurrentVersion\Explorer\VisualEffects", "VisualFXSetting", 2, REG_DWORD),
                  ("HKCU", r"Control Panel\Desktop", "UserPreferencesMask", bytes([0x90, 0x12, 0x03, 0x80, 0x10, 0x00, 0x00, 0x00]), REG_BINARY),
                  ("HKCU", r"Control Panel\Desktop", "DragFullWindows", "0", REG_SZ),
                  ("HKCU", r"Control Panel\Desktop\WindowMetrics", "MinAnimate", "0", REG_SZ),
                  ("HKCU", r"Software\Microsoft\Windows\CurrentVersion\Explorer\Advanced", "ListviewAlphaSelect", 0, REG_DWORD),
                  ("HKCU", r"Software\Microsoft\Windows\CurrentVersion\Explorer\Advanced", "ListviewShadow", 0, REG_DWORD),
                  ("HKCU", r"Software\Microsoft\Windows\CurrentVersion\Explorer\Advanced", "TaskbarAnimations", 0, REG_DWORD),
                  ("HKCU", r"Software\Microsoft\Windows\DWM", "EnableAeroPeek", 0, REG_DWORD)],
                 profiles=("gaming", "work", "extreme"), effect="pequeño", reboot=True),
        RegTweak("x_faststart", "speed", "Apagado completo (sin «inicio rápido»)",
                 "El inicio rápido de Windows guarda parte del sistema al apagar y lo restaura al encender. Eso arrastra drivers y estados "
                 "viejos de una sesión a otra. Desactivarlo hace que cada arranque sea limpio (puede tardar unos segundos más en arrancar).",
                 [("HKLM", r"SYSTEM\CurrentControlSet\Control\Session Manager\Power", "HiberbootEnabled", 0, REG_DWORD)],
                 needs_admin=True, profiles=ex, effect="depende", reboot=True),
        BuildGatedTweak("x_widgets", "speed", "Quitar Widgets y Copilot (Windows 11)",
                        "Widgets y Copilot mantienen procesos en segundo plano (WebView) que gastan RAM y red aunque no los uses. "
                        "Con este ajuste Windows los deshabilita por directiva.",
                        [("HKLM", r"SOFTWARE\Policies\Microsoft\Dsh", "AllowNewsAndInterests", 0, REG_DWORD),
                         ("HKCU", r"Software\Policies\Microsoft\Windows\WindowsCopilot", "TurnOffWindowsCopilot", 1, REG_DWORD)],
                        needs_admin=True, profiles=ex, effect="pequeño", reboot=True),
        RegTweak("x_telemetry", "speed", "Telemetría al mínimo y sin anuncios personalizados",
                 "Reduce el envío de datos de diagnóstico a Microsoft al mínimo que permite tu edición y apaga el ID de publicidad y las "
                 "notificaciones de opiniones. Menos actividad en segundo plano. En Windows Home el mínimo que acepta es «Requerido».",
                 [("HKLM", r"SOFTWARE\Policies\Microsoft\Windows\DataCollection", "AllowTelemetry", 0, REG_DWORD),
                  ("HKLM", r"SOFTWARE\Policies\Microsoft\Windows\DataCollection", "DoNotShowFeedbackNotifications", 1, REG_DWORD),
                  ("HKCU", r"Software\Microsoft\Windows\CurrentVersion\AdvertisingInfo", "Enabled", 0, REG_DWORD)],
                 needs_admin=True, profiles=ex, effect="mínimo"),
        RegTweak("x_mitig", "tradeoff", "Desactivar las mitigaciones de CPU (Spectre/Meltdown)",
                 "Quita los parches que protegen contra ataques de canal lateral a la CPU. Recupera rendimiento sobre todo en CPUs "
                 "antiguas (Intel hasta la 8ª gen. y similares); en CPUs recientes la ganancia es pequeña porque ya lo hacen por hardware.",
                 [("HKLM", K_MEM, "FeatureSettingsOverride", 3, REG_DWORD),
                  ("HKLM", K_MEM, "FeatureSettingsOverrideMask", 3, REG_DWORD)],
                 needs_admin=True, profiles=ex, effect="depende", reboot=True, risk="alto",
                 warning="Reduce la protección frente a ataques que roban datos de la memoria (principalmente desde web/programas maliciosos). "
                         "Hazlo solo si este PC es sobre todo para jugar y no guardas datos sensibles."),
        VbsTweak("x_vbs", "tradeoff", "Desactivar VBS / Integridad de memoria (HVCI)",
                 "Windows 11 ejecuta tu sistema dentro de un mini-hipervisor de seguridad (VBS). Eso cuesta rendimiento: entre un 5 % y un 15 % de FPS "
                 "en algunos juegos, según CPU y juego. Desactivarlo es de lo que más se nota en este modo.",
                 [("HKLM", K_DEVGUARD, "EnableVirtualizationBasedSecurity", 0, REG_DWORD),
                  ("HKLM", K_HVCI, "Enabled", 0, REG_DWORD)],
                 needs_admin=True, profiles=ex, effect="real", reboot=True, risk="alto",
                 warning="Baja la protección contra malware que ataca el núcleo de Windows y bloquea drivers vulnerables. "
                         "Algunos anti-cheat modernos (por ejemplo Vanguard) exigen VBS/TPM: si juegas a esos, NO lo desactives."),
    ]


# --------------------------------------------------------------------------
# Servicios extra (uno por uno)
# --------------------------------------------------------------------------
EXTREME_SERVICES = [
    ("WSearch", "Windows Search (indexador)",
     "Indexa tus archivos en segundo plano para que la búsqueda sea rápida. Sin él, buscar archivos tarda más pero baja el uso de disco y CPU.", "bajo", "pequeño"),
    ("DoSvc", "Optimización de entrega",
     "Comparte partes de actualizaciones con otros PC por Internet usando tu conexión. No lo necesitas.", "bajo", "pequeño"),
    ("lfsvc", "Servicio de ubicación", "Geolocalización para apps. Si no usas el Tiempo o mapas con tu ubicación, sobra.", "bajo", "mínimo"),
    ("PcaSvc", "Asistente de compatibilidad de programas",
     "Vigila programas antiguos para sugerir ajustes de compatibilidad. Consume un poco al abrir programas.", "bajo", "mínimo"),
    ("XblAuthManager", "Xbox Live: autenticación",
     "Solo hace falta para juegos de Xbox / Game Pass / Microsoft Store con inicio de sesión Xbox. SI JUEGAS A ESOS, NO LO DESACTIVES.", "medio", "mínimo"),
    ("XblGameSave", "Xbox Live: partidas guardadas en la nube",
     "Sincroniza partidas de juegos de Xbox. Si no usas juegos de Xbox, sobra.", "medio", "mínimo"),
    ("XboxNetApiSvc", "Xbox Live: red", "Complemento de red de Xbox. Solo útil con juegos de Xbox.", "medio", "mínimo"),
    ("Spooler", "Cola de impresión", "Necesario para imprimir. Si no tienes impresora o la usas poco, puedes desactivarlo y volver a activarlo desde el Historial.", "medio", "pequeño"),
]


def service_extra_actions():
    from actions import ServiceAction
    return [ServiceAction(n, t, d, profiles=("extreme",), risk=r, effect=e) for n, t, d, r, e in EXTREME_SERVICES]


# --------------------------------------------------------------------------
# Hardware: tarjeta de red y gráfica
# --------------------------------------------------------------------------
_NIC_SCRIPT = r"""
$ErrorActionPreference='SilentlyContinue'
$r=@()
foreach($a in @(Get-NetAdapter -Physical | Where-Object Status -eq 'Up')){
  foreach($p in @(Get-NetAdapterAdvancedProperty -Name $a.Name)){
    if($p.DisplayName -match 'Energy.Efficient|Green Ethernet|Power Saving|Ultra Low Power|Gigabit Lite|Interrupt Moderation|Eficiencia energ|Ahorro de energ|Moderaci'){
      $r += [pscustomobject]@{Adapter=[string]$a.Name;Guid=[string]$a.InterfaceGuid;Display=[string]$p.DisplayName;Keyword=[string]$p.RegistryKeyword;Value=[string](@($p.RegistryValue)[0]);Valid=@($p.ValidRegistryValues | ForEach-Object {[string]$_})}
    }
  }
}
ConvertTo-Json -InputObject @($r) -Compress -Depth 4
"""

_GPU_SCRIPT = r"""
$ErrorActionPreference='SilentlyContinue'
ConvertTo-Json -InputObject @(Get-PnpDevice -Class Display -Status OK | Where-Object { $_.InstanceId -like 'PCI*' } |
  ForEach-Object { [pscustomobject]@{Id=[string]$_.InstanceId;Name=[string]$_.FriendlyName} }) -Compress
"""


class NicPowerAction(Action):
    group = "network"
    needs_admin = True
    profiles = ("extreme",)
    effect = "pequeño"

    def __init__(self, adapter, props):
        self.adapter, self.props = adapter, props   # props: [{Display, Keyword, Value}]
        self.id = f"nic:{adapter}"
        self.title = f"Red sin ahorro de energía: {adapter}"
        names = ", ".join(p["Display"] for p in props)
        self.desc = ("Desactiva en la tarjeta de red lo que añade latencia: " + names + ". "
                     "La red se corta un par de segundos al aplicarlo. Menos latencia y menos «tirones» de ping.")

    def check(self):
        return f"{len(self.props)} ajuste(s) a desactivar"

    def apply(self):
        prev = []
        for p in self.props:
            if not re.fullmatch(r"[A-Za-z0-9_]+", p["Keyword"]):
                continue
            rc, out, err = run_ps(f"Set-NetAdapterAdvancedProperty -Name {ps_quote(self.adapter)} "
                                  f"-RegistryKeyword {ps_quote(p['Keyword'])} -RegistryValue 0 -ErrorAction Stop", timeout=60)
            if rc != 0:
                raise RuntimeError(err or out or "No se pudo cambiar el ajuste de red")
            prev.append({"adapter": self.adapter, "kw": p["Keyword"], "val": p["Value"]})
        return {"prev": prev}

    @classmethod
    def undo_data(cls, d):
        for e in d["prev"]:
            run_ps(f"Set-NetAdapterAdvancedProperty -Name {ps_quote(e['adapter'])} -RegistryKeyword {ps_quote(e['kw'])} "
                   f"-RegistryValue {ps_quote(e['val'])}", timeout=60)


def nic_actions():
    rows = as_list(run_ps_json(_NIC_SCRIPT, timeout=60, default=[]))
    by_adapter = {}
    for r in rows:
        valid = [str(v) for v in as_list(r.get("Valid"))]
        if "0" in valid and str(r.get("Value")) != "0":
            by_adapter.setdefault(r["Adapter"], []).append(r)
    acts = [NicPowerAction(a, props) for a, props in by_adapter.items()]
    guids = sorted({r["Guid"] for r in rows if r.get("Guid")})
    if not guids:
        guids = [g for g in as_list(run_ps_json(
            "ConvertTo-Json -InputObject @(Get-NetAdapter -Physical | Where-Object Status -eq 'Up' | "
            "ForEach-Object { [string]$_.InterfaceGuid }) -Compress", default=[]))]
    if guids:
        base = r"SYSTEM\CurrentControlSet\Services\Tcpip\Parameters\Interfaces"
        changes = []
        for g in guids:
            changes += [("HKLM", f"{base}\\{g}", "TcpAckFrequency", 1, REG_DWORD),
                        ("HKLM", f"{base}\\{g}", "TCPNoDelay", 1, REG_DWORD)]
        acts.append(RegTweak("x_nagle", "network", "Desactivar el algoritmo de Nagle (TCP sin retardos)",
                             "Envía los paquetes TCP al instante en vez de agruparlos. Con juegos que usan UDP (casi todos) el cambio es "
                             "mínimo; ayuda en algunos MMO y juegos con TCP. Se ofrece por completitud.",
                             changes, needs_admin=True, profiles=("extreme",), effect="mínimo"))
    return acts


def gpu_actions():
    acts = []
    for g in as_list(run_ps_json(_GPU_SCRIPT, timeout=40, default=[])):
        path = rf"SYSTEM\CurrentControlSet\Enum\{g['Id']}\Device Parameters\Interrupt Management\MessageSignaledInterruptProperties"
        acts.append(RegTweak(f"x_msi:{g['Id']}", "latency", f"Modo MSI en la gráfica ({g['Name']})",
                             "Cambia cómo la gráfica avisa a la CPU (interrupciones MSI en vez de líneas compartidas): menos latencia y menos "
                             "carga de CPU. Muchos drivers de NVIDIA ya lo traen activado; en ese caso no se ofrece.",
                             [("HKLM", path, "MSISupported", 1, REG_DWORD)],
                             needs_admin=True, profiles=("extreme",), effect="depende", reboot=True, risk="medio"))
    return acts


# --------------------------------------------------------------------------
def extreme_actions():
    acts = power_actions() + bcd_actions() + registry_actions() + service_extra_actions()
    acts += [HibernateAction(), FsutilAction()]
    return acts


def hardware_actions():
    return nic_actions() + gpu_actions()
