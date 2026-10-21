"""Guía de overclock SEGURO adaptada al procesador, la gráfica y la RAM de este equipo.

No toca nada del sistema: son pasos para hacer a mano con herramientas externas, con límites seguros,
pruebas de estabilidad y cómo volver atrás. Las cifras son orientativas: cada chip es distinto.
"""


def _cpu_section(cpu):
    v, plat, gen = cpu.get("vendor"), cpu.get("platform"), cpu.get("gen")
    name = cpu.get("name") or "tu procesador"
    if cpu.get("mobile"):
        return ("Procesador", f"{name} es de portátil",
                ["En portátiles el límite casi siempre es el calor y la potencia, no el reloj. No te recomiendo tocar voltajes.",
                 "Lo que sí funciona: subir la ventilación (modo «Turbo» del fabricante), usar una base refrigeradora y limpiar polvo.",
                 "Si tu BIOS lo permite, un undervolt pequeño reduce temperatura y mantiene el turbo más tiempo."], "yellow")
    if v == "AMD":
        steps = []
        if cpu.get("x3d"):
            steps = [f"{name} es X3D: la caché extra es sensible al voltaje. NO subas voltajes ni uses PBO con sobreboost de frecuencia.",
                     "Lo único recomendable: Curve Optimizer negativo (undervolt) para bajar temperatura y mantener el turbo más tiempo.",
                     "BIOS → Advanced → AMD Overclocking → Precision Boost Overdrive → Curve Optimizer → All Core → Negative.",
                     "Empieza en -10, pasa pruebas de estabilidad y sube de 5 en 5 hasta un máximo de -25 (cada chip aguanta distinto)."]
        elif plat == "AM4" or (gen and gen <= 5):
            steps = [f"Con {name} un overclock manual de todos los núcleos rinde MENOS que dejar actuar al boost automático. Lo bueno es PBO + Curve Optimizer.",
                     "BIOS → Advanced → AMD Overclocking → Precision Boost Overdrive → Enabled (o Advanced). Límites (PPT/TDC/EDC): «Motherboard».",
                     "Curve Optimizer → All Core → Negative → empieza en 10. Guarda, arranca Windows y haz las pruebas de estabilidad de abajo.",
                     "Si pasa las pruebas, sube a 15, luego 20, y quédate en el último valor 100 % estable (lo normal: entre 15 y 30).",
                     "Opcional: «Max CPU Boost Clock Override» +50 MHz y luego +100 MHz. Si baja la estabilidad, déjalo en 0.",
                     "Vigila la temperatura: los Ryzen 5000 suben a 80-85 °C en carga y es normal. Pasar de 90 °C sostenido NO es normal."]
        else:
            steps = [f"En {name} (AM5) lo recomendable es PBO + Curve Optimizer; la frecuencia manual casi nunca compensa.",
                     "BIOS → Advanced → AMD Overclocking → PBO → Enabled. Curve Optimizer → All Core → Negative, empieza en 15.",
                     "Sube de 5 en 5 hasta -30 como máximo, probando estabilidad cada vez. Tras cada subida, mira los errores WHEA (pestaña Diagnóstico).",
                     "Límite térmico: «Platform Thermal Throttle Limit» en 85-90 °C si quieres menos calor a costa de algo de rendimiento.",
                     "Con EXPO, el voltaje SoC no debe superar 1,30 V. Algunas placas se pasan en «Auto»: revísalo."]
        return ("Procesador", f"{name}: PBO + Curve Optimizer", steps, "green")
    if v == "Intel":
        if not cpu.get("unlocked"):
            return ("Procesador", f"{name}: sin multiplicador desbloqueado",
                    ["Tu procesador no es de la serie K, así que no se puede hacer overclock de frecuencia en la mayoría de placas.",
                     "Lo que SÍ puedes hacer: activar XMP en la BIOS y asegurarte de que los límites de potencia (PL1/PL2) están en «sin límite» o en lo que permite tu refrigeración.",
                     "BIOS → Advanced → CPU Configuration → Power Limits: PL1 = PL2 = el máximo que tu placa recomiende."], "yellow")
        steps = [f"{name} es una K: el overclock manual rinde poco frente al riesgo. Lo más útil es un undervolt: misma velocidad con menos calor.",
                 "Antes de nada, actualiza la BIOS: las generaciones 13 y 14 necesitan el microcódigo reciente para ser estables.",
                 "BIOS → AI Tweaker/OC → CPU Core Voltage → Adaptive → Offset negativo: -0,030 V para empezar. Sube de 10 en 10 mV hasta -0,100 V como máximo.",
                 "Mantén «Intel Default Settings» (o el perfil de potencia «Intel Default») si tu CPU es de 13.ª o 14.ª generación.",
                 "No pases de 1,35 V de forma sostenida ni de 100 °C. Si ves apagones o pantallazos azules, sube el offset hacia 0 de inmediato."]
        return ("Procesador", f"{name}: undervolt, no sobrevoltaje", steps, "green")
    return ("Procesador", "No he reconocido tu procesador",
            ["No puedo darte pasos seguros concretos. Lo más seguro sigue siendo activar XMP/EXPO y mantener temperaturas bajas."], "yellow")


