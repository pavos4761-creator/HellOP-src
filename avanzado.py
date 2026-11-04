"""Ajustes avanzados del sistema: los que NO salen en el típico vídeo de «optimiza Windows en 5 minutos».
Todos se miden en TU equipo antes de ofrecerse (solo aparece lo que de verdad está sin hacer), se explican con su efecto real
y se pueden deshacer desde «Historial / Deshacer»."""
from actions import REG_DWORD, Action, RegTweak
from util import DEMO, IS_WIN, run_ps, run_ps_json

KERNEL = r"SYSTEM\CurrentControlSet\Control\Session Manager\kernel"
MEMORIA = r"SYSTEM\CurrentControlSet\Control\Session Manager\Memory Management"
MOUCLASS = r"SYSTEM\CurrentControlSet\Services\mouclass\Parameters"
KBDCLASS = r"SYSTEM\CurrentControlSet\Services\kbdclass\Parameters"
EX = ("extreme",)


def _ram_gb():
    try:
        import psutil
        return psutil.virtual_memory().total / 1024 ** 3
    except Exception:  # noqa: BLE001
        return 0.0


def _build():
    try:
        from extreme import windows_build
        return windows_build()
    except Exception:  # noqa: BLE001
        return 0


class _Gated(RegTweak):
    """RegTweak que solo se ofrece si se cumple una condición de tu PC (versión de Windows, cantidad de RAM…)."""
    condicion = staticmethod(lambda: True)

    def check(self):
        return None if not self.condicion() else super().check()


class _Timer(_Gated):
    condicion = staticmethod(lambda: DEMO or _build() >= 22621)


class _Ram16(_Gated):
    condicion = staticmethod(lambda: DEMO or _ram_gb() >= 15.5)


class DefenderLowCpuAction(Action):
    id, group = "av_defender_cpu", "advanced"
    title = "Antivirus de Windows: que sus análisis no te roben CPU mientras juegas"
    desc = ("Defender hace análisis programados y en segundo plano que pueden disparar la CPU y el disco en mitad de una partida. "
            "Esto los pasa a prioridad baja y limita el uso medio de CPU de cada análisis al 20 %. NO desactiva la protección en tiempo real: "
            "sigues igual de protegido, solo que los análisis esperan su turno.")
    needs_admin, reversible, risk, effect, reboot, profiles = True, True, "bajo", "real", False, EX

    def _prefs(self):
        d = run_ps_json("Get-MpPreference -ErrorAction Stop | Select-Object EnableLowCpuPriority,ScanAvgCPULoadFactor | ConvertTo-Json -Compress",
                        timeout=30, default=None)
        return d if isinstance(d, dict) else None

    def check(self):
        if DEMO:
            return "Análisis de Defender: prioridad normal, hasta el 50 % de CPU"
        if not IS_WIN:
            return None
        p = self._prefs()
        if not p or p.get("ScanAvgCPULoadFactor") is None:
            return None                      # Defender no está activo (otro antivirus)
        low, fac = bool(p.get("EnableLowCpuPriority")), int(p.get("ScanAvgCPULoadFactor") or 50)
        if low and fac <= 20:
            return None
        return f"Análisis de Defender: prioridad {'baja' if low else 'normal'}, hasta el {fac} % de CPU"

    def apply(self):
        if DEMO:
            return {"prev": {}, "_msg": "(Demo) análisis en prioridad baja"}
        prev = self._prefs() or {}
        rc, out, err = run_ps("Set-MpPreference -EnableLowCpuPriority $true -ScanAvgCPULoadFactor 20 -ErrorAction Stop", timeout=40)
        if rc != 0:
            raise RuntimeError((err or out or "Defender no dejó cambiarlo")[:150])
        return {"prev": prev, "_msg": "Análisis de Defender en prioridad baja"}

    @classmethod
    def undo_data(cls, data):
        p = data.get("prev") or {}
        if DEMO or not p:
            return
        low = "$true" if p.get("EnableLowCpuPriority") else "$false"
        run_ps(f"Set-MpPreference -EnableLowCpuPriority {low} -ScanAvgCPULoadFactor {int(p.get('ScanAvgCPULoadFactor') or 50)}", timeout=40)


