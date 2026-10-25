"""«Qué pieza mejorar»: dice con honestidad qué te frena y si te conviene (o no) gastar dinero.

Usa datos reales de TU equipo: RAM (capacidad, canales, velocidad), discos y, si mides un juego con PresentMon, si el
límite lo pone la gráfica o el procesador. No inventa nada: si no hay datos suficientes lo dice.
Prioridad:  0 = hazlo ya (gratis o crítico) · 1 = merece la pena · 2 = opcional / dato útil · 3 = no hace falta.
"""
import sysinfo
from util import DEMO

PRIO_TXT = {0: "HAZLO YA", 1: "MERECE LA PENA", 2: "OPCIONAL", 3: "NO HACE FALTA"}


def _item(key, part, prio, title, why, cost):
    return {"key": key, "part": part, "prio": prio, "title": title, "why": why, "cost": cost}


def diagnose(hw, ram, hdd_games, m=None):
    """Lista ordenada de recomendaciones. `m` = medición de un juego (fps.analyze) o None."""
    items = []
    mods = hw.get("ram") or []
    gb = sum((x.get("Capacity") or 0) for x in mods) / 1024 ** 3
    notes = ram["notes"] if ram else []
    single = any("canal único" in n[1] for n in notes)

    # ---- RAM
    if mods:
        if ram and ram["level"] == "warn":
            items.append(_item("xmp", "RAM", 0, "Activa el perfil XMP/EXPO de tu RAM", "Tu memoria va más lenta de lo que su kit permite. "
                               "Es un ajuste de BIOS de 2 minutos y gana FPS en juegos limitados por el procesador. Mira la guía en la página BIOS.", "gratis"))
        if gb < 8:
            items.append(_item("ram", "RAM", 0, f"Solo tienes {gb:.0f} GB de RAM", "Es poca para Windows y juegos actuales: verás tirones y cierres. "
                               "Subir a 16 GB (2 módulos iguales) es la mejora más barata y notable.", "barato"))
        elif gb < 16:
            items.append(_item("ram", "RAM", 1, f"{gb:.0f} GB de RAM: justa", "Muchos juegos recomiendan 16 GB y con Discord y el navegador abiertos se queda corta. "
                               "Pasar a 16 GB en dos módulos iguales también te da dual channel.", "barato"))
        elif single:
            items.append(_item("channel", "RAM", 1, "Tu RAM está en canal único", "Un segundo módulo igual al que tienes duplica el ancho de banda. "
                               "Se nota en juegos limitados por el procesador (sobre todo Ryzen).", "barato"))
        else:
            items.append(_item("ram", "RAM", 3, f"RAM: {gb:.0f} GB, bien", "No necesitas más para jugar. Más de 16-32 GB solo ayuda si editas vídeo o haces streaming.", ""))
        if single and gb < 16 and not any(i["key"] == "channel" for i in items):
            items.append(_item("channel", "RAM", 1, "Y además está en canal único", "Al ampliar, compra dos módulos iguales para activar el dual channel.", "barato"))

    # ---- Disco
    disks = hw.get("disks") or []
    kinds = [sysinfo.disk_kind(d) for d in disks]
    has_ssd = any("SSD" in k for k in kinds)
    if disks and not has_ssd:
        items.append(_item("ssd", "Disco", 0, "No tienes ningún SSD", "Con un disco duro el arranque, las cargas y los tirones al entrar en zonas nuevas "
                           "son mucho peores. Un SSD es la mejora más grande y más barata que puedes hacer.", "barato"))
    elif hdd_games:
        items.append(_item("ssd", "Disco", 1, "Tienes juegos en un disco duro mecánico", "Mueve esos juegos a tu SSD: " + ", ".join(hdd_games[:4])
                           + ". Es gratis si tienes hueco y quita tirones al cargar.", "gratis"))
    elif disks:
        items.append(_item("ssd", "Disco", 3, "Disco: bien", "Tus juegos están en SSD. Aquí no hay nada que ganar.", ""))

    # ---- Gráfica / procesador (solo con medición real)
    gpu_pct = m.get("gpu_pct") if m else None
    cpu = (hw.get("cpu") or [{}])[0]
    cores = cpu.get("Cores") or 0
    if gpu_pct is None:
        items.append(_item("measure", "CPU/GPU", 2, "Para saber si limita la gráfica o el procesador hay que medir un juego",
                           "Sin medir no puedo decírtelo y no voy a adivinar. Pulsa «Medir un juego» con tu juego abierto: "
                           "te diré cuál de las dos piezas va al límite.", "gratis"))
    elif gpu_pct >= 90:
        items.append(_item("gpu", "Gráfica", 1, "En este juego limita la GRÁFICA", f"La gráfica va al {gpu_pct} % del tiempo de cada fotograma. "
                           "Antes de comprar: bajar sombras, efectos o la resolución da FPS gratis. Si quieres más FPS con calidad alta, "
                           "la pieza a cambiar es la gráfica.", "caro"))
        items.append(_item("cpu", "Procesador", 3, "El procesador no es el límite aquí", "Cambiarlo casi no te daría FPS en este juego.", ""))
    elif gpu_pct <= 65:
        cpu_note = f" Tienes {cores} núcleos." if cores else ""
        items.append(_item("cpu", "Procesador", 1, "En este juego limita el PROCESADOR (o la RAM)", f"La gráfica solo trabaja el {gpu_pct} % del tiempo y espera "
                           f"a la CPU.{cpu_note} Una gráfica más potente casi no daría FPS. Antes de cambiar el procesador: activa el XMP, usa dual "
                           "channel y cierra programas de fondo; si ya está todo bien, entonces sí, el procesador.", "medio"))
        items.append(_item("gpu", "Gráfica", 3, "La gráfica va sobrada", "Cambiarla ahora sería tirar el dinero en este juego.", ""))
    else:
        items.append(_item("balance", "CPU/GPU", 3, "Tu PC está equilibrado en este juego", f"La gráfica va al {gpu_pct} %: ninguna pieza frena claramente a la otra. "
                           "Para ganar FPS, ajusta los gráficos del juego antes de gastar dinero.", ""))
    if m and m.get("low1") and m.get("avg") and m["low1"] < 0.6 * m["avg"] and m.get("stutter_per_min", 0) >= 15:
        items.append(_item("stutter", "Tirones", 2, "Tienes tirones aunque la media sea buena", "Suelen venir de RAM justa, un disco lento, programas de fondo o calor, "
                           "no de que te falte potencia. Mira «Salud del PC», «Gestor de arranque» y «Rendimiento oculto».", "gratis"))

    items.sort(key=lambda i: i["prio"])
    return items


