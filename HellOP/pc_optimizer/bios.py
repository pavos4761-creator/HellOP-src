"""Guía de BIOS a medida: qué cambiar para el máximo rendimiento y qué tiempos poner a la RAM.

Los tiempos de RAM y los ajustes de CPU/placa NO se pueden cambiar desde Windows: se hacen en la BIOS.
Esta guía detecta tu plataforma (CPU, placa, RAM, gráfica) y genera pasos concretos con la ruta de menú
según el fabricante de tu placa. Los valores de RAM son PUNTOS DE PARTIDA: hay que probarlos con un test de
estabilidad (ver el aviso en la propia guía).
"""
import json
import re
import shutil
import time
from pathlib import Path

import psutil

import sysinfo
from util import APP_DIR, DEMO, IS_WIN, as_list, fmt_gb, run_cmd, run_ps

CHECK_FILE = APP_DIR / ("bios_checklist_demo.json" if DEMO else "bios_checklist.json")


# --------------------------------------------------------------------------
# Detección de plataforma
# --------------------------------------------------------------------------
def parse_cpu(name, socket=""):
    n = name or ""
    info = {"vendor": "?", "name": n.strip(), "gen": None, "platform": None, "unlocked": False, "x3d": False,
            "mobile": False}
    up = n.upper()
    if "AMD" in up or "RYZEN" in up:
        info["vendor"] = "AMD"
        m = re.search(r"RYZEN\s+(?:\d\s+)?(?:PRO\s+)?(\d)(\d{3})(\w*)", up)
        if m:
            info["gen"] = int(m.group(1))
            suf = m.group(3)
            info["x3d"] = "X3D" in suf
            info["unlocked"] = ("X" in suf) or (info["gen"] >= 7 and not suf.startswith(("G", "U", "H")))
            info["mobile"] = suf.startswith(("U", "H", "HX", "HS"))
        sock = (socket or "").upper()
        if "AM5" in sock or (info["gen"] and info["gen"] >= 7 and not info["mobile"]):
            info["platform"] = "AM5"
        elif "AM4" in sock or (info["gen"] and info["gen"] <= 5):
            info["platform"] = "AM4"
    elif "INTEL" in up or "CORE" in up:
        info["vendor"] = "Intel"
        if "ULTRA" in up:
            info["gen"], info["platform"] = "ultra", "LGA1851"
        else:
            m = re.search(r"I[3579]-(\d{4,5})([A-Z]*)", up)
            if m:
                digits = m.group(1)
                info["gen"] = int(digits[:2]) if len(digits) == 5 else int(digits[0])
                suf = m.group(2)
                info["unlocked"] = "K" in suf
                info["mobile"] = suf.startswith(("U", "H", "P")) and "K" not in suf
                info["platform"] = {12: "LGA1700", 13: "LGA1700", 14: "LGA1700", 10: "LGA1200", 11: "LGA1200"}.get(info["gen"])
    return info


def parse_gpu(name):
    n = (name or "").upper()
    g = {"vendor": "?", "name": name or "?", "rebar": "unknown", "gen": None}
    m = re.search(r"RTX\s*(\d{2})\d{2}", n)
    if "NVIDIA" in n or "GEFORCE" in n or "RTX" in n or "GTX" in n:
        g["vendor"] = "NVIDIA"
        if m:
            g["gen"] = int(m.group(1))
            g["rebar"] = "yes" if g["gen"] >= 30 else "vbios"      # RTX 20: solo con actualización de vBIOS del fabricante
        elif "GTX" in n:
            g["rebar"] = "no"
    elif "RADEON" in n or "AMD" in n:
        g["vendor"] = "AMD"
        m = re.search(r"RX\s*(\d)\d{3}", n)
        if m:
            g["gen"] = int(m.group(1))
            g["rebar"] = "yes" if g["gen"] >= 6 else "no"
    elif "ARC" in n or "INTEL" in n:
        g["vendor"] = "Intel"
        g["rebar"] = "required"
    return g


def board_vendor(maker):
    m = (maker or "").upper()
    if "ASUS" in m:
        return "ASUS"
    if "MSI" in m or "MICRO-STAR" in m:
        return "MSI"
    if "GIGABYTE" in m:
        return "Gigabyte"
    if "ASROCK" in m:
        return "ASRock"
    return "genérica"


