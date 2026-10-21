"""Análisis de hardware: CPU, placa, RAM, GPU, discos, temperaturas, drivers y
recomendaciones (incluida la guía de BIOS/XMP para los tiempos de la RAM)."""
import random
import re
import shutil

import psutil

from util import (DEMO, IS_WIN, age_text, as_list, days_since, fmt_bytes, fmt_gb,
                  run_cmd, run_ps_json)

# --------------------------------------------------------------------------
# Recogida de datos (una sola llamada a PowerShell devuelve todo)
# --------------------------------------------------------------------------
HW_SCRIPT = r"""
$ErrorActionPreference='SilentlyContinue'
function D($d){ if($d){ $d.ToString('yyyy-MM-dd') } else { $null } }
$cpu = @(Get-CimInstance Win32_Processor | ForEach-Object { [pscustomobject]@{Name=([string]$_.Name).Trim();Cores=$_.NumberOfCores;Threads=$_.NumberOfLogicalProcessors;MaxMHz=$_.MaxClockSpeed;Socket=$_.SocketDesignation} })
$board = @(Get-CimInstance Win32_BaseBoard | ForEach-Object { [pscustomobject]@{Maker=$_.Manufacturer;Model=$_.Product} })
$bios = @(Get-CimInstance Win32_BIOS | ForEach-Object { [pscustomobject]@{Version=$_.SMBIOSBIOSVersion;Maker=$_.Manufacturer;Date=(D $_.ReleaseDate)} })
$ram = @(Get-CimInstance Win32_PhysicalMemory | ForEach-Object { [pscustomobject]@{Capacity=[int64]$_.Capacity;Speed=$_.Speed;Configured=$_.ConfiguredClockSpeed;Maker=([string]$_.Manufacturer).Trim();Part=([string]$_.PartNumber).Trim();Type=$_.SMBIOSMemoryType;Slot=$_.DeviceLocator} })
$slots = (Get-CimInstance Win32_PhysicalMemoryArray | Measure-Object -Property MemoryDevices -Sum).Sum
$gpuReg = @{}
Get-ChildItem 'HKLM:\SYSTEM\CurrentControlSet\Control\Class\{4d36e968-e325-11ce-bfc1-08002be10318}' -ErrorAction SilentlyContinue | ForEach-Object {
  $p = Get-ItemProperty $_.PSPath -ErrorAction SilentlyContinue
  $q = $p.'HardwareInformation.qwMemorySize'
  if($p.DriverDesc -and $q){ $gpuReg[[string]$p.DriverDesc] = [int64]$q }
}
$gpu = @(Get-CimInstance Win32_VideoController | ForEach-Object {
  $v = [int64]$_.AdapterRAM
  if($gpuReg.ContainsKey([string]$_.Name)){ $v = $gpuReg[[string]$_.Name] }
  [pscustomobject]@{Name=$_.Name;VRAM=$v;Driver=$_.DriverVersion;DriverDate=(D $_.DriverDate)}
})
$disks = @(Get-PhysicalDisk | ForEach-Object {
  $c = $_ | Get-StorageReliabilityCounter
  [pscustomobject]@{Name=$_.FriendlyName;Media=[string]$_.MediaType;Bus=[string]$_.BusType;Size=[int64]$_.Size;Health=[string]$_.HealthStatus;Temp=$c.Temperature;Wear=$c.Wear;Hours=$c.PowerOnHours}
})
$os = @(Get-CimInstance Win32_OperatingSystem | ForEach-Object { [pscustomobject]@{Name=$_.Caption;Build=$_.BuildNumber;Arch=$_.OSArchitecture} })
$drv = @(Get-CimInstance Win32_PnPSignedDriver | Where-Object { $_.DeviceClass -in 'DISPLAY','NET','MEDIA','BLUETOOTH' -and $_.Manufacturer -notmatch 'Microsoft' -and $_.DriverDate } | ForEach-Object { [pscustomobject]@{Name=$_.DeviceName;Class=$_.DeviceClass;Version=$_.DriverVersion;Date=(D $_.DriverDate);Maker=$_.Manufacturer} })
[pscustomobject]@{cpu=$cpu;board=$board;bios=$bios;ram=$ram;slots=$slots;gpu=$gpu;disks=$disks;os=$os;drivers=$drv} | ConvertTo-Json -Depth 4 -Compress
"""

