"""Perfil «Mando»: menos retraso y menos tirones al jugar con mando (Xbox, PlayStation, genéricos).

Honestidad: «0 de retraso» no existe. Un mando por cable ya añade 1-8 ms y tu pantalla y tus FPS suman más. Lo que SÍ se puede quitar
son los tirones raros: que Windows apague el mando o el puerto USB para ahorrar energía (y se despierte tarde), que el botón Xbox
abra la Game Bar en mitad de la partida, y que la captura en segundo plano de Windows robe tiempo al juego.
"""
import re

from actions import REG_DWORD, Action, RegTweak
from util import DEMO, IS_WIN, run_cmd, run_ps, run_ps_json, as_list

USB_SUB = "2a737441-1930-4402-8d77-b2bebba308a3"       # ajustes USB
USB_SET = "48e6b7a6-50f5-4782-a5d4-53bb8f07e226"       # suspensión selectiva de USB
NOMBRES = r"controller|gamepad|xbox|dualsense|dualshock|wireless controller|joystick|game pad|pro controller|8bitdo|gamesir"


# --------------------------------------------------------------------------- detección
def mandos():
    """[(nombre, conexion)] con conexion = 'cable' | 'bluetooth' | 'receptor'."""
    if DEMO:
        return [("Xbox Wireless Controller", "bluetooth")]
    if not IS_WIN:
        return []
    ps = ("Get-PnpDevice -PresentOnly -ErrorAction SilentlyContinue | Where-Object { $_.FriendlyName -match '" + NOMBRES +
          "' -and $_.Class -in @('HIDClass','XboxComposite','Xbox360Peripherals','XnaComposite','Bluetooth','USB') } | "
          "Select-Object FriendlyName,InstanceId | ConvertTo-Json -Compress")
    out, vistos = [], set()
    for d in as_list(run_ps_json(ps, timeout=30, default=[])):
        n, iid = (d.get("FriendlyName") or "").strip(), (d.get("InstanceId") or "").upper()
        if not n or n.lower().startswith("hid-compliant") or n in vistos:
            continue
        vistos.add(n)
        con = "bluetooth" if iid.startswith(("BTH", "HID\\{0000")) or "BTHENUM" in iid or "BTHLE" in iid else \
              "receptor" if "WIRELESS" in n.upper() and "XBOX" in n.upper() and iid.startswith("USB") and "ADAPTER" in n.upper() else "cable"
        out.append((n, con))
    return out


# --------------------------------------------------------------------------- acciones
def _indice(setting, ac=True):
    rc, out, _ = run_cmd(["powercfg", "/q", "SCHEME_CURRENT", USB_SUB, USB_SET], timeout=15)
    m = re.search(r"(AC|DC)[^\n]*Index:\s*0x([0-9a-fA-F]+)".replace("(AC|DC)", "AC" if ac else "DC"), out)
    return int(m.group(2), 16) if m else None


class UsbSuspendAction(Action):
    id, group = "mando_usb_suspend", "mando"
    title = "USB: que Windows no apague los puertos para ahorrar energía"
    desc = ("Windows puede «dormir» un puerto USB si cree que no lo usas. Con un mando, eso se nota como un parón o una pulsación perdida al "
            "volver a tocarlo. Esto desactiva la suspensión selectiva de USB en tu plan de energía actual.")
    needs_admin, reversible, risk, effect, reboot, profiles = True, True, "bajo", "real", False, ("mando",)

    def check(self):
        if DEMO:
            return "Ahora: suspensión selectiva de USB activada  →  desactivada"
        ac, dc = _indice(None, True), _indice(None, False)
        if ac == 0 and dc in (0, None):
            return None
        return "Ahora: suspensión selectiva de USB activada  →  desactivada"

    def apply(self):
        if DEMO:
            return {"ac": 1, "dc": 1, "_msg": "(Demo) USB sin suspensión"}
        ac, dc = _indice(None, True), _indice(None, False)
        for modo in ("setacvalueindex", "setdcvalueindex"):
            run_cmd(["powercfg", f"/{modo}", "SCHEME_CURRENT", USB_SUB, USB_SET, "0"], timeout=15)
        run_cmd(["powercfg", "/setactive", "SCHEME_CURRENT"], timeout=15)
        return {"ac": ac if ac is not None else 1, "dc": dc if dc is not None else 1, "_msg": "Suspensión de USB desactivada"}

    @classmethod
    def undo_data(cls, data):
        if DEMO:
            return
        run_cmd(["powercfg", "/setacvalueindex", "SCHEME_CURRENT", USB_SUB, USB_SET, str(data.get("ac", 1))], timeout=15)
        run_cmd(["powercfg", "/setdcvalueindex", "SCHEME_CURRENT", USB_SUB, USB_SET, str(data.get("dc", 1))], timeout=15)
        run_cmd(["powercfg", "/setactive", "SCHEME_CURRENT"], timeout=15)


_PS_LISTA = ("Get-CimInstance -Namespace root\\wmi -ClassName MSPower_DeviceEnable -ErrorAction SilentlyContinue | "
             "Where-Object { $_.InstanceName -match '^(USB|HID|BTHENUM|BTHLE)\\\\' -and $_.Enable } | "
             "ForEach-Object { $_.InstanceName } | ConvertTo-Json -Compress")