MENU = {   # ruta de menú por fabricante de placa
    "xmp": {"ASUS": "Ai Tweaker → Ai Overclock Tuner → XMP / DOCP / EXPO (Perfil 1)",
            "MSI": "OC (pulsa EZ Mode → «A-XMP / EXPO» en la esquina) → Memory Try It! / XMP Profile",
            "Gigabyte": "Tweaker → Extreme Memory Profile (X.M.P.) → Profile 1",
            "ASRock": "OC Tweaker → Load XMP Setting (o «Load EXPO») → Profile 1",
            "genérica": "Busca «XMP», «EXPO», «DOCP» o «A-XMP» en las pestañas OC / Overclocking / Tweaker / AI Tweaker"},
    "rebar": {"ASUS": "Advanced → PCI Subsystem Settings → Above 4G Decoding = Enabled, y Re-Size BAR Support = Enabled",
              "MSI": "Settings → Advanced → PCI Subsystem Settings → Above 4G memory = Enabled, y Re-Size BAR Support = Enabled",
              "Gigabyte": "Settings → IO Ports → Above 4G Decoding = Enabled, y Re-Size BAR Support = Enabled",
              "ASRock": "Advanced → PCI Configuration → Above 4G Decoding = Enabled, y Re-Size BAR = Enabled",
              "genérica": "Busca «Above 4G Decoding» y «Re-Size BAR» / «Smart Access Memory» (AMD) en Advanced / PCI"},
    "csm": {"ASUS": "Boot → CSM (Compatibility Support Module) → Disabled",
            "MSI": "Settings → Boot → CSM Support / Windows 10/11 WHQL Support → Disabled / Enabled",
            "Gigabyte": "Boot → CSM Support → Disabled",
            "ASRock": "Boot → CSM → Disabled",
            "genérica": "Pestaña Boot → CSM / Legacy Support → Disabled (solo UEFI)"},
    "adv": {"ASUS": "Advanced → …", "MSI": "Settings → Advanced → …", "Gigabyte": "Settings / Tweaker → …",
            "ASRock": "Advanced → …", "genérica": "Pestañas Advanced / OC"},
}


def enter_bios_key(vendor):
    return {"ASUS": "Supr (o F2)", "MSI": "Supr", "Gigabyte": "Supr", "ASRock": "F2 (o Supr)"}.get(
        vendor, "Supr o F2 (según tu placa; mira el logo al encender)")


# --------------------------------------------------------------------------
# Estado actual (ReBAR, UEFI, Secure Boot)
# --------------------------------------------------------------------------
def firmware_status():
    """{'uefi': True/False/None, 'secure_boot': ..., 'rebar': True/False/None}"""
    st = {"uefi": None, "secure_boot": None, "rebar": None}
    if DEMO:
        return {"uefi": True, "secure_boot": True, "rebar": False}
    if IS_WIN:
        rc, out, _ = run_ps("$env:firmware_type; try{ Confirm-SecureBootUEFI }catch{ 'NA' }")
        lines = [x.strip() for x in out.splitlines() if x.strip()]
        if lines:
            st["uefi"] = lines[0].upper() == "UEFI"
        if len(lines) > 1 and lines[1] in ("True", "False"):
            st["secure_boot"] = lines[1] == "True"
    if shutil.which("nvidia-smi"):
        rc, out, _ = run_cmd(["nvidia-smi", "-q", "-d", "MEMORY"], timeout=15)
        m = re.search(r"BAR1 Memory Usage\s*\n\s*Total\s*:\s*(\d+)\s*MiB", out)
        if m:
            st["rebar"] = int(m.group(1)) > 512     # 256 MiB = ReBAR desactivado
    return st


# --------------------------------------------------------------------------
# Plan de tiempos de RAM por niveles
# --------------------------------------------------------------------------
def _ns_to_cycles(ns, speed):
    return int(round(ns * speed / 2000.0))