DEMO_HW = {
    "cpu": [{"Name": "AMD Ryzen 5 5600X 6-Core Processor", "Cores": 6, "Threads": 12, "MaxMHz": 3701, "Socket": "AM4"}],
    "board": [{"Maker": "ASUSTeK COMPUTER INC.", "Model": "TUF GAMING B550-PLUS"}],
    "bios": [{"Version": "2803", "Maker": "American Megatrends Inc.", "Date": "2021-03-10"}],
    "ram": [
        {"Capacity": 8 * 1024 ** 3, "Speed": 3200, "Configured": 2133, "Maker": "G.Skill", "Part": "F4-3200C16-8GVKB", "Type": 26, "Slot": "DIMM_A1"},
        {"Capacity": 8 * 1024 ** 3, "Speed": 3200, "Configured": 2133, "Maker": "G.Skill", "Part": "F4-3200C16-8GVKB", "Type": 26, "Slot": "DIMM_B1"},
    ],
    "slots": 4,
    "gpu": [{"Name": "NVIDIA GeForce RTX 3060", "VRAM": 12 * 1024 ** 3, "Driver": "31.0.15.3623", "DriverDate": "2023-09-12"}],
    "disks": [
        {"Name": "Samsung SSD 970 EVO Plus 500GB", "Media": "SSD", "Bus": "NVMe", "Size": 500107862016, "Health": "Healthy", "Temp": 41, "Wear": 6, "Hours": 5120},
        {"Name": "Kingston SA400S37480G", "Media": "SSD", "Bus": "SATA", "Size": 480103981056, "Health": "Healthy", "Temp": 33, "Wear": 12, "Hours": 9800},
        {"Name": "WDC WD10EZEX-08WN4A0", "Media": "HDD", "Bus": "SATA", "Size": 1000204886016, "Health": "Healthy", "Temp": 36, "Wear": None, "Hours": 21000},
    ],
    "os": [{"Name": "Microsoft Windows 11 Home", "Build": "22631", "Arch": "64-bit"}],
    "drivers": [
        {"Name": "NVIDIA GeForce RTX 3060", "Class": "DISPLAY", "Version": "31.0.15.3623", "Date": "2023-09-12", "Maker": "NVIDIA"},
        {"Name": "Realtek PCIe GbE Family Controller", "Class": "NET", "Version": "10.57.118.2022", "Date": "2022-01-18", "Maker": "Realtek"},
        {"Name": "Realtek High Definition Audio", "Class": "MEDIA", "Version": "6.0.9235.1", "Date": "2021-06-02", "Maker": "Realtek Semiconductor Corp."},
        {"Name": "Intel(R) Wi-Fi 6 AX200 160MHz", "Class": "NET", "Version": "22.250.1.2", "Date": "2025-08-20", "Maker": "Intel Corporation"},
    ],
}


VRAM_CAP = 4293918720   # Windows (AdapterRAM, 32 bits) nunca informa de más de ~4 GB


def fix_vram(gpus):
    """Corrige la VRAM: el valor de 64 bits del registro ya viene de PowerShell; aquí se usa
    nvidia-smi (exacto) cuando existe y la lectura sigue en el tope de 4 GB."""
    if not any((g.get("VRAM") or 0) >= VRAM_CAP - 1024 ** 2 and (g.get("VRAM") or 0) <= 4294967296 for g in gpus):
        return
    if not shutil.which("nvidia-smi"):
        return
    rc, out, _ = run_cmd(["nvidia-smi", "--query-gpu=name,memory.total", "--format=csv,noheader,nounits"], timeout=10)
    if rc != 0:
        return
    smi = {}
    for line in out.splitlines():
        name, _, mem = line.rpartition(",")
        try:
            smi[name.strip().lower()] = int(float(mem.strip())) * 1024 ** 2
        except ValueError:
            continue
    for g in gpus:
        v = g.get("VRAM") or 0
        if VRAM_CAP - 1024 ** 2 <= v <= 4294967296:
            n = (g.get("Name") or "").lower()
            for k, mem in smi.items():
                if k in n or n in k or k.replace("nvidia ", "") in n:
                    g["VRAM"] = mem
                    break


