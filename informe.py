"""Informe del PC en HTML: un archivo bonito y autónomo (sin internet) con tu nota, tu hardware, lo que te frena y lo que HellOP ha cambiado.
Pensado para guardar, compartir en un foro o enseñar a un técnico."""
import html
import os
import time
import webbrowser

import actions
import puntuacion
import sysinfo
import version
from util import APP_DIR, DEMO


def _e(x):
    return html.escape(str(x if x is not None else "—"))


def _gb(b):
    try:
        return f"{float(b) / 1024 ** 3:.0f} GB"
    except (TypeError, ValueError):
        return "—"


def _filas(pares):
    return "".join(f"<tr><th>{_e(k)}</th><td>{_e(v)}</td></tr>" for k, v in pares if v not in (None, ""))


def construir(res=None):
    hw = {}
    try:
        hw = sysinfo.collect_hardware()
    except Exception:  # noqa: BLE001
        pass
    res = res or puntuacion.ultima() or {"score": 0, "medal": ("Sin medir", "#8a8f98"), "perdidos": []}
    sc, (medalla, col) = res["score"], res["medal"]
    cpu = (sysinfo.as_list(hw.get("cpu")) or [{}])[0] if hasattr(sysinfo, "as_list") else (hw.get("cpu") or [{}])[0]
    gpus, rams, disks = hw.get("gpu") or [], hw.get("ram") or [], hw.get("disks") or []
    board = (hw.get("board") or [{}])[0]
    so = (hw.get("os") or [{}])[0]
    ram_total = sum(r.get("Capacity") or 0 for r in rams)
    rows_hw = [("Procesador", f"{cpu.get('Name', '—')} · {cpu.get('Cores', '?')} núcleos / {cpu.get('Threads', '?')} hilos"),
               ("Placa base", f"{board.get('Maker', '')} {board.get('Model', '')}".strip()),
               ("Memoria RAM", f"{_gb(ram_total)} en {len(rams)} módulo(s)" + (f" · {rams[0].get('Configured')} MHz (kit de {rams[0].get('Speed')} MHz)" if rams else "")),
               ("Sistema", f"{so.get('Name', '—')} (build {so.get('Build', '?')})")]
    for g in gpus:
        rows_hw.append(("Gráfica", f"{g.get('Name', '—')} · {_gb(g.get('VRAM'))} · driver {g.get('Driver', '?')}"))
    for d in disks:
        rows_hw.append(("Disco", f"{d.get('Name', '—')} · {d.get('Media', '')} {d.get('Bus', '')} · {_gb(d.get('Size'))} · salud {d.get('Health', '?')}"))
    try:
        for m, libre, total in sysinfo.volumes():
            rows_hw.append((f"Espacio {m}", f"{_gb(libre)} libres de {_gb(total)}"))
    except Exception:  # noqa: BLE001
        pass
    perdidos = "".join(f"<li><b>−{p} pts</b> {_e(t)}</li>" for t, p, _f in res.get("perdidos", [])) or "<li>Nada que te frene ahora mismo.</li>"
    hechos = [e for e in actions.load_log() if not e.get("undone")][-15:][::-1]
    cambios = "".join(f"<li><span>{_e(e['ts'])}</span> {_e(e['title'])}</li>" for e in hechos) or "<li>Todavía no se ha cambiado nada.</li>"
    ang = 3.14159 * 2 * max(0, min(100, sc)) / 100
    circ = 2 * 3.14159 * 54
    return f"""<!doctype html><html lang="es"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Informe HellOP — {_e(time.strftime('%d/%m/%Y'))}</title>
<style>
:root{{--bg:#120d1d;--p:#1c1430;--l:#3a2a63;--fg:#f3eefb;--mu:#a99cc7;--ac:#b66dff}}
*{{box-sizing:border-box}}body{{margin:0;background:radial-gradient(900px 500px at 10% -10%,#3b2370 0,transparent 60%),radial-gradient(800px 500px at 100% 110%,#5a2a8c55 0,transparent 60%),var(--bg);
color:var(--fg);font:15px/1.55 "Segoe UI",system-ui,sans-serif;padding:40px 18px}}
.w{{max-width:860px;margin:auto}}h1{{font-size:28px;margin:0}}.s{{color:var(--mu);margin:2px 0 26px}}
.c{{background:linear-gradient(160deg,#241a3d,var(--p));border:1px solid var(--l);border-radius:22px;padding:22px 24px;margin-bottom:16px}}
h2{{font-size:13px;letter-spacing:.14em;text-transform:uppercase;color:var(--ac);margin:0 0 12px}}
.n{{display:flex;gap:26px;align-items:center}}.n svg{{flex:none}}.big{{font-size:44px;font-weight:800}}
table{{width:100%;border-collapse:collapse}}th{{text-align:left;color:var(--mu);font-weight:600;width:150px;padding:6px 10px 6px 0;vertical-align:top}}td{{padding:6px 0}}tr+tr{{border-top:1px solid #ffffff10}}
ul{{margin:0;padding-left:20px}}li{{margin:5px 0}}li span{{color:var(--mu);font-size:12px;margin-right:6px}}
footer{{color:var(--mu);font-size:12px;text-align:center;margin-top:24px}}
</style><body><div class="w">
<h1>Informe de tu PC</h1><div class="s">Generado por HellOP v{_e(version.__version__)} · {_e(time.strftime('%d/%m/%Y %H:%M'))}{' · MODO DEMO (datos de ejemplo)' if DEMO else ''}</div>
<div class="c"><h2>Puntuación HellOP</h2><div class="n">
<svg width="130" height="130" viewBox="0 0 130 130"><circle cx="65" cy="65" r="54" fill="none" stroke="#ffffff14" stroke-width="12"/>
<circle cx="65" cy="65" r="54" fill="none" stroke="{_e(col)}" stroke-width="12" stroke-linecap="round" stroke-dasharray="{circ * sc / 100:.1f} {circ:.1f}" transform="rotate(-90 65 65)"/>
<text x="65" y="73" text-anchor="middle" fill="#fff" font-size="30" font-weight="800">{sc}</text></svg>
<div><div class="big" style="color:{_e(col)}">{_e(medalla)}</div><div style="color:var(--mu)">Mide lo bien configurado que está tu PC, no su potencia. Máximo 100.</div></div></div></div>
<div class="c"><h2>Lo que más te frena</h2><ul>{perdidos}</ul></div>
<div class="c"><h2>Tu equipo</h2><table>{_filas(rows_hw)}</table></div>
<div class="c"><h2>Últimos cambios hechos con HellOP</h2><ul>{cambios}</ul></div>
<footer>HellOP no recoge ni envía datos: este informe se ha creado en tu PC y solo está donde tú lo guardes.</footer></div></body></html>"""


def guardar(res=None):
    """Crea el informe en el Escritorio (o en la carpeta de datos si no hay) y devuelve la ruta."""
    destino = os.path.join(os.path.expanduser("~"), "Desktop")
    if not os.path.isdir(destino):
        APP_DIR.mkdir(parents=True, exist_ok=True)
        destino = str(APP_DIR)
    ruta = os.path.join(destino, "Informe_HellOP.html")
    with open(ruta, "w", encoding="utf-8") as f:
        f.write(construir(res))
    return ruta


def abrir(ruta):
    try:
        webbrowser.open("file:///" + ruta.replace("\\", "/"))
    except Exception:  # noqa: BLE001
        pass