def ram_plan(hw):
    mods = as_list(hw.get("ram"))
    if not mods:
        return None
    mtype = sysinfo._mem_type(mods)
    rated = max((m.get("Speed") or 0) for m in mods)
    running = max((m.get("Configured") or 0) for m in mods) or rated
    part = next((m.get("Part") for m in mods if m.get("Part")), "")
    kit_speed, kit_cl = sysinfo._kit_from_part(part)
    base = {"DDR4": 2666, "DDR5": 4800}.get(mtype, 0)
    speed = kit_speed or rated or 0                      # lo que el kit puede de verdad
    no_profile = bool(speed) and speed <= base and not kit_speed   # kit de velocidad base: no tiene perfil XMP/EXPO
    sweet = {"DDR4": 3600, "DDR5": 6000}.get(mtype)
    target = speed or running or sweet
    cl = kit_cl
    cl_known = bool(kit_cl)
    typical = sysinfo.TYPICAL_TIMINGS.get(target, "")
    if not cl and typical:
        cl = int(re.match(r"CL(\d+)", typical).group(1))
    if typical and cl and not typical.startswith(f"CL{cl}-"):
        typical = ""                                     # no mostrar tiempos «típicos» que contradicen el CL real
    total_gb = sum(m.get("Capacity") or 0 for m in mods) / 1024 ** 3
    count = len(mods)
    plan = {"type": mtype, "target": target, "running": running, "cl": cl, "count": count,
            "total_gb": total_gb, "part": part, "tiers": [], "notes": []}

    # --- Nivel 1: perfil del fabricante
    if no_profile:
        plan["tiers"].append({
            "level": 1, "name": "SEGURO · tu kit es de velocidad base (no trae perfil XMP/EXPO)", "risk": "bajo",
            "rows": [("Frecuencia", f"{mtype}-{target}: ya va a su velocidad; no hay perfil que activar"),
                     ("Qué hacer", f"Asegúrate de tener dual channel y de que la BIOS no la deja por debajo de {target} MHz."),
                     ("Mejora real", f"Cambiar a un kit con perfil XMP/EXPO ({mtype}-{sweet} es el punto ideal) o afinar tiempos a mano (nivel 2). "
                                     "Pasar de una memoria base a una rápida es lo que más se nota.")]})
    else:
      plan["tiers"].append({
        "level": 1, "name": "SEGURO · perfil del fabricante (lo que más rendimiento da)",
        "risk": "bajo",
        "rows": [("Frecuencia", f"{mtype}-{target}" + (f" ({running} MHz ahora → {target} MHz)" if running and running < target - 100 else "")),
                 ("Tiempos", f"CL{cl}" + (f"  ({typical})" if typical else "") if cl else (typical or "los del perfil")),
                 ("Tensión (VDIMM)", "la que marque el perfil (normalmente 1,35 V en DDR4; 1,25–1,40 V en DDR5)"),
                 ("Cómo", "Activa XMP / EXPO / DOCP y listo. Es 5–15 % más de ancho de banda que a velocidad base.")],
    })

    # --- Nivel 2: afinado seguro
    if mtype == "DDR4" and cl:
        trcd = cl
        tras = cl + trcd
        rows = [("Frecuencia", f"DDR4-{target}"),
                ("tCL / tRCD / tRP / tRAS", f"{cl} / {trcd} / {trcd} / {tras}   (si no arranca o falla un test: sube tRCD y tRP de 1 en 1)"),
                ("tRC", f"{tras + trcd}   (= tRAS + tRP)"),
                ("tRRD_S / tRRD_L / tFAW", "4 / 6 / 16   (tFAW = 4 × tRRD_S)"),
                ("tWR / tRTP / tWTR_S / tWTR_L", "16 / 8 / 4 / 8"),
                ("tRFC", f"{_ns_to_cycles(300, target)}   (≈ 300 ns; si falla, sube a {_ns_to_cycles(340, target)}; B-die aguanta ≈ 260 ns = {_ns_to_cycles(260, target)})"),
                ("tREFI", "32768   (sube hacia 65535 solo con buen flujo de aire; da ancho de banda extra)"),
                ("Command Rate / Gear Down", "1T   (en AMD: Gear Down Mode = Disabled; si da errores vuelve a 2T)"),
                ("Tensión (VDIMM)", "1,35–1,40 V   (máx. 1,45 V a diario con ventilación)")]
        if not cl_known:
            rows.insert(0, ("Ojo: CL estimado", f"No pude leer el CL de tu kit (he supuesto CL{cl}). Usa como tCL el que pone en la etiqueta del módulo "
                                                "y calcula el resto con la misma regla (tRCD = tRP = tCL; tRAS = tCL + tRCD). Nunca pongas un tCL menor que el de la etiqueta."))
        plan["tiers"].append({"level": 2, "name": "AFINADO · puntos de partida que funcionan en la mayoría de kits",
                              "risk": "medio", "rows": rows})
    elif mtype == "DDR5":
        rows = [("Frecuencia", f"DDR5-{target}" + (f" CL{cl}" if cl else "")),
                ("tRCD / tRP", "bájalos 2 puntos respecto al perfil (ej.: 38 → 36 → 34) hasta que falle un test y vuelve al anterior"),
                ("tRFC", f"≈ 10–15 % menos que el perfil (prueba paso a paso). Referencia: {_ns_to_cycles(240, target)}–{_ns_to_cycles(300, target)} ciclos"),
                ("tREFI", "sube a 32768–65535 SOLO si la RAM se mantiene por debajo de ~50 °C (DDR5 es sensible al calor)"),
                ("Tensión (VDIMM / VDDQ)", "no pases de 1,40 V a diario; vigila la temperatura del módulo"),
                ("Si tienes AMD AM5", "SoC voltage ≤ 1,25 V (AMD limita a 1,3 V). Con DDR5-6000: UCLK = MEMCLK (modo 1:1) y FCLK 2000")]
        plan["tiers"].append({"level": 2, "name": "AFINADO · puntos de partida para DDR5", "risk": "medio", "rows": rows})
    else:
        plan["tiers"].append({"level": 2, "name": "AFINADO", "risk": "medio",
                              "rows": [("Nota", "No pude leer los tiempos de tu kit. Activa el perfil XMP/EXPO y mira el CL en la etiqueta del módulo.")]})

    # --- Nivel 3: extremo
    if mtype == "DDR4":
        rows = [("Si tus chips son Samsung B-die", f"DDR4-{max(target, 3600)} CL14-14-14-28 con ~1,45 V; tRFC ≈ 260 ns; tREFI 65535"),
                ("Si son Micron Rev.E / Hynix CJR/DJR", "Usa «DRAM Calculator for Ryzen» (también vale como guía en Intel): te da tiempos seguros/rápidos según el chip"),
                ("¿Qué chips tengo?", "Descarga «Thaiphoon Burner» (gratis): lee el SPD de tu kit y te dice el fabricante del chip"),
                ("Tensión", "no pases de 1,50 V ni de 45–50 °C en los módulos")]
    else:
        rows = [("Frecuencias altas", "En AM5, DDR5-6000 CL30 es el punto ideal; subir más rara vez compensa por el límite de FCLK/UCLK."),
                ("En Intel 13/14.ª gen.", "Cada procesador aguanta una frecuencia distinta (6400–7600+). Sube de 200 en 200 MHz con test entre medias."),
                ("Tensiones", "VDDQ/VDD2 y SA/IMC también influyen: súbelos solo de 0,02 V en 0,02 V.")]
    plan["tiers"].append({"level": 3, "name": "EXTREMO · solo si sabes lo que haces", "risk": "alto", "rows": rows})

    plan["notes"] = [
        "OBLIGATORIO tras tocar tiempos o tensiones: pasar un test de estabilidad. Recomendado: TestMem5 (con el perfil «anta777 Extreme») "
        "o Karhu RAM Test ≥ 1 hora, o MemTest86 con 4 pasadas. Un PC que arranca no es un PC estable.",
        "Un error de RAM no siempre se ve como un pantallazo azul: también corrompe archivos en silencio. Si dudas, vuelve al nivel 1.",
        "Los módulos deben ir en dual channel (2 o 4 módulos iguales) y en las ranuras que indica el manual (normalmente A2 y B2).",
    ]
    if count == 1:
        plan["notes"].insert(0, "Ahora mismo tienes UN solo módulo (canal único): pasar a dos módulos iguales da más rendimiento que cualquier ajuste de tiempos.")
    return plan