def collect_hardware():
    if DEMO:
        return DEMO_HW
    data = run_ps_json(HW_SCRIPT, timeout=120, default=None)
    if not isinstance(data, dict):
        raise RuntimeError("No pude leer el hardware (¿PowerShell bloqueado?).")
    try:
        fix_vram(as_list(data.get("gpu")))
    except Exception:  # noqa: BLE001
        pass
    return data


# --------------------------------------------------------------------------
# Memoria RAM: tipo, kit, tiempos y guía de BIOS
# --------------------------------------------------------------------------
MEM_TYPES = {20: "DDR", 21: "DDR2", 24: "DDR3", 26: "DDR4", 34: "DDR5"}
KINGSTON = {426: 2666, 429: 2933, 432: 3200, 436: 3600, 440: 4000,
            548: 4800, 552: 5200, 556: 5600, 560: 6000, 564: 6400}
TYPICAL_TIMINGS = {   # tiempos habituales de perfiles XMP/EXPO (orientativos)
    2400: "CL15-15-15-35", 2666: "CL16-16-16-36", 3000: "CL15-17-17-35",
    3200: "CL16-18-18-38", 3600: "CL16-19-19-39", 4000: "CL18-22-22-42",
    4800: "CL40-40-40-77", 5200: "CL40-40-40-77", 5600: "CL36-36-36-76",
    6000: "CL30-38-38-96", 6400: "CL32-39-39-102",
}


def _mem_type(mods):
    code = next((m.get("Type") for m in mods if m.get("Type")), 0)
    if code in MEM_TYPES:
        return MEM_TYPES[code]
    top = max((m.get("Speed") or 0) for m in mods) if mods else 0
    return "DDR5" if top >= 4400 else "DDR4" if top >= 2133 else "DDR3" if top >= 800 else "RAM"


def _kit_from_part(part):
    """Intenta leer velocidad (MHz) y CL desde la referencia del módulo."""
    part = (part or "").upper().replace(" ", "")
    m = re.search(r"(\d{4,5})C(\d{2})", part)           # G.Skill, Corsair, Crucial...
    if m:
        return int(m.group(1)), int(m.group(2))
    m = re.match(r"KF([45]\d{2})C(\d{2})", part)         # Kingston Fury
    if m and int(m.group(1)) in KINGSTON:
        return KINGSTON[int(m.group(1))], int(m.group(2))
    return None, None


def _xmp_name(cpu_name, board_maker, mtype):
    cpu = (cpu_name or "").upper()
    maker = (board_maker or "").upper()
    if "AMD" in cpu or "RYZEN" in cpu:
        if mtype == "DDR5":
            return "EXPO (o DOCP / A-XMP, según tu placa)"
        return "DOCP" if "ASUS" in maker else "A-XMP" if "MSI" in maker else "DOCP / XMP / A-XMP"
    return "XMP (Extreme Memory Profile)"


def _bios_key(board_maker):
    maker = (board_maker or "").upper()
    if "ASUS" in maker:
        return "Supr o F2"
    if "MSI" in maker or "MICRO-STAR" in maker:
        return "Supr"
    if "GIGABYTE" in maker:
        return "Supr"
    if "ASROCK" in maker:
        return "F2 o Supr"
    return "Supr o F2 (según el fabricante de tu placa)"


