"""Perfil «Streaming»: emitir en directo sin que el juego pierda FPS.

Lo que hace de verdad (nada de mitos):
  • Crea un PERFIL NUEVO en OBS Studio («HellOP Streaming») con el codificador de TU gráfica (NVENC, AMF o Quick Sync) en vez del de la CPU,
    que es lo que menos le quita al juego, con resolución, FPS y bitrate acordes (los de las guías de Twitch/YouTube). El perfil que ya
    tengas en OBS NO se toca: lo eliges tú en el menú «Perfil» de OBS, y aquí se puede borrar con «Deshacer».
  • Pone OBS (y Streamlabs, si lo tienes) en «Alto rendimiento» en la configuración de gráficos de Windows: en portátiles con dos gráficas
    evita que graben con la integrada, que es una causa típica de fotogramas perdidos.
  • Añade los ajustes de Gaming que no molestan al directo, y protege OBS/Discord para que «Procesos pesados» nunca te los cierre.
"""
import os
import shutil
import sys

from actions import REG_SZ, Action, RegTweak
from util import DEMO, IS_WIN, run_ps

PERFIL = "HellOP Streaming"
MARCA = "hellop_streaming.txt"
OBS_EXES = ("obs64.exe",)
CLAVE_GPU = r"Software\Microsoft\DirectX\UserGpuPreferences"


# --------------------------------------------------------------------------- detección
def _reg_default(path):
    if not IS_WIN:
        return None
    try:
        import winreg
        for view in (winreg.KEY_WOW64_64KEY, winreg.KEY_WOW64_32KEY):
            try:
                with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, path, 0, winreg.KEY_READ | view) as k:
                    return winreg.QueryValueEx(k, "")[0]
            except OSError:
                continue
    except Exception:  # noqa: BLE001
        pass
    return None


def find_obs():
    """Ruta de obs64.exe de OBS Studio, o None."""
    if DEMO:
        return r"C:\Program Files\obs-studio\bin\64bit\obs64.exe"
    cands = []
    d = _reg_default(r"SOFTWARE\OBS Studio")
    if d:
        cands.append(os.path.join(d, "bin", "64bit", "obs64.exe"))
    for base in (os.environ.get("ProgramFiles"), os.environ.get("ProgramFiles(x86)")):
        if base:
            cands.append(os.path.join(base, "obs-studio", "bin", "64bit", "obs64.exe"))
            cands.append(os.path.join(base, "Steam", "steamapps", "common", "OBS Studio", "bin", "64bit", "obs64.exe"))
    return next((c for c in cands if os.path.exists(c)), None)


def find_streamlabs():
    if DEMO:
        return None
    for base in (os.environ.get("ProgramFiles"), os.environ.get("ProgramFiles(x86)")):
        if base:
            for sub in (r"Streamlabs Desktop\Streamlabs Desktop.exe", r"Streamlabs OBS\Streamlabs OBS.exe"):
                p = os.path.join(base, sub)
                if os.path.exists(p):
                    return p
    return None


def gpu_names():
    if DEMO:
        return ["NVIDIA GeForce RTX 3060"]
    if not IS_WIN:
        return []
    out = run_ps("(Get-CimInstance Win32_VideoController | ForEach-Object { $_.Name }) -join '|'", timeout=30)[1].strip()
    return [x for x in out.split("|") if x]


def pick_encoder(names):
    """(id de OBS en modo simple, nombre para mostrar). Si hay varias gráficas manda la dedicada."""
    low = " ".join(names).lower()
    if any(k in low for k in ("nvidia", "geforce", "rtx", "gtx", "quadro")):
        return "nvenc", "NVENC (la gráfica NVIDIA)"
    if any(k in low for k in ("radeon", "amd")):
        return "amd", "AMF (la gráfica AMD)"
    if any(k in low for k in ("intel", " arc", "uhd", "iris")):
        return "qsv", "Quick Sync (la gráfica Intel)"
    return "x264", "x264 (la CPU: no encontré una gráfica con codificador)"


def pantalla():
    if IS_WIN:
        try:
            import ctypes
            u = ctypes.windll.user32
            w, h = int(u.GetSystemMetrics(0)), int(u.GetSystemMetrics(1))
            if w > 0 and h > 0:
                return w, h
        except Exception:  # noqa: BLE001
            pass
    return 1920, 1080


def plan(enc, base):
    """Resolución de salida, FPS y bitrate según el codificador y la pantalla (valores de las guías de Twitch/YouTube)."""
    bw, bh = base
    hw = enc != "x264"
    oh = 1080 if (hw and bh >= 1080) else 720 if bh >= 720 else bh
    ow = max(2, int(round(bw * oh / bh / 2)) * 2)
    fps = 60 if hw else 30            # con la CPU, 60 FPS a 720p le roba demasiado al juego
    kbps = 6000 if oh >= 1080 else 4500 if fps == 60 else 3500
    return ow, oh, fps, kbps


def perfiles_dir():
    return os.path.join(os.environ.get("APPDATA", ""), "obs-studio", "basic", "profiles")


def construir_ini(enc, base, ow, oh, fps, kbps):
    return "\n".join([
        "[General]", f"Name={PERFIL}", "",
        "[Video]", f"BaseCX={base[0]}", f"BaseCY={base[1]}", f"OutputCX={ow}", f"OutputCY={oh}",
        "FPSType=0", f"FPSCommon={fps}", "ScaleType=bicubic", "",
        "[Output]", "Mode=Simple", "",
        "[SimpleOutput]", f"StreamEncoder={enc}", f"VBitrate={kbps}", "ABitrate=160", "UseAdvanced=false", "EnforceBitrate=true",
        "Preset=veryfast", "NVENCPreset2=p5", "AMDPreset=quality", "QSVPreset=balanced", "RecQuality=Stream", "",
        "[Audio]", "SampleRate=48000", "ChannelSetup=Stereo", ""])