# --------------------------------------------------------------------------
# Checklist de BIOS
# --------------------------------------------------------------------------
def build_items(hw, cpu, gpu, vendor):
    items = []

    def add(id, area, title, where, set_to, why, effect, risk="bajo", note=""):
        items.append({"id": id, "area": area, "title": title, "where": where, "set_to": set_to, "why": why,
                      "effect": effect, "risk": risk, "note": note})

    add("update", "Antes de empezar", "Actualiza la BIOS a la última versión estable",
        "Web del fabricante de tu placa → Soporte → tu modelo → BIOS (usa la función de actualización de la propia BIOS o USB BIOS Flashback)",
        "Última versión estable",
        "Mejora estabilidad, compatibilidad de memoria y rendimiento (microcódigo / AGESA). En AMD X3D y en Intel 13.ª/14.ª gen. es especialmente importante.",
        "real", "medio",
        "Nunca apagues el PC durante la actualización. Si la placa tiene BIOS Flashback, úsalo. Si tu BIOS ya funciona y no tienes problemas, es opcional.")
    if cpu["vendor"] == "Intel" and cpu["gen"] in (13, 14):
        add("intel_microcode", "Antes de empezar", "Intel 13.ª/14.ª gen.: BIOS con el microcódigo de estabilidad más reciente (0x12B o superior)",
            "Web de tu placa → BIOS más reciente; después, en la BIOS: perfil «Intel Default Settings» / «Baseline»",
            "BIOS reciente + perfil Intel por defecto",
            "Los procesadores 13.ª/14.ª gen. pueden degradarse por exceso de tensión; los parches de Intel lo evitan. Ante todo, que el procesador no se estropee.",
            "real", "bajo")

    add("xmp", "Memoria", "Activa el perfil de memoria (XMP / EXPO / DOCP)", MENU["xmp"][vendor],
        "Perfil 1",
        "Sin esto tu RAM va a la velocidad base (p. ej. 2133 o 4800 MHz) y pierdes un 5–15 % de ancho de banda. Es el ajuste de BIOS que más se nota.",
        "real", "bajo", "Si el PC no arranca, la BIOS vuelve sola a valores seguros tras 2–3 reinicios.")

    if gpu["rebar"] in ("yes", "required"):
        add("rebar", "Gráfica", "Resizable BAR + Above 4G Decoding", MENU["rebar"][vendor],
            "Enabled (primero Above 4G Decoding, luego Re-Size BAR)",
            "La CPU puede acceder a toda la memoria de la gráfica de golpe, no en trozos de 256 MB. Gana de 0 a 10 % en muchos juegos; en alguno más.",
            "depende", "bajo", "Requiere arrancar en modo UEFI (ver el punto de CSM) y driver reciente. Puedes comprobar si está activo en esta pantalla.")
    elif gpu["rebar"] == "vbios":
        add("rebar", "Gráfica", "Resizable BAR (RTX serie 20): solo si tu fabricante publicó actualización de vBIOS de la gráfica", MENU["rebar"][vendor],
            "Enabled (solo tras actualizar el vBIOS de la gráfica)",
            "Las RTX 20 no lo traen activado de serie; algunos fabricantes (MSI, Gigabyte, ASUS…) han publicado una actualización de vBIOS para ciertos modelos.",
            "depende", "medio",
            "Busca en la web de tu fabricante «Resizable BAR» + tu modelo exacto. Actualizar el vBIOS de la gráfica tiene riesgo: solo con el archivo oficial.")
    if gpu["rebar"] in ("yes", "required", "vbios"):
        add("csm", "Gráfica", "CSM desactivado (arranque solo UEFI)", MENU["csm"][vendor], "Disabled",
            "Resizable BAR necesita arrancar en UEFI puro. Además es requisito de Windows 11 y de Secure Boot.",
            "depende", "medio",
            "Antes de hacerlo, comprueba abajo que tu Windows arranca en modo UEFI. Si está en modo Legacy/MBR, Windows no arrancará.")

    add("pcie", "Gráfica", "Ranura PCIe de la gráfica a la generación máxima (no «Auto»)",
        MENU["adv"][vendor].replace("…", "PCI Subsystem Settings → PCIEX16 Link Speed"), "Gen 3 / Gen 4 / Gen 5 según tu gráfica y placa",
        "Evita que la placa negocie una velocidad menor. La diferencia en juegos es mínima, pero es gratis.", "mínimo", "bajo")

    add("fans", "Refrigeración", "Curva de ventiladores más agresiva", "Q-Fan / Smart Fan / Fan Xpert / Hardware Monitor (según fabricante)",
        "Perfil «Performance» o curva manual que llegue al 100 % a ~75 °C",
        "Un procesador o gráfica caliente baja su frecuencia (thermal throttling). Con buena refrigeración sostienes el boost más tiempo. Es lo que más importa si al tope vas justo.",
        "real", "bajo")

    # ----- AMD
    if cpu["vendor"] == "AMD":
        add("amd_boost", "Procesador", "Core Performance Boost = Enabled / Auto", MENU["adv"][vendor].replace("…", "AMD CBS → CPU Common Options → Core Performance Boost"),
            "Enabled / Auto", "Es el turbo de AMD. Debe estar activado (casi siempre ya lo está).", "real", "bajo")
        if cpu["platform"] == "AM4" and isinstance(cpu["gen"], int) and cpu["gen"] >= 3:
            add("amd_pbo", "Procesador", "Precision Boost Overdrive (PBO) + Curve Optimizer",
                MENU["adv"][vendor].replace("…", "AMD Overclocking → Precision Boost Overdrive → Advanced → Curve Optimizer"),
                "PBO = Enabled / Advanced; Curve Optimizer = All Core, Negative, magnitud 10 → sube a 20 → 30 probando",
                "Curve Optimizer baja el voltaje a la misma frecuencia: la CPU sostiene más boost con menos calor. Ganas 3–8 % en multi-hilo sin riesgo para el chip.",
                "real" if cpu["gen"] >= 5 else "pequeño", "medio",
                "Si hay reinicios, cuelgues en reposo o errores WHEA, reduce la magnitud. Ryzen 5000 (Zen 3) soporta Curve Optimizer; Ryzen 3000 usa solo PBO." +
                (" En el 5800X3D el multiplicador y los voltajes están bloqueados por AMD." if cpu["x3d"] and cpu["gen"] == 5 else ""))
            add("amd_fclk", "Memoria", "FCLK = la mitad de la velocidad de la RAM (modo 1:1)",
                MENU["adv"][vendor].replace("…", "AMD Overclocking → Infinity Fabric Frequency and Dividers (FCLK)"),
                "DDR4-3600 → FCLK 1800 MHz · DDR4-3800 → FCLK 1900 MHz · DDR4-3200 → FCLK 1600 MHz",
                "Con FCLK = MCLK la latencia entre núcleos y memoria es la menor posible. Por encima de FCLK 1900 la mayoría de chips no es estable.",
                "real", "bajo", "«Auto» suele hacerlo bien hasta 3600. Solo hace falta tocarlo si usas RAM de más de 3600 MHz.")
        if cpu["platform"] == "AM5":
            add("am5_pbo", "Procesador", "PBO + Curve Optimizer (AM5)",
                MENU["adv"][vendor].replace("…", "AMD Overclocking → Precision Boost Overdrive → Advanced → Curve Optimizer"),
                "Curve Optimizer = All Core, Negative, magnitud 15 → sube a 25 → 35 probando" +
                (" · NO subas los límites de potencia en X3D" if cpu["x3d"] else ""),
                "Baja voltaje a igual frecuencia: más boost sostenido con menos temperatura.",
                "real", "medio", "Si ves reinicios o errores WHEA, reduce la magnitud. En los X3D no merece la pena subir PPT/TDC/EDC.")
            add("am5_mem", "Memoria", "DDR5-6000 con EXPO: UCLK = MEMCLK (1:1) y FCLK 2000",
                MENU["adv"][vendor].replace("…", "AMD Overclocking → Infinity Fabric / UCLK DIV1 MODE"),
                "EXPO 6000 + UCLK DIV1 MODE = UCLK=MEMCLK + FCLK 2000 MHz; SoC voltage ≤ 1,25 V",
                "6000 MT/s en 1:1 es el punto ideal de latencia en AM5. Por encima de 6400 se pierde el modo 1:1 y suele salir peor.",
                "real", "medio", "Vigila el voltaje SoC: nunca por encima de lo que permite tu BIOS (AMD lo limita a 1,3 V).")
        add("amd_cstate", "Procesador", "Global C-State Control: déjalo en Auto (NO lo desactives)",
            MENU["adv"][vendor].replace("…", "AMD CBS → CPU Common Options → Global C-state Control"), "Auto",
            "Desactivarlo en Ryzen suele bajar el boost de un núcleo porque los demás no pueden dormir. Lo he dejado como «no tocar» a propósito.",
            "mínimo", "bajo")
    # ----- Intel
    if cpu["vendor"] == "Intel":
        add("intel_turbo", "Procesador", "Intel Turbo Boost + Speed Shift = Enabled", MENU["adv"][vendor].replace("…", "CPU Configuration → Intel Turbo Boost Technology / Intel Speed Shift"),
            "Enabled", "Turbo es el boost de Intel; Speed Shift deja que la CPU cambie de frecuencia en milisegundos (menos latencia).", "real", "bajo")
        if cpu["unlocked"]:
            add("intel_power", "Procesador", "Límites de potencia: sin recorte (solo con buena refrigeración)",
                "OC / Tweaker → Long Duration Package Power Limit (PL1), Short Duration (PL2), Tau",
                "Perfil «Extreme / Performance» de Intel o PL1 = PL2 = el máximo de tu CPU; Tau = ilimitado",
                "El modo por defecto de algunas placas limita la potencia; quitar el límite mantiene el boost en cargas largas.",
                "pequeño", "medio", "Más calor y más consumo. Con refrigeración justa déjalo en el perfil por defecto de Intel.")
        add("intel_cstate", "Procesador", "C-States de Intel: Enabled (o desactivar C6/C7 si quieres la menor latencia)",
            MENU["adv"][vendor].replace("…", "CPU Configuration → CPU C-states / Package C State Limit"),
            "Por defecto Enabled. Para latencia extrema: C1E = Disabled, Package C State = C0/C1",
            "Evita que los núcleos se duerman profundo y tarden microsegundos en despertar. A cambio: más consumo y calor en reposo.",
            "pequeño", "medio")
        if cpu["platform"] in ("LGA1700", "LGA1851") and sysinfo._mem_type(as_list(hw.get("ram"))) == "DDR4":
            add("intel_gear", "Memoria", "Memory Gear 1 con DDR4", MENU["adv"][vendor].replace("…", "Memory Controller → Gear Mode"),
                "Gear 1 (DDR4)", "Con DDR4, Gear 1 da la menor latencia (el controlador va a la misma velocidad que la RAM).", "real", "bajo")

    add("virt", "Seguridad ↔ rendimiento", "Virtualización (SVM en AMD / VT-x en Intel): desactivar solo si no la usas",
        MENU["adv"][vendor].replace("…", "CPU Configuration → SVM Mode (AMD) / Intel Virtualization Technology (Intel)"), "Disabled",
        "Sin virtualización Windows no puede activar VBS/Integridad de memoria, lo que libera rendimiento en juegos.",
        "depende", "medio",
        "Dejarán de funcionar WSL2, Docker, máquinas virtuales y emuladores de Android (BlueStacks, etc.). Si los usas, déjala activada.")
    add("fastboot", "Arranque", "Fast Boot = Enabled", "Boot → Fast Boot", "Enabled",
        "Arranca más rápido saltándose pruebas de hardware. No afecta a los FPS.", "mínimo", "bajo",
        "Si alguna vez no te deja entrar a la BIOS, mantén pulsada la tecla Supr/F2 con el PC apagado al encender o usa el botón de la app «Reiniciar a la BIOS».")
    add("unused", "Limpieza de BIOS", "Desactiva dispositivos integrados que no uses", MENU["adv"][vendor].replace("…", "Onboard Devices Configuration"),
        "Desactivar: Wi-Fi/Bluetooth si usas cable; audio integrado si usas DAC/USB; puertos serie/COM; RGB que no uses",
        "Cada dispositivo activo carga drivers y genera interrupciones. Quitar los que no uses reduce un poco el ruido de fondo.",
        "mínimo", "bajo")
    return items