def _gpu_section(gpu):
    v, gen, name = gpu.get("vendor"), gpu.get("gen"), gpu.get("name") or "tu gráfica"
    if v == "NVIDIA":
        undervolt = {20: "unos 1800-1900 MHz a 900 mV", 30: "unos 1800-1900 MHz a 850-875 mV",
                     40: "unos 2700 MHz a 900-925 mV"}.get(gen, "un punto de frecuencia estable a un voltaje un poco menor que el de serie")
        steps = [f"Instala MSI Afterburner (gratis, también vale con otras marcas de tarjeta) y RivaTuner para ver FPS en pantalla.",
                 "sube «Power Limit» y «Temp Limit» al máximo que te deje. Pulsa Aplicar.",
                 "sube «Core Clock» de 25 en 25 MHz. Después de cada subida, 5 minutos de prueba gráfica. Para en el primer cuelgue, parpadeo o artefactos y vuelve al valor anterior.",
                 "sube «Memory Clock» de 100 en 100 MHz. La memoria falla de forma silenciosa: si la puntuación BAJA, te has pasado aunque no veas artefactos.",
                 f"Undervolt (el que más gusta): abre la curva con Ctrl+F. Elige {undervolt}, sube ese punto al reloj objetivo y aplana todo lo de la derecha con Shift+clic. Menos calor y relojes más estables.",
                 "Guarda el perfil en un slot y marca «Aplicar overclock al iniciar» solo cuando pase 1 hora de prueba.",
                 "Si algo va mal: botón «Reset» de Afterburner, o arranca en modo seguro y desinstálalo."]
        return ("Gráfica", f"{name}: MSI Afterburner paso a paso", steps, "green")
    if v == "AMD":
        steps = ["Abre AMD Software: Adrenalin → Rendimiento → Ajuste.",
                 "Prueba primero «Undervolt automático de GPU» y «Ajuste de rendimiento» en modo automático: es lo más seguro.",
                 "Ajuste manual: sube el límite de potencia (+10 %) y baja un poco el voltaje de la GPU a la vez.",
                 "Sube el reloj máximo de 25 en 25 MHz con prueba entre cada subida; para en el primer cuelgue.",
                 "Memoria: activa «Fast Timing» y sube la frecuencia de 20 en 20 MHz. Si baja la puntuación, retrocede."]
        return ("Gráfica", f"{name}: Adrenalin", steps, "green")
    return ("Gráfica", "Gráfica no reconocida",
            ["No he reconocido tu gráfica dedicada, así que no te doy pasos concretos."], "yellow")


