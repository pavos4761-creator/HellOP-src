"""LIMPIEZA PROFUNDA de Windows + ajustes extra de gaming.

Todo es reversible desde el Historial y cada ajuste explica con honestidad qué hace y qué efecto tiene.
Perfil «deep»: quita telemetría, publicidad, tareas y servicios que Windows ejecuta sin que los pidas.
"""
import json

import psutil

from actions import Action, RegTweak, ServiceAction, REG_DWORD
from util import DEMO, IS_WIN, ps_quote, run_ps, run_ps_json

DEEP = ("deep",)
CDM = r"Software\Microsoft\Windows\CurrentVersion\ContentDeliveryManager"
ADV = r"Software\Microsoft\Windows\CurrentVersion\Explorer\Advanced"


def _t(path, name):
    return (path, name)


# --------------------------------------------------------------------------
# Tareas programadas
# --------------------------------------------------------------------------
class ScheduledTasksAction(Action):
    group = "deep"
    needs_admin = True
    profiles = DEEP

    def __init__(self, id, title, desc, tasks, effect="pequeño", risk="bajo"):
        self.id, self.title, self.desc, self.tasks = id, title, desc, tasks
        self.effect, self.risk = effect, risk

    @staticmethod
    def _list(tasks):
        return "@(" + ",".join(f"@({ps_quote(p)},{ps_quote(n)})" for p, n in tasks) + ")"

    def _states(self):
        script = ("$ErrorActionPreference='SilentlyContinue'; $r=@(); foreach($t in " + self._list(self.tasks) + "){ "
                  "$x=Get-ScheduledTask -TaskPath $t[0] -TaskName $t[1]; if($x){ $r+=[pscustomobject]@{p=$t[0];n=$t[1];s=[string]$x.State} } }; "
                  "ConvertTo-Json -InputObject @($r) -Compress")
        data = run_ps_json(script, timeout=40, default=[])
        data = data if isinstance(data, list) else [data]
        return [(d["p"], d["n"], d["s"]) for d in data if isinstance(d, dict) and "p" in d]

    def check(self):
        on = [x for x in self._states() if x[2] != "Disabled"]
        return f"{len(on)} tarea(s) programada(s) activa(s)" if on else None

    def apply(self):
        on = [(p, n) for p, n, s in self._states() if s != "Disabled"]
        if not on:
            return {"tasks": []}
        script = "$ErrorActionPreference='Stop'; foreach($t in " + self._list(on) + "){ Disable-ScheduledTask -TaskPath $t[0] -TaskName $t[1] | Out-Null }"
        rc, out, err = run_ps(script, timeout=60)
        if rc != 0:
            raise RuntimeError(err or out or "No se pudieron desactivar las tareas (¿administrador?)")
        return {"tasks": on}

    @classmethod
    def undo_data(cls, data):
        tasks = [tuple(t) for t in data.get("tasks", [])]
        if tasks:
            run_ps("$ErrorActionPreference='SilentlyContinue'; foreach($t in " + cls._list(tasks) + "){ Enable-ScheduledTask -TaskPath $t[0] -TaskName $t[1] | Out-Null }", timeout=60)


APPEXP = "\\Microsoft\\Windows\\Application Experience\\"
CEIP = "\\Microsoft\\Windows\\Customer Experience Improvement Program\\"