# --------------------------------------------------------------------------
def build_guide(hw=None):
    hw = hw or sysinfo.collect_hardware()
    for k in ("cpu", "board", "bios", "ram", "gpu"):
        hw[k] = as_list(hw.get(k))
    c0 = hw["cpu"][0] if hw["cpu"] else {}
    cpu = parse_cpu(c0.get("Name", ""), c0.get("Socket", ""))
    gpu_list = [parse_gpu(g.get("Name")) for g in hw["gpu"]]
    gpu = next((g for g in gpu_list if g["vendor"] in ("NVIDIA", "AMD", "Intel") and
                not re.search(r"graphics|uhd|iris|vega \d", g["name"], re.I)), gpu_list[0] if gpu_list else parse_gpu(""))
    board = hw["board"][0] if hw["board"] else {}
    vendor = board_vendor(board.get("Maker", ""))
    laptop = not (DEMO or psutil.sensors_battery() is None)
    plan = ram_plan(hw)
    platform = [("Procesador", cpu["name"] or "?"),
                ("Placa base", f"{board.get('Maker', '?')} {board.get('Model', '')}".strip()),
                ("BIOS actual", f"{(hw['bios'] or [{}])[0].get('Version', '?')} ({(hw['bios'] or [{}])[0].get('Date') or 'sin fecha'})"),
                ("Memoria", f"{plan['type']} · {plan['count']} × {fmt_gb((hw['ram'][0].get('Capacity') or 0))} · {plan['running']} MHz ahora" if plan else "?"),
                ("Gráfica", gpu["name"])]
    return {"platform": platform, "cpu": cpu, "gpu": gpu, "vendor": vendor, "laptop": laptop,
            "enter_key": enter_bios_key(vendor), "ram": plan, "items": build_items(hw, cpu, gpu, vendor),
            "fw": firmware_status(), "gpu_tips": gpu_tips(gpu)}