def ram_advice(hw):
    mods = hw.get("ram") or []
    if not mods:
        return None
    cpu = (hw.get("cpu") or [{}])[0].get("Name", "")
    board = (hw.get("board") or [{}])[0].get("Maker", "")
    mtype = _mem_type(mods)
    total = sum(m.get("Capacity") or 0 for m in mods)
    count = len(mods)
    slots = hw.get("slots") or count
    rated = max((m.get("Speed") or 0) for m in mods)
    running = max((m.get("Configured") or 0) for m in mods) or rated
    part = next((m.get("Part") for m in mods if m.get("Part")), "")
    kit_speed, kit_cl = _kit_from_part(part)
    capable = max(rated, kit_speed or 0)
    base = {"DDR4": 2666, "DDR5": 4800, "DDR3": 1600}.get(mtype, 0)
    sweet = {"DDR4": (3200, "CL16"), "DDR5": (6000, "CL30"), "DDR3": (1600, "CL9")}.get(mtype)

    lines = [
        ("Tipo", mtype),
        ("Módulos", f"{count} × {fmt_gb(mods[0].get('Capacity'))} = {fmt_gb(total)} (placa con {slots} ranuras)"),
        ("Velocidad ahora", f"{running} MHz" if running else "no disponible"),
    ]
    if capable and capable != running:
        lines.append(("Velocidad de tu kit", f"{capable} MHz"))
    if kit_speed:
        lines.append(("Perfil del kit (según su referencia)", f"{kit_speed} MHz CL{kit_cl}"))
    if part:
        lines.append(("Referencia", part))

    level = "ok"
    if capable and running and running < capable - 100:
        level = "warn"
        headline = f"Tu RAM va a {running} MHz y tu kit es capaz de {capable} MHz"
    elif not capable and base and running and running <= base:
        level = "info"
        headline = f"Tu RAM va a {running} MHz (velocidad base). Si tu kit es más rápido, falta activar su perfil"
    else:
        headline = f"Tu RAM funciona a {running} MHz: bien configurada"

    target = kit_speed or (capable if capable > base else (sweet[0] if sweet else 0))
    goal = []
    if target:
        timing = TYPICAL_TIMINGS.get(target)
        goal.append(f"Objetivo para tu equipo: {mtype}-{target}" + (f" con tiempos típicos {timing}" if timing else ""))
        if kit_cl:
            goal.append(f"Tu kit anuncia CL{kit_cl}: ese es el perfil que debes activar.")
    if sweet:
        goal.append(f"Punto ideal de {mtype} (velocidad/latencia): {mtype}-{sweet[0]} {sweet[1]}.")
    goal.append("Los tiempos (CL, tRCD, tRP, tRAS) NO se pueden cambiar desde Windows: se fijan en la BIOS.")

    xmp = _xmp_name(cpu, board, mtype)
    steps = []
    if level != "ok":
        steps = [
            f"Reinicia y entra a la BIOS pulsando {_bios_key(board)} al encender.",
            f"Busca la opción {xmp} (suele estar en Ai Tweaker / OC / Extreme Tweaker / Overclocking).",
            "Elige el Perfil 1 y guarda con F10. El PC reiniciará solo.",
            "Vuelve a pulsar «ANÁLISIS DE PC»: debería mostrar la velocidad nueva.",
            "Si no arranca, déjalo reiniciar 2-3 veces y la BIOS vuelve sola a valores seguros.",
        ]

    notes = []
    if count == 1 and slots >= 2:
        notes.append(("warn", "Estás en canal único (1 solo módulo)",
                      "Con dos módulos iguales (dual channel) ganas ancho de banda: se nota en juegos y sobre todo en gráficos integrados."))
    if count > 1 and len({m.get("Capacity") for m in mods}) > 1:
        notes.append(("info", "Módulos de distinta capacidad",
                      "Funcionan, pero lo ideal es usar módulos idénticos para mantener el dual channel completo."))
    gb = total / 1024 ** 3
    if gb < 8:
        notes.append(("warn", f"Solo {gb:.0f} GB de RAM", "Es poca para Windows moderno: ampliar a 16 GB es la mejora más notable."))
    elif gb < 16:
        notes.append(("info", f"{gb:.0f} GB de RAM", "Justa para juegos actuales y muchas pestañas; 16 GB es lo cómodo."))
    return {"level": level, "headline": headline, "lines": lines, "goal": goal,
            "steps": steps, "notes": notes, "xmp": xmp}


