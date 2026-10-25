"""Tweaks de registro extra, elegidos por tener un efecto REAL y comprobable (los mitos se explican en la página Tweaks).
Todos son reversibles desde el Historial."""
from actions import REG_DWORD, REG_SZ, RegTweak

_WU = r"SOFTWARE\Policies\Microsoft\Windows\WindowsUpdate"


def extra_actions():
    return [
        RegTweak("xt_sticky", "gaming", "Sin avisos de «Teclas especiales» (Shift ×5, Bloq Mayús…)",
                 "Pulsar Shift cinco veces o mantener una tecla abre un cuadro de Windows que MINIMIZA el juego en mitad de la partida. "
                 "Esto apaga esos avisos (Teclas especiales, Teclas filtro y Teclas de alternancia).",
                 [("HKCU", r"Control Panel\Accessibility\StickyKeys", "Flags", "506", REG_SZ),
                  ("HKCU", r"Control Panel\Accessibility\Keyboard Response", "Flags", "122", REG_SZ),
                  ("HKCU", r"Control Panel\Accessibility\ToggleKeys", "Flags", "58", REG_SZ)],
                 profiles=("gaming",), effect="real", risk="bajo"),
        RegTweak("xt_gamebar_pop", "gaming", "Sin ventanas emergentes de la Xbox Game Bar",
                 "Quita el panel de bienvenida y las sugerencias de la Game Bar, que a veces salen sobre el juego y le roban el foco. "
                 "No toca tus grabaciones (para eso está el tweak de grabación en segundo plano).",
                 [("HKCU", r"Software\Microsoft\GameBar", "ShowStartupPanel", 0, REG_DWORD),
                  ("HKCU", r"Software\Microsoft\GameBar", "UseNexusForGameBarEnabled", 0, REG_DWORD),
                  ("HKCU", r"Software\Microsoft\GameBar", "GamePanelStartupTipIndex", 3, REG_DWORD)],
                 profiles=("gaming",), effect="pequeño", risk="bajo"),
        RegTweak("xt_kb_repeat", "speed", "Teclado: repetición de tecla al máximo",
                 "Sube la velocidad de repetición del teclado y baja el retraso antes de repetir. Se nota al moverte con una tecla "
                 "mantenida y al escribir. Se aplica al volver a iniciar sesión.",
                 [("HKCU", r"Control Panel\Keyboard", "KeyboardDelay", "0", REG_SZ),
                  ("HKCU", r"Control Panel\Keyboard", "KeyboardSpeed", "31", REG_SZ)],
                 profiles=("gaming",), effect="pequeño", risk="bajo", reboot=True),
        RegTweak("xt_no_autoreboot", "gaming", "Que Windows no se reinicie solo mientras tienes la sesión abierta",
                 "Tras una actualización, Windows puede reiniciar el PC él solo aunque estés en plena partida. Con esto te avisa "
                 "y espera a que reinicies tú. Sigues recibiendo las actualizaciones.",
                 [("HKLM", _WU + r"\AU", "NoAutoRebootWithLoggedOnUsers", 1, REG_DWORD)],
                 needs_admin=True, profiles=("gaming",), effect="real", risk="bajo"),
        RegTweak("xt_wu_drivers", "gaming", "Que Windows Update no cambie el driver de tu gráfica",
                 "Windows Update a veces sustituye tu driver de NVIDIA/AMD por otro más antiguo o genérico y empiezan los fallos o "
                 "la bajada de FPS. Con esto sigues actualizando tus drivers tú desde la web del fabricante.",
                 [("HKLM", _WU, "ExcludeWUDriversInQualityUpdate", 1, REG_DWORD)],
                 needs_admin=True, profiles=("gaming",), effect="real", risk="medio",
                 warning="Dejarás de recibir drivers (de red, audio…) por Windows Update. Instálalos tú desde la web de tu placa o fabricante."),
        RegTweak("xt_widgets", "speed", "Quitar los Widgets de Windows 11",
                 "Los Widgets mantienen un proceso web abierto en segundo plano (decenas de MB de RAM y algo de red). Esto los apaga por "
                 "política, que es la forma que Windows respeta.",
                 [("HKLM", r"SOFTWARE\Policies\Microsoft\Dsh", "AllowNewsAndInterests", 0, REG_DWORD)],
                 needs_admin=True, profiles=("gaming", "work"), effect="pequeño", risk="bajo"),
        RegTweak("xt_timer_global", "latency", "Temporizador de Windows 11: que valga para todos los programas",
                 "Desde Windows 11, un programa que pide el temporizador rápido solo lo consigue si su ventana está visible. Con esto "
                 "vuelve al comportamiento clásico: sirve si usas Discord, OBS o herramientas de fondo junto al juego.",
                 [("HKLM", r"SYSTEM\CurrentControlSet\Control\Session Manager\kernel", "GlobalTimerResolutionRequests", 1, REG_DWORD)],
                 needs_admin=True, profiles=("extreme",), effect="depende", risk="medio", reboot=True,
                 warning="Algo más de consumo de energía. Solo tiene efecto en Windows 11."),
        RegTweak("xt_ntfs_8dot3", "speed", "Disco: no crear nombres cortos 8.3",
                 "NTFS crea un nombre antiguo (tipo PROGRA~1) por cada archivo. Apagarlo reduce un poco el trabajo del disco al crear "
                 "archivos. Es una mejora pequeña.",
                 [("HKLM", r"SYSTEM\CurrentControlSet\Control\FileSystem", "NtfsDisable8dot3NameCreation", 1, REG_DWORD)],
                 needs_admin=True, profiles=("extreme",), effect="mínimo", risk="medio", reboot=True,
                 warning="Algún instalador muy antiguo puede fallar. Los archivos que ya existen no se tocan."),
    ]


# Tweaks muy repetidos en vídeos y foros que, según la documentación de Microsoft y pruebas públicas, NO hacen lo que prometen.
# HellOP no los ofrece a propósito: aplicarlos no sube FPS y algunos empeoran cosas.
MITOS = [
    ("SystemResponsiveness = 0", "Windows trata los valores bajos como 20 (el de fábrica): no cambia nada."),
    ("«GPU Priority» y «SFIO Priority» en Tasks\\Games", "Microsoft los documenta como «no usados»: no hacen nada."),
    ("Win32PrioritySeparation = 26 (hex)", "En Windows de escritorio el valor de fábrica ya da lo mismo; solo ayuda si venía en modo servidor."),
    ("TcpAckFrequency / TCPNoDelay para el ping", "Solo afecta a conexiones TCP; casi todos los juegos online usan UDP."),
    ("Paquetes de 6 valores TCP (TTL, ventana, puertos…)", "Son ajustes de administración sin relación entre sí: no bajan el ping."),
    ("QoS: limitar «ancho de banda reservado» al 0 %", "Windows solo reserva ancho de banda si un programa lo pide: por defecto no reserva nada."),
    ("Desactivar el autoajuste de TCP", "Empeora la velocidad de descarga y no mejora el ping."),
    ("MaxPreRenderedFrames", "Sin documentación actual en Windows 11: usa la opción de baja latencia del propio juego."),
    ("Forzar HPET o «useplatformclock»", "Suele empeorar los tirones. HellOP lo QUITA si lo encuentra."),
    ("Desactivar el archivo de paginación", "Hay juegos que fallan sin él; el rendimiento no mejora."),
    ("Programas de «resolución del temporizador»", "En Windows 11 se gestiona por proceso: la mejora es casi siempre placebo."),
]