def gpu_tips(gpu):
    if gpu["vendor"] == "NVIDIA":
        return [("Panel de control NVIDIA → Administrar configuración 3D", [
            "Modo de administración de energía = Preferir el máximo rendimiento",
            "Modo de baja latencia = Ultra (o «Activado» si el juego tiene NVIDIA Reflex: úsalo en el juego)",
            "Tamaño de la caché de sombreadores = Ilimitado (o 10 GB)",
            "Sincronización vertical = Desactivada (si tu monitor es G-SYNC, déjala en «Usar configuración de la aplicación» y activa G-SYNC)",
            "Optimización con subprocesos = Automática"]),
            ("Windows → Configuración → Sistema → Pantalla → Gráficos", [
                "Programación de GPU acelerada por hardware: prueba activada y desactivada en tu juego favorito y quédate con la que dé mejores mínimos"])]
    if gpu["vendor"] == "AMD":
        return [("AMD Software: Adrenalin", [
            "Rendimiento → Ajuste → Ajuste manual: déjalo en Auto o usa un perfil «Gaming»",
            "Radeon Anti-Lag = Activado (menos latencia de entrada)",
            "Radeon Chill = Desactivado (limita FPS)",
            "Radeon Boost = Desactivado si quieres calidad constante",
            "Caché de sombreadores = AMD optimizada / Activada"])]
    return [("Gráfica", ["No detecté una gráfica dedicada compatible con estos consejos."])]