def _ram_section(cpu, ram):
    if not ram:
        return ("Memoria RAM", "No pude leer tu RAM", ["Abre la pestaña Análisis y vuelve a generar la guía."], "yellow")
    mtype, target, running = ram.get("type"), ram.get("target"), ram.get("running")
    steps = []
    if running and target and running + 100 < target:
        steps.append(f"PRIMERO: tu RAM va a {running} MHz y tu kit llega a {target} MHz. Activa XMP/EXPO en la BIOS; esto solo ya es mejor que cualquier otro ajuste.")
    else:
        steps.append(f"Tu RAM ya funciona a {running or '?'} MHz (kit: {target or '?'} MHz). Bien.")
    amd = cpu.get("vendor") == "AMD"
    if mtype == "DDR4" and amd:
        steps += ["Ryzen con DDR4: el punto ideal es DDR4-3600 con FCLK a 1800 MHz (relación 1:1). Más de 3800 suele obligar a bajar la relación y rinde peor.",
                  "Si tu kit es de 3200, puedes probar 3600 con 1,40-1,45 V. Si no arranca, vuelve a 3200 y baja los tiempos en su lugar."]
    elif mtype == "DDR5" and amd:
        steps += ["Ryzen con DDR5: el punto ideal es DDR5-6000 con CL30 y FCLK a 2000 MHz. Más rápido casi nunca compensa.",
                  "VDD/VDDQ no pases de 1,40 V y el SoC de 1,30 V."]
    elif mtype == "DDR5":
        steps += ["Intel con DDR5: 6000-6400 en modo Gear 2 es lo estable en la mayoría de placas. Más allá hay que probar mucho.",
                  "VDD/VDDQ no pases de 1,40 V a diario."]
    else:
        steps += ["Intel con DDR4: de 3600 a 4000 MHz en Gear 1 es el rango bueno. No pases de 1,45 V a diario (1,50 V es el máximo absoluto)."]
    steps += ["Apretar tiempos (CL, tRCD, tRP, tRAS): baja de uno en uno, nunca varios a la vez. En Ryzen DDR4 usa «DRAM Calculator for Ryzen» como referencia.",
              "Prueba la RAM al menos 1 hora con TestMem5 (configuración anta777) u OCCT → Memoria. Cualquier error significa que no es estable: sube tiempos o baja la frecuencia.",
              "Una RAM inestable no siempre se cuelga: puede corromper archivos. Por eso la prueba larga es obligatoria."]
    return ("Memoria RAM", f"{mtype or 'RAM'}: del XMP al ajuste fino", steps, "green")


def build(guide):
    """guide = bios.build_guide(). Devuelve (resumen, secciones). Sección: (etiqueta, título, pasos, color)."""
    cpu, gpu, ram = guide["cpu"], guide["gpu"], guide.get("ram")
    rules = ("Reglas de oro", "Antes de tocar nada",
             ["Cambia UNA cosa cada vez y prueba. Si cambias tres y falla, no sabrás cuál fue.",
              "Apunta cada valor que cambias (en papel o en el móvil). Así puedes volver atrás.",
              "Límites de temperatura: CPU máximo 90 °C sostenidos, gráfica máximo 83 °C. Si los pasas, para y mejora la ventilación.",
              "Cómo volver atrás en la BIOS: «Load Optimized Defaults» (F5 o F9). Si no arranca el PC, apaga, quita la pila de la placa 30 segundos y vuelve a ponerla.",
              "Un overclock puede acortar la vida de los componentes si subes voltajes. Esta guía solo usa undervolt y subidas pequeñas.",
              "Las cifras son orientativas: dos chips iguales aguantan distinto. Manda siempre tu prueba de estabilidad, no mi número."], "red")
    tests = ("Pruebas", "Cómo comprobar que es estable",
             ["Gráfica: 3DMark Time Spy Stress Test (debe dar 97 % o más), Unigine Superposition en bucle, o 1 hora de tu juego más exigente.",
              "Procesador: OCCT (CPU) 30 minutos o Cinebench R23 en bucle 30 minutos. Para PBO/undervolt, prueba además con cargas ligeras: cuelgues al estar parado indican un Curve Optimizer demasiado agresivo.",
              "Memoria: TestMem5 (anta777) u OCCT memoria, 1 hora.",
              "Después de las pruebas, abre la pestaña «Diagnóstico» de HellOP y mira los errores WHEA: si aparecen, el ajuste no es estable aunque no se haya colgado.",
              "Criterio: sin cuelgues, sin artefactos, sin errores WHEA y con temperaturas bajo los límites. Si falla algo, vuelve al valor anterior."], "cyan")
    sections = [rules, _gpu_section(gpu), _cpu_section(cpu), _ram_section(cpu, ram), tests]
    summary = f"{cpu.get('name') or '?'}  ·  {gpu.get('name') or '?'}" + (f"  ·  {ram['type']}-{ram['running']}" if ram and ram.get("running") else "")
    return summary, sections