class RscAction(Action):
    id, group = "av_rsc", "advanced"
    title = "Red: recibir los paquetes uno a uno (sin agruparlos)"
    desc = ("Windows agrupa los paquetes de red que llegan seguidos (RSC) para gastar menos CPU. Es bueno para descargas enormes, pero retrasa "
            "unos microsegundos cada paquete: en juegos online, donde todo son paquetes pequeños, esa espera es latencia de más. "
            "Las descargas siguen yendo igual de rápido en una conexión doméstica.")
    needs_admin, reversible, risk, effect, reboot, profiles = True, True, "bajo", "pequeño", False, EX

    def _estado(self):
        out = run_ps("(Get-NetOffloadGlobalSetting -ErrorAction Stop).ReceiveSegmentCoalescing", timeout=25)[1].strip().lower()
        return out if out in ("enabled", "disabled") else None

    def check(self):
        if DEMO:
            return "Agrupado de paquetes (RSC): activado"
        if not IS_WIN:
            return None
        return "Agrupado de paquetes (RSC): activado" if self._estado() == "enabled" else None

    def apply(self):
        if DEMO:
            return {"prev": "enabled", "_msg": "(Demo) RSC desactivado"}
        prev = self._estado()
        rc, out, err = run_ps("Set-NetOffloadGlobalSetting -ReceiveSegmentCoalescing Disabled -ErrorAction Stop", timeout=40)
        if rc != 0:
            raise RuntimeError((err or out or "Windows no dejó cambiarlo")[:150])
        return {"prev": prev, "_msg": "RSC desactivado"}

    @classmethod
    def undo_data(cls, data):
        if not DEMO and data.get("prev") == "enabled":
            run_ps("Set-NetOffloadGlobalSetting -ReceiveSegmentCoalescing Enabled", timeout=40)


class MemCompressionAction(Action):
    id, group = "av_memcomp", "advanced"
    title = "Memoria: no comprimir la RAM (tienes de sobra)"
    desc = ("Windows comprime en segundo plano datos poco usados para ahorrar RAM, gastando algo de CPU cada vez que los comprime o descomprime. "
            "Con 16 GB o más rara vez hace falta: sin compresión hay menos trabajo de CPU escondido y menos picos. "
            "Usará algo más de RAM; si tu PC se queda corto de memoria, se vuelve a activar con «Deshacer».")
    needs_admin, reversible, risk, effect, reboot, profiles = True, True, "bajo", "depende", True, EX

    def _on(self):
        out = run_ps("(Get-MMAgent -ErrorAction Stop).MemoryCompression", timeout=25)[1].strip().lower()
        return True if out == "true" else False if out == "false" else None

    def check(self):
        if DEMO:
            return "Compresión de memoria: activada (RAM: 32 GB)"
        if not IS_WIN or _ram_gb() < 15.5:
            return None
        return f"Compresión de memoria: activada (RAM: {_ram_gb():.0f} GB)" if self._on() else None

    def apply(self):
        if DEMO:
            return {"_msg": "(Demo) compresión de memoria desactivada"}
        rc, out, err = run_ps("Disable-MMAgent -MemoryCompression -ErrorAction Stop", timeout=40)
        if rc != 0:
            raise RuntimeError((err or out or "Windows no dejó cambiarlo")[:150])
        return {"_msg": "Compresión de memoria desactivada (se nota al reiniciar)"}

    @classmethod
    def undo_data(cls, data):
        if not DEMO:
            run_ps("Enable-MMAgent -MemoryCompression", timeout=40)


def avanzado_actions():
    return [
        _Timer("av_timer", "advanced", "Temporizador: respetar la precisión que pide cada juego",
               "Desde Windows 11 los programas minimizados o en segundo plano ya no pueden subir la precisión del reloj del sistema, "
               "y un juego que lo pide pierde ese ajuste en cuanto otra ventana toma el foco (el típico «tirón al hacer alt-tab» o con Discord encima). "
               "Esta clave devuelve el comportamiento clásico: la precisión que pide un programa vale para todo el sistema.",
               [("HKLM", KERNEL, "GlobalTimerResolutionRequests", 1, REG_DWORD)], needs_admin=True, profiles=EX, effect="depende", reboot=True),
        RegTweak("av_inputq", "advanced", "Ratón y teclado: cola de entrada más corta",
                 "Windows guarda hasta 100 eventos de ratón y teclado en una cola antes de entregarlos. Con una cola de 20 los eventos se entregan "
                 "antes en cuanto hay carga (juegos con muchos FPS, ratones de 1000 Hz o más). Es un ajuste fino: el efecto es pequeño "
                 "pero real si notas el ratón «pegajoso» en escenas pesadas.",
                 [("HKLM", MOUCLASS, "MouseDataQueueSize", 20, REG_DWORD), ("HKLM", KBDCLASS, "KeyboardDataQueueSize", 20, REG_DWORD)],
                 needs_admin=True, profiles=EX, effect="pequeño", reboot=True),
        DefenderLowCpuAction(),
        RscAction(),
        MemCompressionAction(),
        _Ram16("av_pagingexec", "advanced", "Memoria: mantener el núcleo de Windows siempre en RAM",
               "Windows puede mandar partes de su propio núcleo y de los drivers al archivo de paginación, y recuperarlas luego con un parón. "
               "Con 16 GB o más de RAM no tiene sentido: esto las deja siempre en memoria. Efecto pequeño, sin riesgo.",
               [("HKLM", MEMORIA, "DisablePagingExecutive", 1, REG_DWORD)], needs_admin=True, profiles=EX, effect="pequeño", reboot=True),
    ]