def summary(items):
    """(texto, color) con la conclusión honesta."""
    top = [i for i in items if i["prio"] <= 1]
    if top:
        i = top[0]
        coste = {"gratis": "no cuesta nada", "barato": "es barato", "medio": "cuesta algo", "caro": "es la inversión grande"}.get(i["cost"], "")
        return f"Lo primero que haría: {i['title'].rstrip('.')}" + (f" ({coste})." if coste else "."), "yellow" if i["prio"] else "red"
    if any(i["key"] == "measure" for i in items):
        return "Con lo que veo no hay nada urgente. Mide un juego para saber si la gráfica o el procesador va justo.", "cyan"
    return "No compres nada: no veo ningún cuello de botella claro. Ajusta los gráficos del juego y listo.", "green"


def run(m=None, progress=lambda s: None):
    """Lee tu equipo y devuelve (resumen, items, líneas de hardware)."""
    progress("Leyendo tu hardware…")
    hw = sysinfo.collect_hardware()
    ram = sysinfo.ram_advice(hw)
    progress("Mirando dónde están tus juegos…")
    try:
        import hidden
        hdd = hidden.games_on_hdd()
    except Exception:  # noqa: BLE001
        hdd = []
    items = diagnose(hw, ram, hdd, m)
    cpu = (hw.get("cpu") or [{}])[0]
    gpu = (hw.get("gpu") or [{}])[0]
    mods = hw.get("ram") or []
    gb = sum((x.get("Capacity") or 0) for x in mods) / 1024 ** 3
    specs = [("Procesador", f"{cpu.get('Name', '?')} ({cpu.get('Cores', '?')} núcleos / {cpu.get('Threads', '?')} hilos)"),
             ("Gráfica", gpu.get("Name", "?")),
             ("RAM", f"{gb:.0f} GB en {len(mods)} módulo(s)")]
    return summary(items), items, specs