def task_actions():
    return [
        ScheduledTasksAction("dc_task_telemetry", "Desactivar las tareas de telemetría y compatibilidad de Windows",
                             "Windows lanza tareas que recogen datos de uso y de programas instalados (Compatibility Appraiser, ProgramDataUpdater, "
                             "Customer Experience Program). Aparecen de golpe y consumen disco y CPU, a veces en plena partida. Desactivarlas "
                             "no afecta a nada que uses.",
                             [_t(APPEXP, "Microsoft Compatibility Appraiser"), _t(APPEXP, "ProgramDataUpdater"),
                              _t(APPEXP, "StartupAppTask"), _t(CEIP, "Consolidator"), _t(CEIP, "UsbCeip"),
                              _t(CEIP, "KernelCeipTask"), _t("\\Microsoft\\Windows\\Autochk\\", "Proxy")],
                             effect="real"),
        ScheduledTasksAction("dc_task_diag", "Desactivar tareas de diagnóstico, opiniones y mapas",
                             "Tareas de informes de errores, recogida de datos de disco, encuestas de opinión y actualización de mapas. "
                             "Son ruido de fondo que se activa solo.",
                             [_t("\\Microsoft\\Windows\\Windows Error Reporting\\", "QueueReporting"),
                              _t("\\Microsoft\\Windows\\DiskDiagnostic\\", "Microsoft-Windows-DiskDiagnosticDataCollector"),
                              _t("\\Microsoft\\Windows\\Feedback\\Siuf\\", "DmClient"),
                              _t("\\Microsoft\\Windows\\Feedback\\Siuf\\", "DmClientOnScenarioDownload"),
                              _t("\\Microsoft\\Windows\\Maps\\", "MapsUpdateTask"), _t("\\Microsoft\\Windows\\Maps\\", "MapsToastTask")]),
    ]