def _dispositivos_con_ahorro():
    return [x for x in as_list(run_ps_json(_PS_LISTA, timeout=40, default=[])) if isinstance(x, str)]


def _poner_ahorro(nombres, valor):
    if not nombres:
        return
    lista = ",".join("'" + n.replace("'", "''") + "'" for n in nombres)
    run_ps("$n=@(" + lista + "); Get-CimInstance -Namespace root\\wmi -ClassName MSPower_DeviceEnable -ErrorAction SilentlyContinue | "
           "Where-Object { $n -contains $_.InstanceName } | ForEach-Object { $_.Enable=" + ("$true" if valor else "$false") +
           "; Set-CimInstance -InputObject $_ -ErrorAction SilentlyContinue }", timeout=60)


class DevicePowerAction(Action):
    id, group = "mando_dev_power", "mando"
    title = "Mandos, USB y Bluetooth: que Windows no los apague para ahorrar energía"
    desc = ("En el Administrador de dispositivos, cada dispositivo USB, HID (mandos, teclados, ratones) y Bluetooth tiene «Permitir que el equipo "
            "apague este dispositivo para ahorrar energía». Si está activo, el mando puede tardar en reaccionar al despertar. Esto lo "
            "desmarca solo en esos dispositivos y recuerda cuáles cambió para devolverlos al deshacer.")
    needs_admin, reversible, risk, effect, reboot, profiles = True, True, "bajo", "real", False, ("mando",)

    def check(self):
        if DEMO:
            return "Hay 9 dispositivos USB/HID/Bluetooth con ahorro de energía activado"
        n = len(_dispositivos_con_ahorro())
        return f"Hay {n} dispositivos USB/HID/Bluetooth con ahorro de energía activado" if n else None

    def apply(self):
        if DEMO:
            return {"dev": [], "_msg": "(Demo) ahorro de energía desactivado"}
        dev = _dispositivos_con_ahorro()
        _poner_ahorro(dev, False)
        return {"dev": dev, "_msg": f"Ahorro de energía desactivado en {len(dev)} dispositivos"}

    @classmethod
    def undo_data(cls, data):
        if not DEMO:
            _poner_ahorro(data.get("dev") or [], True)


def mando_actions():
    acts = [
        UsbSuspendAction(), DevicePowerAction(),
        RegTweak("mando_nexus", "mando", "El botón Xbox del mando no abre la Game Bar",
                 "Con la Game Bar activa, pulsar el botón central (Xbox) en mitad de la partida abre un panel de Windows y puede tirar de los FPS "
                 "un momento. Esto hace que el botón no abra nada (tu juego o Steam lo siguen leyendo igual).",
                 [("HKCU", r"Software\Microsoft\GameBar", "UseNexusForGameBarEnabled", 0, REG_DWORD)],
                 profiles=("mando",), effect="pequeño", risk="bajo"),
        RegTweak("mando_gamebar", "mando", "Windows: no grabar ni capturar en segundo plano mientras juegas",
                 "La captura en segundo plano de Windows (Game DVR) reserva GPU y disco aunque no grabes nada. Apagarla deja ese tiempo al juego. "
                 "Si usas «Grabar los últimos 30 s» de Xbox, perderás esa función; OBS o ShadowPlay no se tocan.",
                 [("HKCU", r"Software\Microsoft\Windows\CurrentVersion\GameDVR", "AppCaptureEnabled", 0, REG_DWORD),
                  ("HKCU", r"System\GameConfigStore", "GameDVR_Enabled", 0, REG_DWORD)],
                 profiles=("mando",), effect="pequeño", risk="bajo"),
        RegTweak("mando_timer", "mando", "Temporizador de Windows 11: que valga para todos los programas",
                 "En Windows 11, un programa que pide el temporizador rápido solo lo consigue con su ventana visible. Con esto vuelve al comportamiento "
                 "clásico: el juego lee el mando con intervalos más regulares aunque tengas Discord u otro programa delante.",
                 [("HKLM", r"SYSTEM\CurrentControlSet\Control\Session Manager\kernel", "GlobalTimerResolutionRequests", 1, REG_DWORD)],
                 needs_admin=True, profiles=("mando",), effect="depende", risk="medio", reboot=True,
                 warning="Algo más de consumo de energía. Solo tiene efecto en Windows 11."),
    ]
    return acts


CONSEJOS = [
    "Usa el mando POR CABLE si puedes. Por Bluetooth suma unos milisegundos y a veces da saltos; por cable es lo más estable.",
    "Enchúfalo directo a la placa (parte trasera del PC), no a un hub USB ni a un cable extensor largo.",
    "Un mando Xbox va a unos 125 Hz de lectura y un DualSense a unos 250 Hz por USB: es cosa del propio mando, Windows no lo puede subir.",
    "En el juego: sincronización vertical (VSync) apagada, o NVIDIA Reflex / AMD Anti-Lag en «Activado» si el juego lo tiene.",
    "Limita los FPS un poco por debajo de la frecuencia de tu monitor: reduce la cola de imágenes y con ella el retraso al pulsar.",
    "Si el juego soporta mando de forma nativa, en Steam desactiva «Steam Input» para él: una capa menos entre el mando y el juego.",
    "Nada de esto convierte el retraso en 0: quita tirones y capas de más. La diferencia real es sobre todo mantenerlo estable.",
]
