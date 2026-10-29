"""Perfil «Mando»: menos retraso y menos tirones al jugar con mando (Xbox, PlayStation, genéricos).

Honestidad: «0 de retraso» no existe. Un mando por cable ya añade 1-8 ms y tu pantalla y tus FPS suman más. Lo que SÍ se puede quitar
son los tirones raros: que Windows apague el mando o el puerto USB para ahorrar energía (y se despierte tarde), que el botón Xbox
abra la Game Bar en mitad de la partida, y que la captura en segundo plano de Windows robe tiempo al juego.
"""
import re

from actions import REG_DWORD, REG_SZ, Action, RegTweak, reg_read
from util import DEMO, IS_WIN, as_list, ps_quote, run_cmd, run_ps, run_ps_json

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
PCIE_SUB, PCIE_SET = "501a4d13-42af-4429-9fd1-a8218c268e20", "ee12f906-d277-404b-b6da-e5fa1a576df5"      # ahorro de energía del enlace PCIe (ASPM)
USB3_LPM = "d4e98f31-5ffe-4ce1-be31-1b38b384c009"                                                         # gestión de energía del enlace USB 3
WIFI_SUB, WIFI_SET = "19cbb8fa-5279-450e-9fac-8a3d5fedd0c1", "12bbebe6-58d6-4636-95bb-3217ef867c1a"      # ahorro del adaptador inalámbrico (Wi-Fi/BT)


def _indice(sub, setting, ac=True):
    rc, out, _ = run_cmd(["powercfg", "/q", "SCHEME_CURRENT", sub, setting], timeout=15)
    m = re.search(("AC" if ac else "DC") + r"[^\n]*Index:\s*0x([0-9a-fA-F]+)", out)
    return int(m.group(1), 16) if m else None


class _PowerCfgAction(Action):
    """Pone a 0 uno o varios ajustes ocultos del plan de energía actual (en red y en batería) y recuerda los valores para deshacer."""
    needs_admin, reversible, risk, reboot, profiles = True, True, "bajo", False, ("mando",)
    ajustes = ()        # ((subgrupo, ajuste), ...)
    texto = ""

    def check(self):
        if DEMO:
            return self.texto
        for s, a in self.ajustes:
            for ac in (True, False):
                v = _indice(s, a, ac)
                if v not in (0, None):
                    return self.texto
        return None

    def apply(self):
        if DEMO:
            return {"prev": [], "_msg": "(Demo) ajuste de energía aplicado"}
        prev = [(s, a, _indice(s, a, True), _indice(s, a, False)) for s, a in self.ajustes]
        for s, a in self.ajustes:
            run_cmd(["powercfg", "/setacvalueindex", "SCHEME_CURRENT", s, a, "0"], timeout=15)
            run_cmd(["powercfg", "/setdcvalueindex", "SCHEME_CURRENT", s, a, "0"], timeout=15)
        run_cmd(["powercfg", "/setactive", "SCHEME_CURRENT"], timeout=15)
        return {"prev": prev, "_msg": "Ajuste de energía aplicado"}

    @classmethod
    def undo_data(cls, data):
        if DEMO:
            return
        for s, a, ac, dc in data.get("prev", []):
            if ac is not None:
                run_cmd(["powercfg", "/setacvalueindex", "SCHEME_CURRENT", s, a, str(ac)], timeout=15)
            if dc is not None:
                run_cmd(["powercfg", "/setdcvalueindex", "SCHEME_CURRENT", s, a, str(dc)], timeout=15)
        run_cmd(["powercfg", "/setactive", "SCHEME_CURRENT"], timeout=15)