# --------------------------------------------------------------------------- acciones
class ObsProfileAction(Action):
    id, group = "obs_profile", "streaming"
    reversible = True
    effect = "real"
    risk, reboot, needs_admin, profiles = "bajo", False, False, ("streaming",)

    def __init__(self, enc, nombre_enc, base, ow, oh, fps, kbps):
        self.enc, self.nombre_enc, self.base, self.ow, self.oh, self.fps, self.kbps = enc, nombre_enc, base, ow, oh, fps, kbps
        self.title = f"Crear el perfil «{PERFIL}» en OBS ({oh}p{fps} · {kbps} kbps · {nombre_enc.split(' (')[0]})"
        self.desc = (f"Crea un perfil NUEVO en OBS Studio que codifica con {nombre_enc}, a {ow}×{oh} y {fps} FPS, {kbps} kbps constantes y "
                     "audio a 160 kbps. Codificar con la gráfica casi no resta FPS al juego (con la CPU sí). Tu perfil actual de OBS no se toca: "
                     "ábrelo desde el menú «Perfil» de OBS. Si OBS está abierto, ciérralo y vuelve a abrirlo para verlo.")

    def check(self):
        d = os.path.join(perfiles_dir(), PERFIL)
        if os.path.exists(os.path.join(d, MARCA)) and not DEMO:
            return None            # ya está creado
        return f"{self.nombre_enc}  ·  {self.ow}×{self.oh} a {self.fps} FPS  ·  {self.kbps} kbps"

    def apply(self):
        if DEMO:
            return {"dir": "", "_msg": f"(Demo) perfil «{PERFIL}» creado"}
        d = os.path.join(perfiles_dir(), PERFIL)
        os.makedirs(d, exist_ok=True)
        with open(os.path.join(d, "basic.ini"), "w", encoding="utf-8", newline="\n") as f:
            f.write(construir_ini(self.enc, self.base, self.ow, self.oh, self.fps, self.kbps))
        with open(os.path.join(d, MARCA), "w", encoding="utf-8") as f:
            f.write("Creado por HellOP. Se puede borrar desde «Historial / Deshacer».\n")
        return {"dir": d, "_msg": f"Perfil «{PERFIL}» creado: elígelo en OBS > Perfil"}

    @classmethod
    def undo_data(cls, data):
        d = data.get("dir")
        if d and os.path.exists(os.path.join(d, MARCA)):       # solo se borra lo que creó HellOP
            shutil.rmtree(d, ignore_errors=True)


def _gpu_pref(clave, nombre, exe):
    return RegTweak(clave, "gpu", f"Alto rendimiento de gráfica para {nombre}",
                    f"Pone {nombre} en «Alto rendimiento» en Configuración > Sistema > Pantalla > Gráficos. En portátiles con dos gráficas evita "
                    "que capture o codifique con la integrada (causa típica de fotogramas perdidos). En un PC con una sola gráfica no cambia nada.",
                    [("HKCU", CLAVE_GPU, exe, "GpuPreference=2;", REG_SZ)],
                    profiles=("streaming",), effect="pequeño", risk="bajo")


def streaming_actions():
    acts = []
    names = gpu_names()
    enc, nombre = pick_encoder(names)
    obs = find_obs()
    if obs:
        base = pantalla()
        ow, oh, fps, kbps = plan(enc, base)
        acts.append(ObsProfileAction(enc, nombre, base, ow, oh, fps, kbps))
        acts.append(_gpu_pref("stream_gpu_obs", "OBS Studio", obs))
    sl = find_streamlabs()
    if sl:
        acts.append(_gpu_pref("stream_gpu_slobs", "Streamlabs", sl))
    return acts


APPS_PROTEGIDAS = {"obs64.exe", "obs32.exe", "obs-browser-page.exe", "streamlabs desktop.exe", "streamlabs obs.exe",
                   "xsplit.core.exe", "discord.exe", "nvidia broadcast.exe", "nvidia app.exe"}

CONSEJOS = [
    "Captura el juego con «Captura de juego» (no «Captura de pantalla»): gasta menos y evita pantallas negras.",
    "Codificador: el de tu gráfica (NVENC, AMF o Quick Sync). Control de tasa: CBR. Intervalo de fotogramas clave: 2 s (Twitch, YouTube y Kick lo piden).",
    "Bitrate de guía: 1080p60 → 6000 kbps en Twitch (YouTube admite 8000-9000); 720p60 → 3500-5000 kbps; 1080p30 → 4000-6000 kbps.",
    "No subas el bitrate «por si acaso»: más allá del que admite la plataforma solo gasta subida y puede cortar el directo.",
    "Cierra la vista previa de OBS y las fuentes que no uses (navegador, cámara a alta resolución): también gastan gráfica.",
    "Si el juego deja la gráfica al 100 %, limita sus FPS al de tu monitor: así sobra margen para codificar sin tirones.",
    "Desactiva el overlay de NVIDIA/ShadowPlay mientras emites con OBS: dos capturas a la vez se estorban.",
    "Si pierdes fotogramas por «codificador sobrecargado», baja el preset o la resolución; si es por «red», baja el bitrate.",
]