# --------------------------------------------------------------------------
# Registro: publicidad, seguimiento y funciones de IA
# --------------------------------------------------------------------------
def registry_deep():
    cdm = [("HKCU", CDM, k, 0, REG_DWORD) for k in (
        "ContentDeliveryAllowed", "OemPreInstalledAppsEnabled", "PreInstalledAppsEnabled", "PreInstalledAppsEverEnabled",
        "SilentInstalledAppsEnabled", "SoftLandingEnabled", "SystemPaneSuggestionsEnabled", "RotatingLockScreenOverlayEnabled",
        "SubscribedContentEnabled", "SubscribedContent-310093Enabled", "SubscribedContent-338387Enabled",
        "SubscribedContent-338388Enabled", "SubscribedContent-338389Enabled", "SubscribedContent-338393Enabled",
        "SubscribedContent-353694Enabled", "SubscribedContent-353696Enabled", "SubscribedContent-353698Enabled")]
    d = DEEP
    return [
        RegTweak("dc_ads", "deep", "Quitar publicidad, apps patrocinadas y sugerencias de Windows",
                 "Windows instala solo apps patrocinadas (Candy Crush, TikTok…), te muestra consejos en el menú Inicio, en la pantalla de bloqueo "
                 "y en el Explorador, y usa un identificador publicitario. Esto lo apaga todo. Menos procesos y menos ruido.",
                 cdm + [("HKCU", r"Software\Microsoft\Windows\CurrentVersion\AdvertisingInfo", "Enabled", 0, REG_DWORD),
                        ("HKCU", r"Software\Microsoft\Windows\CurrentVersion\Privacy", "TailoredExperiencesWithDiagnosticDataEnabled", 0, REG_DWORD),
                        ("HKCU", ADV, "ShowSyncProviderNotifications", 0, REG_DWORD),
                        ("HKCU", ADV, "Start_IrisRecommendations", 0, REG_DWORD)],
                 profiles=d, effect="pequeño"),
        RegTweak("dc_activity", "deep", "Desactivar el historial de actividad y el seguimiento de programas",
                 "Windows guarda qué abres y cuándo (Línea de tiempo) y lo sube a tu cuenta. Con esto deja de registrarlo.",
                 [("HKLM", r"SOFTWARE\Policies\Microsoft\Windows\System", "EnableActivityFeed", 0, REG_DWORD),
                  ("HKLM", r"SOFTWARE\Policies\Microsoft\Windows\System", "PublishUserActivities", 0, REG_DWORD),
                  ("HKLM", r"SOFTWARE\Policies\Microsoft\Windows\System", "UploadUserActivities", 0, REG_DWORD),
                  ("HKCU", ADV, "Start_TrackProgs", 0, REG_DWORD)],
                 needs_admin=True, profiles=d, effect="mínimo"),
        RegTweak("dc_wer", "deep", "Desactivar el envío de informes de errores y las encuestas",
                 "Tras un cuelgue Windows prepara y envía un informe, y a veces provoca picos de disco. Se apaga junto con las encuestas de opinión.",
                 [("HKLM", r"SOFTWARE\Microsoft\Windows\Windows Error Reporting", "Disabled", 1, REG_DWORD),
                  ("HKCU", r"Software\Microsoft\Siuf\Rules", "NumberOfSIUFInPeriod", 0, REG_DWORD)],
                 needs_admin=True, profiles=d, effect="pequeño"),
        RegTweak("dc_p2p", "deep", "Quitar el reparto de actualizaciones entre PCs (P2P)",
                 "Por defecto Windows puede usar tu conexión para subir actualizaciones a otros ordenadores de Internet. Con esto solo descarga, "
                 "y no te roba ancho de banda mientras juegas online.",
                 [("HKLM", r"SOFTWARE\Policies\Microsoft\Windows\DeliveryOptimization", "DODownloadMode", 0, REG_DWORD)],
                 needs_admin=True, profiles=d, effect="real"),
        RegTweak("dc_ai", "deep", "Desactivar Copilot y Recall (funciones de IA de Windows)",
                 "Quita Copilot de la barra y evita que Recall haga capturas de tu pantalla para analizarlas. Menos procesos y más privacidad. "
                 "Si tu Windows no los tiene, no se ofrece.",
                 [("HKCU", r"Software\Policies\Microsoft\Windows\WindowsCopilot", "TurnOffWindowsCopilot", 1, REG_DWORD),
                  ("HKLM", r"SOFTWARE\Policies\Microsoft\Windows\WindowsAI", "DisableAIDataAnalysis", 1, REG_DWORD)],
                 needs_admin=True, profiles=d, effect="pequeño"),
        RegTweak("dc_search", "deep", "Quitar Bing y Cortana de la búsqueda del menú Inicio",
                 "Cada vez que escribes en Inicio, Windows envía lo que tecleas a Bing y carga resultados de internet. Esto deja la búsqueda "
                 "solo local: más rápida y privada.",
                 [("HKCU", r"Software\Policies\Microsoft\Windows\Explorer", "DisableSearchBoxSuggestions", 1, REG_DWORD),
                  ("HKCU", r"Software\Microsoft\Windows\CurrentVersion\Search", "BingSearchEnabled", 0, REG_DWORD),
                  ("HKLM", r"SOFTWARE\Policies\Microsoft\Windows\Windows Search", "AllowCortana", 0, REG_DWORD)],
                 needs_admin=True, profiles=d, effect="pequeño"),
        RegTweak("dc_edge", "deep", "Edge: que no se ejecute en segundo plano",
                 "Edge se queda cargado y precarga páginas aunque no lo uses (consume RAM y CPU). Esto lo detiene: se abre igual cuando lo lanzas.",
                 [("HKLM", r"SOFTWARE\Policies\Microsoft\Edge", "StartupBoostEnabled", 0, REG_DWORD),
                  ("HKLM", r"SOFTWARE\Policies\Microsoft\Edge", "BackgroundModeEnabled", 0, REG_DWORD)],
                 needs_admin=True, profiles=d, effect="real"),
        RegTweak("dc_remote", "deep", "Desactivar la asistencia remota de Windows",
                 "Impide que otra persona pida conectarse a tu PC mediante Asistencia remota. Si no la usas, es una puerta menos.",
                 [("HKLM", r"SYSTEM\CurrentControlSet\Control\Remote Assistance", "fAllowToGetHelp", 0, REG_DWORD)],
                 needs_admin=True, profiles=d, effect="mínimo"),
    ]


# --------------------------------------------------------------------------
# Servicios
# --------------------------------------------------------------------------
DEEP_SERVICES = [
    ("NvTelemetryContainer", "Telemetría de NVIDIA", "Envía datos de uso de tu driver a NVIDIA. Los juegos y el panel funcionan igual sin él.", "bajo", "pequeño"),
    ("TrkWks", "Seguimiento de vínculos distribuidos", "Mantiene vínculos de archivos entre PCs de una red de empresa. En casa no hace nada.", "bajo", "mínimo"),
    ("RemoteRegistry", "Registro remoto", "Permite editar el registro de tu PC desde otro equipo de la red. Desactivarlo es más seguro.", "bajo", "mínimo"),
    ("WpcMonSvc", "Control parental", "Solo hace falta si usas el control parental de Microsoft.", "bajo", "mínimo"),
    ("PhoneSvc", "Servicio de teléfono", "Enlaza tu PC con tu móvil (Vincular con el teléfono). Si no lo usas, sobra.", "bajo", "mínimo"),
    ("icssvc", "Zona con cobertura móvil", "Comparte la conexión de tu PC como punto de acceso WiFi. Si no lo usas, sobra.", "bajo", "mínimo"),
]