# --------------------------------------------------------------------------
# Progreso del checklist
# --------------------------------------------------------------------------
def load_checks():
    try:
        return json.loads(CHECK_FILE.read_text("utf-8"))
    except Exception:  # noqa: BLE001
        return {}


def save_checks(d):
    try:
        CHECK_FILE.write_text(json.dumps(d), "utf-8")
    except OSError:
        pass


# --------------------------------------------------------------------------
# Exportar a TXT (para consultarlo en el móvil mientras estás dentro de la BIOS)
# --------------------------------------------------------------------------
def export_text(g):
    L = ["GUÍA DE BIOS PARA MÁXIMO RENDIMIENTO — HellOP", time.strftime("%d/%m/%Y"), "=" * 62, ""]
    for k, v in g["platform"]:
        L.append(f"{k:<12}: {v}")
    L += ["", f"Tecla para entrar a la BIOS: {g['enter_key']}",
          "Desde Windows: Configuración → Sistema → Recuperación → Inicio avanzado → Solucionar problemas → Opciones avanzadas → Configuración de firmware UEFI", ""]
    if g["ram"]:
        L += ["TIEMPOS DE RAM", "-" * 62]
        for t in g["ram"]["tiers"]:
            L += [f"[Nivel {t['level']}] {t['name']}  (riesgo {t['risk']})"] + [f"   {a}: {b}" for a, b in t["rows"]] + [""]
        L += ["IMPORTANTE:"] + [f" - {n}" for n in g["ram"]["notes"]] + [""]
    L += ["AJUSTES DE BIOS (marca los que vayas haciendo)", "-" * 62]
    for it in g["items"]:
        L += [f"[ ] {it['title']}", f"    Dónde : {it['where']}", f"    Poner : {it['set_to']}",
              f"    Por qué: {it['why']}", f"    Efecto: {it['effect']} · Riesgo: {it['risk']}"]
        if it["note"]:
            L.append(f"    Ojo   : {it['note']}")
        L.append("")
    for title, tips in g["gpu_tips"]:
        L += [title, "-" * 62] + [f" - {t}" for t in tips] + [""]
    L += ["Si tras un cambio el PC no arranca: apaga, quita la pila CMOS 30 s o usa el botón/jumper Clear CMOS de la placa.", ""]
    return "\n".join(L)


def export_to_desktop(g):
    base = Path.home() / "Desktop"
    if not base.exists():
        base = Path.home()
    path = base / "Guia_BIOS_HellOP.txt"
    path.write_text(export_text(g), "utf-8")
    return path


def reboot_to_firmware():
    """Reinicia directamente a la pantalla de la BIOS/UEFI (solo Windows en modo UEFI)."""
    if DEMO or not IS_WIN:
        return True, "(demo) Se reiniciaría a la BIOS"
    rc, out, err = run_cmd(["shutdown", "/r", "/fw", "/t", "10"])
    return rc == 0, (out or err or "")