# --------------------------------------------------------------------------
# Discos
# --------------------------------------------------------------------------
def disk_kind(d):
    bus = (d.get("Bus") or "").lower()
    media = (d.get("Media") or "").lower()
    if "nvme" in bus:
        return "SSD NVMe (M.2 PCIe)"
    if "usb" in bus:
        return "Unidad USB externa"
    if media == "ssd":
        return 'SSD SATA (2.5" o M.2 SATA)'
    if media == "hdd":
        return "Disco duro mecánico (HDD)"
    return "Tipo no identificado"


def volumes():
    if DEMO:
        g = 1024 ** 3
        return [("C:\\", 118 * g, 466 * g), ("D:\\", 612 * g, 932 * g)]
    out = []
    try:
        for p in psutil.disk_partitions(all=False):
            if IS_WIN and "fixed" not in (p.opts or "").lower():
                continue
            try:
                u = psutil.disk_usage(p.mountpoint)
            except OSError:
                continue
            out.append((p.mountpoint, u.free, u.total))
    except Exception:  # noqa: BLE001
        pass
    return out


# --------------------------------------------------------------------------
# Drivers
# --------------------------------------------------------------------------
VENDOR_URLS = [
    ("NVIDIA", "https://www.nvidia.com/Download/index.aspx"),
    ("AMD", "https://www.amd.com/en/support/download/drivers.html"),
    ("ADVANCED MICRO", "https://www.amd.com/en/support/download/drivers.html"),
    ("INTEL", "https://www.intel.com/content/www/us/en/download-center/home.html"),
    ("REALTEK", "https://www.realtek.com/Download"),
    ("QUALCOMM", "https://www.qualcomm.com/support"),
    ("MEDIATEK", "https://www.mediatek.com/products/downloads"),
]


def analyze_drivers(hw):
    res = []
    for d in as_list(hw.get("drivers")):
        age = days_since(d.get("Date"))
        limit = 365 if d.get("Class") == "DISPLAY" else 730
        maker = (d.get("Maker") or "").upper()
        url = next((u for k, u in VENDOR_URLS if k in maker or k in (d.get("Name") or "").upper()), None)
        res.append({"name": d.get("Name") or "?", "class": d.get("Class"), "version": d.get("Version"),
                    "date": d.get("Date"), "age_days": age, "old": bool(age and age > limit), "url": url})
    res.sort(key=lambda r: -(r["age_days"] or 0))
    return res