class UsbSuspendAction(_PowerCfgAction):
    id, group, effect = "mando_usb_suspend", "mando", "real"
    title = "USB: que Windows no apague los puertos para ahorrar energía"
    desc = ("Windows puede «dormir» un puerto USB si cree que no lo usas. Con un mando, eso se nota como un parón o una pulsación perdida al "
            "volver a tocarlo. Esto desactiva la suspensión selectiva de USB en tu plan de energía actual.")
    ajustes = ((USB_SUB, USB_SET),)
    texto = "Ahora: suspensión selectiva de USB activada  →  desactivada"


class Usb3LinkAction(_PowerCfgAction):
    id, group, effect = "mando_usb3_lpm", "mando", "pequeño"
    title = "USB 3: sin ahorro de energía en el enlace"
    desc = ("Los puertos USB 3 bajan a un estado de bajo consumo entre ráfagas de datos y tardan un instante en volver. Un mando manda datos "
            "constantemente, así que ese «despertar» solo le estorba. Esto apaga la gestión de energía del enlace USB 3 (ajuste oculto del plan).")
    ajustes = ((USB_SUB, USB3_LPM),)
    texto = "Ahora: gestión de energía del enlace USB 3 activada  →  desactivada"


class PcieAspmAction(_PowerCfgAction):
    id, group, effect = "mando_pcie_aspm", "mando", "pequeño"
    title = "PCIe: sin ahorro de energía en los enlaces (donde cuelgan USB y Bluetooth)"
    desc = ("Los controladores USB y la tarjeta Bluetooth/Wi-Fi van por PCIe, que también puede bajar de estado para ahorrar energía y tardar en "
            "despertar. Esto lo apaga. En portátil gastará algo más de batería.")
    ajustes = ((PCIE_SUB, PCIE_SET),)
    texto = "Ahora: ahorro de energía PCIe (ASPM) activado  →  desactivado"


class WirelessPowerAction(_PowerCfgAction):
    id, group, effect = "mando_wifi_power", "mando", "pequeño"
    title = "Bluetooth / Wi-Fi: adaptador en «máximo rendimiento»"
    desc = ("En muchas tarjetas, Bluetooth y Wi-Fi comparten chip. En modo ahorro, el chip se duerme entre paquetes: en un mando Bluetooth se nota "
            "como saltos o una entrada tardía. «Máximo rendimiento» lo mantiene despierto. Gastará algo más de batería en portátil.")
    ajustes = ((WIFI_SUB, WIFI_SET),)
    texto = "Ahora: adaptador inalámbrico en ahorro  →  máximo rendimiento"


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
        UsbSuspendAction(), Usb3LinkAction(), PcieAspmAction(), WirelessPowerAction(), DevicePowerAction(),
        RegTweak("mando_nexus", "mando", "El botón Xbox del mando no abre la Game Bar",
                 "Con la Game Bar activa, pulsar el botón central (Xbox) en mitad de la partida abre un panel de Windows y puede tirar de los FPS "
                 "un momento. Esto hace que el botón no abra nada (tu juego o Steam lo siguen leyendo igual).",
                 [("HKCU", r"Software\Microsoft\GameBar", "UseNexusForGameBarEnabled", 0, REG_DWORD)],
                 profiles=("mando",), effect="pequeño", risk="bajo"),
        RegTweak("mando_timer", "mando", "Temporizador de Windows 11: que valga para todos los programas",
                 "En Windows 11, un programa que pide el temporizador rápido solo lo consigue con su ventana visible. Con esto vuelve al comportamiento "
                 "clásico: el juego lee el mando con intervalos más regulares aunque tengas Discord u otro programa delante.",
                 [("HKLM", r"SYSTEM\CurrentControlSet\Control\Session Manager\kernel", "GlobalTimerResolutionRequests", 1, REG_DWORD)],
                 needs_admin=True, profiles=("mando",), effect="depende", risk="medio", reboot=True,
                 warning="Algo más de consumo de energía. Solo tiene efecto en Windows 11."),
    ]
    acts += [_flip(), GhostDevicesAction(), HpetDeviceAction()]
    try:
        lista = mandos()
        cable = bool(lista) and all(c == "cable" for _n, c in lista)
        acts += dispositivos_innecesarios(cable)
    except Exception:  # noqa: BLE001
        pass
    return acts