def service_deep():
    return [ServiceAction(n, t, d, profiles=DEEP, risk=r, effect=e) for n, t, d, r, e in DEEP_SERVICES]


# --------------------------------------------------------------------------
# Ajustes extra de gaming (perfil Extremo)
# --------------------------------------------------------------------------
class DefenderExclusionAction(Action):
    id, group = "dc_defender", "tradeoff"
    title = "Excluir tus carpetas de juegos del análisis en tiempo real del antivirus"
    desc = ("Windows Defender analiza cada archivo que el juego lee del disco. En juegos que cargan mucho (mundos abiertos, texturas) eso causa "
            "tirones y cargas más lentas. Con la exclusión, Defender no analiza esas carpetas. SOLO se usan las carpetas de los juegos de tu biblioteca "
            "(pestaña Mis juegos).")
    needs_admin = True
    profiles = ("extreme",)
    risk = "medio"
    effect = "depende"
    warning = "Esas carpetas dejan de analizarse en busca de virus. Hazlo solo con juegos de Steam/Epic oficiales, nunca con descargas de dudosa procedencia."

    def _paths(self):
        import games
        return [g["path"] for g in games.load()["games"] if g.get("path")]

    def check(self):
        if not IS_WIN and not DEMO:
            return None
        paths = self._paths()
        if not paths:
            return None
        if DEMO:
            return f"{len(paths)} carpeta(s) de juegos sin excluir"
        cur = run_ps_json("ConvertTo-Json -InputObject @((Get-MpPreference).ExclusionPath) -Compress", timeout=30, default=[])
        cur = {str(p).lower().rstrip("\\") for p in (cur if isinstance(cur, list) else [cur]) if p}
        missing = [p for p in paths if p.lower().rstrip("\\") not in cur]
        return f"{len(missing)} carpeta(s) de juegos sin excluir" if missing else None

    def apply(self):
        cur = run_ps_json("ConvertTo-Json -InputObject @((Get-MpPreference).ExclusionPath) -Compress", timeout=30, default=[])
        cur = {str(p).lower().rstrip("\\") for p in (cur if isinstance(cur, list) else [cur]) if p}
        missing = [p for p in self._paths() if p.lower().rstrip("\\") not in cur]
        for p in missing:
            rc, out, err = run_ps(f"Add-MpPreference -ExclusionPath {ps_quote(p)}", timeout=30)
            if rc != 0:
                raise RuntimeError(err or out or "Defender no aceptó la exclusión (¿hay otro antivirus?)")
        return {"paths": missing}

    @classmethod
    def undo_data(cls, d):
        for p in d.get("paths", []):
            run_ps(f"Remove-MpPreference -ExclusionPath {ps_quote(p)}", timeout=30)


def svchost_action():
    kb = min(int(psutil.virtual_memory().total // 1024), 0xFFFFFFFF)
    return RegTweak("dc_svchost", "latency", "Agrupar servicios de Windows en menos procesos (svchost)",
                    "Windows separa cada servicio en su propio proceso svchost.exe (decenas de procesos). Con este valor se agrupan como en versiones "
                    "antiguas: menos procesos, menos RAM y menos cambios de contexto. El efecto es pequeño pero real en PCs con mucha RAM.",
                    [("HKLM", r"SYSTEM\CurrentControlSet\Control", "SvcHostSplitThresholdInKB", kb, REG_DWORD)],
                    needs_admin=True, profiles=("extreme",), effect="pequeño", reboot=True)


def extra_gaming_actions():
    return [svchost_action(), DefenderExclusionAction()]


# --------------------------------------------------------------------------
def deep_actions():
    return task_actions() + registry_deep() + service_deep()