# --------------------------------------------------------------------------
# Informe completo
# --------------------------------------------------------------------------
def analyze(progress=None):
    if progress:
        progress("Leyendo procesador, placa, memoria, gráfica y discos…")
    hw = collect_hardware()
    cpu = (as_list(hw.get("cpu")) or [{}])[0]
    board = (as_list(hw.get("board")) or [{}])[0]
    bios = (as_list(hw.get("bios")) or [{}])[0]
    os_ = (as_list(hw.get("os")) or [{}])[0]
    gpus = as_list(hw.get("gpu"))
    disks = as_list(hw.get("disks"))
    for key in ("ram", "cpu", "board", "bios", "gpu", "disks", "os", "drivers"):
        hw[key] = as_list(hw.get(key))

    recs = []
    sections = {}
    sections["cpu"] = ("Procesador", [
        ("Modelo", cpu.get("Name", "?")),
        ("Núcleos / hilos", f"{cpu.get('Cores', '?')} / {cpu.get('Threads', '?')}"),
        ("Frecuencia máx.", f"{(cpu.get('MaxMHz') or 0) / 1000:.2f} GHz"),
        ("Zócalo", cpu.get("Socket") or "—"),
    ])
    bios_days = days_since(bios.get("Date"))
    sections["board"] = ("Placa base", [
        ("Fabricante", board.get("Maker", "?")),
        ("Modelo", board.get("Model", "?")),
        ("BIOS", f"{bios.get('Version', '?')} ({bios.get('Date') or 'sin fecha'})"),
    ])
    if bios_days and bios_days > 365 * 3:
        recs.append(("info", "BIOS antigua", f"Tu BIOS es de {age_text(bios_days)}. Mira si tu fabricante publicó una más nueva (mejora estabilidad y compatibilidad de RAM)."))

    adv = ram_advice(hw)
    sections["ram"] = ("Memoria RAM", adv["lines"] if adv else [("Estado", "No detectada")])
    if adv:
        if adv["level"] == "warn":
            recs.append(("warn", "RAM por debajo de su velocidad", adv["headline"] + ". Mira la guía de BIOS más abajo."))
        for n in adv["notes"]:
            recs.append(n)

    gl = []
    for g in gpus:
        vram = g.get("VRAM") or 0
        if VRAM_CAP - 1024 ** 2 <= vram <= 4294967296:
            vtxt = "4 GB o más (Windows no informa de más) · "
        else:
            vtxt = f"{fmt_gb(vram)} de VRAM · " if vram > 0 else ""
        gl.append((g.get("Name", "?"), vtxt + f"driver {g.get('Driver', '?')} ({g.get('DriverDate') or '—'})"))
    sections["gpu"] = ("Gráfica", gl or [("Estado", "No detectada")])

    dl = []
    system_hdd = False
    for i, d in enumerate(disks):
        kind = disk_kind(d)
        extra = [fmt_gb(d.get("Size")), kind]
        health = d.get("Health") or "?"
        extra.append(f"salud: {'OK' if health.lower() == 'healthy' else health}")
        if d.get("Wear") is not None:
            extra.append(f"desgaste: {d['Wear']}%")
        if d.get("Hours"):
            extra.append(f"{d['Hours']:,} h encendido".replace(",", "."))
        dl.append((d.get("Name", f"Disco {i}"), " · ".join(extra)))
        if health.lower() not in ("healthy", "?", ""):
            recs.append(("warn", f"Salud del disco: {health}", f"{d.get('Name')} reporta estado «{health}». Haz copia de seguridad ya y revisa el disco."))
        if (d.get("Wear") or 0) >= 80:
            recs.append(("warn", "SSD muy desgastado", f"{d.get('Name')} ha consumido el {d['Wear']}% de su vida útil."))
        if "HDD" in kind and len(disks) == 1:
            system_hdd = True
    for mount, free, total in volumes():
        pct = free / total * 100 if total else 0
        dl.append((f"Unidad {mount}", f"{fmt_bytes(free)} libres de {fmt_bytes(total)} ({pct:.0f}%)"))
        if pct < 15:
            recs.append(("warn", f"Poco espacio en {mount}", f"Solo queda el {pct:.0f}% libre. Windows rinde peor con el disco casi lleno."))
    sections["disks"] = ("Almacenamiento", dl or [("Estado", "No detectado")])
    if system_hdd:
        recs.append(("warn", "Tu único disco es mecánico", "Pasar a un SSD es la mejora más grande posible: arranque y programas hasta 5-10 veces más rápidos."))
    if not any(r[0] == "warn" for r in recs):
        recs.insert(0, ("ok", "Sin problemas graves", "No detecto fallos de hardware evidentes."))

    sections["os"] = ("Sistema", [
        ("Windows", os_.get("Name", "?")),
        ("Compilación", f"{os_.get('Build', '?')} ({os_.get('Arch', '')})"),
    ])

    drivers = analyze_drivers(hw)
    old = [d for d in drivers if d["old"]]
    if old:
        recs.append(("info", f"{len(old)} driver(s) con fecha antigua", "Mira la lista de drivers más abajo: conviene actualizar la gráfica desde la web del fabricante."))

    return {"sections": sections, "ram": adv, "recs": recs, "drivers": drivers,
            "gpu_names": [g.get("Name", "") for g in gpus]}