# --------------------------------------------------------------------------- Administrador de dispositivos
# (patrón del nombre, por qué sobra, riesgo, aviso). Solo se ofrece lo que existe en TU PC y está activo; nada se borra: se puede volver a activar.
INNECESARIOS = [
    (r"^Microsoft Kernel Debug Network Adapter$", "Adaptador de red para depurar el núcleo de Windows. Solo lo usan desarrolladores de drivers.", "bajo", ""),
    (r"^Microsoft RRAS Root Enumerator$", "Base de la función de servidor de acceso remoto (RRAS). En un PC de casa no se usa.", "medio",
     "Si usas VPN de Windows (L2TP/PPTP), no lo desactives."),
    (r"^Remote Desktop Device Redirector Bus$", "Sirve para compartir impresoras, discos y audio al conectarte por Escritorio remoto.", "medio",
     "Si usas Escritorio remoto, no lo desactives."),
    (r"^Microsoft Wi-Fi Direct Virtual Adapter", "Crea la red virtual para compartir Internet por Wi-Fi (punto de acceso móvil) y para Miracast.", "medio",
     "Si compartes Internet desde el PC o proyectas la pantalla a una tele, no lo desactives."),
    (r"^Teredo Tunneling Pseudo-Interface$", "Túnel IPv6 antiguo. Casi nadie lo usa hoy.", "medio",
     "Algunos juegos de Microsoft Store / Xbox lo usan para el chat de grupo y el tipo de NAT. Si juegas ahí online, déjalo."),
    (r"Bluetooth", "Radio Bluetooth. Si juegas con el mando POR CABLE y no usas Bluetooth, sobra: quita una fuente de interferencias "
     "con tu Wi-Fi de 2,4 GHz y un dispositivo que despierta el procesador.", "medio",
     "Dejarán de funcionar auriculares, ratón o teclado Bluetooth. Solo se ofrece si tu mando va por cable."),
]


def _estado(ps_filtro):
    ps = ("Get-PnpDevice -ErrorAction SilentlyContinue | Where-Object { " + ps_filtro + " } | "
          "Select-Object FriendlyName,InstanceId,Status,Class | ConvertTo-Json -Compress")
    return [d for d in as_list(run_ps_json(ps, timeout=45, default=[])) if isinstance(d, dict)]


class DeviceDisableAction(Action):
    group, effect, reboot, profiles = "mando", "mínimo", False, ("mando",)
    needs_admin, reversible = True, True

    def __init__(self, nombre, iid, por_que, risk, aviso):
        self.nombre, self.iid, self.risk, self.warning = nombre, iid, risk, aviso
        self.id = "mando_dev_" + re.sub(r"\W+", "_", nombre.lower())[:40]
        self.title = f"Administrador de dispositivos: desactivar «{nombre}»"
        self.desc = por_que + " No se desinstala: se puede volver a activar desde «Historial / Deshacer»."

    def check(self):
        return "Ahora: activo  →  desactivado"

    def apply(self):
        if DEMO:
            return {"iid": self.iid, "_msg": "(Demo) dispositivo desactivado"}
        rc, _o, err = run_ps("Disable-PnpDevice -InstanceId " + ps_quote(self.iid) + " -Confirm:$false -ErrorAction Stop", timeout=60)
        if rc != 0:
            raise RuntimeError(err[:150] or "Windows no dejó desactivarlo")
        return {"iid": self.iid, "_msg": f"«{self.nombre}» desactivado"}

    @classmethod
    def undo_data(cls, data):
        if not DEMO and data.get("iid"):
            run_ps("Enable-PnpDevice -InstanceId " + ps_quote(data["iid"]) + " -Confirm:$false -ErrorAction SilentlyContinue", timeout=60)


def dispositivos_innecesarios(todos_por_cable):
    if DEMO:
        return [DeviceDisableAction("Microsoft Kernel Debug Network Adapter", "ROOT\\KDNIC\\0000", INNECESARIOS[0][1], "bajo", "")]
    if not IS_WIN:
        return []
    out = []
    presentes = _estado("$_.Status -eq 'OK'")
    for patron, por_que, risk, aviso in INNECESARIOS:
        es_bt = "luetooth" in patron
        if es_bt and not todos_por_cable:
            continue
        for d in presentes:
            n = (d.get("FriendlyName") or "").strip()
            iid = (d.get("InstanceId") or "").upper()
            if re.search(patron, n, re.I) and (not es_bt or (d.get("Class") == "Bluetooth" and iid.startswith(("USB\\", "PCI\\")))):
                out.append(DeviceDisableAction(n, d["InstanceId"], por_que, risk, aviso))
                break
    return out


def _flip():
    """Modo «flip» también en ventana/sin bordes (Windows 11 22H2+): menos retraso en juegos DX10/11 que no van en pantalla completa real."""
    cur = reg_read("HKCU", r"Software\Microsoft\DirectX\UserGpuPreferences", "DirectXUserGlobalSettings")
    txt = cur[0] if cur and isinstance(cur[0], str) else ""
    if "SwapEffectUpgradeEnable" in txt:
        txt = re.sub(r"SwapEffectUpgradeEnable=\d;?", "SwapEffectUpgradeEnable=1;", txt)
    else:
        txt = txt + ("" if not txt or txt.endswith(";") else ";") + "SwapEffectUpgradeEnable=1;"
    return RegTweak("mando_flip", "mando", "Juegos en ventana o sin bordes: usar el modo rápido de Windows 11",
                    "Los juegos DirectX 10/11 en «ventana» o «sin bordes» pasan por el compositor de Windows y añaden retraso. Con «Optimizaciones para "
                    "juegos en ventana» activas, Windows los presenta igual que en pantalla completa. Si tu juego va en pantalla completa real, no cambia nada.",
                    [("HKCU", r"Software\Microsoft\DirectX\UserGpuPreferences", "DirectXUserGlobalSettings", txt, REG_SZ)],
                    profiles=("mando",), effect="depende", risk="bajo")


def _pnp(script, timeout=40):
    return as_list(run_ps_json(script, timeout=timeout, default=[]))


class GhostDevicesAction(Action):
    id, group = "mando_ghosts", "mando"
    title = "Administrador de dispositivos: quitar mandos y entradas USB fantasma"
    desc = ("Cada mando que has enchufado alguna vez deja una entrada «fantasma» en Windows (no está conectado, pero sigue registrada). Se acumulan "
            "y a veces se confunden con la copia nueva (mando duplicado, botones cruzados). Esto borra solo las desconectadas con nombre de mando; "
            "el que tienes puesto ahora no se toca.")
    needs_admin, reversible, risk, effect, reboot, profiles = True, False, "bajo", "pequeño", False, ("mando",)
    warning = "No se puede deshacer, pero no pierdes nada: Windows las vuelve a crear solas la próxima vez que enchufes ese mando."
    PS = ("Get-PnpDevice -ErrorAction SilentlyContinue | Where-Object { -not $_.Present -and $_.FriendlyName -match '" + NOMBRES +
          "|usb input device|hid-compliant game' -and $_.Class -in @('HIDClass','XboxComposite','Xbox360Peripherals','XnaComposite','USB','Bluetooth') } | "
          "Select-Object -ExpandProperty InstanceId | ConvertTo-Json -Compress")

    def _lista(self):
        return [x for x in _pnp(self.PS) if isinstance(x, str)]

    def check(self):
        if DEMO:
            return "Hay 4 entradas de mandos desconectados"
        n = len(self._lista())
        return f"Hay {n} entradas de mandos desconectados" if n else None

    def apply(self):
        if DEMO:
            return {"_msg": "(Demo) entradas fantasma eliminadas"}
        ok = sum(run_cmd(["pnputil", "/remove-device", iid], timeout=30)[0] == 0 for iid in self._lista())
        return {"_msg": f"{ok} entradas fantasma eliminadas"}