# --------------------------------------------------------------------------
# Temperaturas
# --------------------------------------------------------------------------
TEMP_SCRIPT = r"""
$ErrorActionPreference='SilentlyContinue'
$r=@()
foreach($ns in 'root/LibreHardwareMonitor','root/OpenHardwareMonitor'){
  $s = Get-CimInstance -Namespace $ns -ClassName Sensor -Filter "SensorType='Temperature'"
  foreach($x in $s){ $r += [pscustomobject]@{src='hwmon';name=[string]$x.Name;parent=[string]$x.Parent;value=[double]$x.Value} }
}
if(-not $r){
  $z = Get-CimInstance -Namespace root/wmi -ClassName MSAcpi_ThermalZoneTemperature
  foreach($t in $z){ $r += [pscustomobject]@{src='acpi';name='Zona térmica';parent='';value=[math]::Round($t.CurrentTemperature/10-273.15,1)} }
}
Get-PhysicalDisk | ForEach-Object { $c = $_ | Get-StorageReliabilityCounter; if($c.Temperature){ $r += [pscustomobject]@{src='disk';name=[string]$_.FriendlyName;parent='';value=[double]$c.Temperature} } }
ConvertTo-Json -InputObject @($r) -Compress
"""

LIMITS = {"cpu": (80, 90), "gpu": (80, 87), "disk": (60, 70)}   # (alto, crítico)


def _level(kind, v):
    hi, crit = LIMITS.get(kind, (80, 90))
    return "crit" if v >= crit else "warn" if v >= hi else "ok"


def read_temps():
    """Lista de dicts: label, value, kind, level, note."""
    if DEMO:
        return [
            {"label": "CPU (Ryzen 5 5600X)", "value": 54 + random.random() * 6, "kind": "cpu", "level": "ok", "note": ""},
            {"label": "GPU (RTX 3060)", "value": 47 + random.random() * 4, "kind": "gpu", "level": "ok", "note": ""},
            {"label": "Samsung SSD 970 EVO Plus", "value": 41, "kind": "disk", "level": "ok", "note": ""},
        ]
    out = []
    data = as_list(run_ps_json(TEMP_SCRIPT, timeout=25, default=[]))
    for t in data:
        v = t.get("value")
        if not isinstance(v, (int, float)) or v <= 0 or v > 125:
            continue
        name = t.get("name") or ""
        if t["src"] == "disk":
            out.append({"label": name, "value": v, "kind": "disk", "level": _level("disk", v), "note": ""})
        elif t["src"] == "hwmon":
            parent = (t.get("parent") or "").lower()
            if "cpu" in name.lower() or "package" in name.lower() or "core" in name.lower() or "cpu" in parent:
                out.append({"label": f"CPU · {name}", "value": v, "kind": "cpu", "level": _level("cpu", v), "note": ""})
            elif "gpu" in name.lower() or "gpu" in parent:
                out.append({"label": f"GPU · {name}", "value": v, "kind": "gpu", "level": _level("gpu", v), "note": ""})
        else:
            note = "aproximada: Windows no expone el sensor real" if v < 35 else "lectura aproximada de Windows"
            out.append({"label": "Procesador (zona térmica)", "value": v, "kind": "cpu", "level": _level("cpu", v), "note": note})
    if shutil.which("nvidia-smi"):
        q = "name,temperature.gpu,utilization.gpu,clocks.sm,clocks.max.sm"
        rc, o, _ = run_cmd(["nvidia-smi", f"--query-gpu={q},clocks_throttle_reasons.active",
                            "--format=csv,noheader,nounits"], timeout=10)
        if rc != 0:
            rc, o, _ = run_cmd(["nvidia-smi", f"--query-gpu={q}", "--format=csv,noheader,nounits"], timeout=10)
        nv = []
        for line in o.splitlines():
            p = [x.strip() for x in line.split(",")]
            try:
                temp = float(p[1])
            except (IndexError, ValueError):
                continue
            note = ""
            if len(p) > 5:
                try:
                    bits = int(p[5], 16)
                    if bits & (0x08 | 0x20 | 0x40):
                        note = "THROTTLING TÉRMICO: la gráfica está bajando su velocidad por calor"
                except ValueError:
                    pass
            nv.append({"label": f"GPU · {p[0]}", "value": temp, "kind": "gpu",
                       "level": _level("gpu", temp), "note": note})
        if nv:   # nvidia-smi es más fiable que el resto para la gráfica
            out = [t for t in out if t["kind"] != "gpu"] + nv
    return out