class HpetDeviceAction(Action):
    id, group = "mando_hpet_dev", "mando"
    title = "Administrador de dispositivos: desactivar el «High precision event timer» (HPET)"
    desc = ("Es un reloj antiguo de la placa. Windows moderno usa el reloj de la CPU, pero dejar el HPET activo puede dar lecturas del reloj más "
            "lentas y variables (microtirones al leer el mando). Es lo mismo que desactivarlo a mano en Administrador de dispositivos > Dispositivos del sistema.")
    needs_admin, reversible, risk, effect, reboot, profiles = True, True, "medio", "depende", True, ("mando",)
    warning = "En algunos PCs mejora los mínimos y en otros no cambia nada. Si algo va peor, «Deshacer» lo vuelve a activar."
    PS = ("Get-PnpDevice -FriendlyName 'High precision event timer' -ErrorAction SilentlyContinue | Where-Object { $_.Status -eq 'OK' } | "
          "Select-Object -ExpandProperty InstanceId | ConvertTo-Json -Compress")

    def check(self):
        if DEMO:
            return "HPET activado en el Administrador de dispositivos"
        return "HPET activado en el Administrador de dispositivos" if _pnp(self.PS, 30) else None

    def apply(self):
        if DEMO:
            return {"ids": [], "_msg": "(Demo) HPET desactivado"}
        ids = [x for x in _pnp(self.PS, 30) if isinstance(x, str)]
        for iid in ids:
            run_ps("Disable-PnpDevice -InstanceId " + ps_quote(iid) + " -Confirm:$false -ErrorAction SilentlyContinue", timeout=40)
        return {"ids": ids, "_msg": "HPET desactivado (se nota tras reiniciar)"}

    @classmethod
    def undo_data(cls, data):
        for iid in data.get("ids") or []:
            run_ps("Enable-PnpDevice -InstanceId " + ps_quote(iid) + " -Confirm:$false -ErrorAction SilentlyContinue", timeout=40)


CONSEJOS = [
    "Usa el mando POR CABLE si puedes. Por Bluetooth suma unos milisegundos y a veces da saltos; por cable es lo más estable.",
    "Si tu mando va con receptor o Bluetooth, usa un puerto USB 2.0 (o un alargador de 1 m): los puertos USB 3 meten ruido justo en los 2,4 GHz y dan saltos.",
    "Wi-Fi de 2,4 GHz y mando inalámbrico se pisan: pon el router/PC en 5 GHz o cable de red.",
    "Enchúfalo directo a la placa (parte trasera del PC), no a un hub USB ni a un cable extensor largo.",
    "Un mando Xbox va a unos 125 Hz de lectura y un DualSense a unos 250 Hz por USB: es cosa del propio mando, Windows no lo puede subir.",
    "En el juego: sincronización vertical (VSync) apagada, o NVIDIA Reflex / AMD Anti-Lag en «Activado» si el juego lo tiene.",
    "Limita los FPS un poco por debajo de la frecuencia de tu monitor: reduce la cola de imágenes y con ella el retraso al pulsar.",
    "Si el juego soporta mando de forma nativa, en Steam desactiva «Steam Input» para él: una capa menos entre el mando y el juego.",
    "Desactivar «todo lo innecesario» del Administrador de dispositivos NO es buena idea: casi nada de eso resta retraso y sí puedes romper el audio, la red o el USB. Aquí solo tocamos lo que sí influye y se puede deshacer.",
    "Nada de esto convierte el retraso en 0: quita tirones y capas de más. La diferencia real es sobre todo mantenerlo estable.",
]
