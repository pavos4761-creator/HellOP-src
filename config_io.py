"""Exportar / importar tu configuración de HellOP a un archivo, para llevarla a otro PC o pasársela a un amigo.

Qué se exporta: los tweaks que tienes aplicados, el perfil de cada juego (qué optimizaciones usa), el modo automático y tu color PRO.
Qué NO se exporta nunca: tu clave de licencia, tu ID de PC, rutas de tu equipo ni tu nombre de usuario.
Al importar no se aplica nada solo: ves la lista y marcas lo que quieres. Los tweaks solo se ofrecen si aplican a ESTE equipo.
"""
import json
import time
from pathlib import Path

import actions
import games
import version
import widgets
from util import DEMO

FORMAT = "hellop-config"
MAX_BYTES = 1_000_000


def build():
    """Diccionario listo para guardar."""
    seen, tw = set(), []
    for e in actions.load_log():
        aid = e.get("aid") or ""
        if aid and not e.get("undone") and e.get("reversible") and aid not in seen:
            seen.add(aid)
            tw.append({"id": aid, "title": str(e.get("title", ""))[:160]})
    g = games.load()
    gl = []
    for x in g["games"]:
        exe = str(x.get("exe") or "").replace("\\", "/").split("/")[-1]
        if exe.lower().endswith(".exe"):
            gl.append({"name": str(x.get("name", exe))[:80], "exe": exe, "profile": {k: bool(v) for k, v in x["profile"].items()
                                                                                       if k in games.DEFAULT_PROFILE}})
    return {"format": FORMAT, "app": "HellOP", "version": version.__version__, "created": time.strftime("%Y-%m-%d"),
            "acento": widgets.acento_actual() if widgets.PRO_THEME else None, "auto": bool(g.get("auto")), "tweaks": tw, "games": gl}


def export(path):
    data = build()
    Path(path).write_text(json.dumps(data, ensure_ascii=False, indent=1), "utf-8")
    return len(data["tweaks"]), len(data["games"])


def read(path):
    """Lee y VALIDA un archivo de configuración. Lanza ValueError si no es válido."""
    p = Path(path)
    if p.stat().st_size > MAX_BYTES:
        raise ValueError("El archivo es demasiado grande para ser una configuración de HellOP.")
    try:
        d = json.loads(p.read_text("utf-8"))
    except (ValueError, UnicodeDecodeError):
        raise ValueError("El archivo no es una configuración de HellOP (no se puede leer).")
    if not isinstance(d, dict) or d.get("format") != FORMAT:
        raise ValueError("El archivo no es una configuración de HellOP.")
    tw = [{"id": str(t["id"])[:200], "title": str(t.get("title", ""))[:160]} for t in (d.get("tweaks") if isinstance(d.get("tweaks"), list) else [])[:300]
          if isinstance(t, dict) and isinstance(t.get("id"), str)]
    gl = []
    for x in (d.get("games") if isinstance(d.get("games"), list) else [])[:200]:
        if isinstance(x, dict) and isinstance(x.get("exe"), str) and x["exe"].lower().endswith(".exe") and "/" not in x["exe"] and "\\" not in x["exe"]:
            prof = x.get("profile") if isinstance(x.get("profile"), dict) else {}
            gl.append({"name": str(x.get("name", x["exe"]))[:80], "exe": x["exe"],
                       "profile": {k: bool(v) for k, v in prof.items() if k in games.DEFAULT_PROFILE}})
    ac = d.get("acento") if d.get("acento") in widgets.ACENTOS else None
    return {"version": str(d.get("version", "?"))[:20], "created": str(d.get("created", ""))[:10], "acento": ac,
            "auto": bool(d.get("auto")), "tweaks": tw, "games": gl}


def applicable_tweaks(cfg, progress=None):
    """Tweaks del archivo que SÍ se pueden aplicar en este PC (y aún no están aplicados): lista de Action."""
    import tweaks
    want = {t["id"] for t in cfg["tweaks"]}
    if not want:
        return []
    return [a for a in tweaks.collect(progress) if a.id in want]


def apply_games(cfg):
    """Pone los perfiles del archivo a los juegos que ya tienes (se emparejan por el nombre del .exe). Devuelve (aplicados, ausentes)."""
    d = games.load()
    mine = {str(g.get("exe") or "").replace("\\", "/").split("/")[-1].lower(): g for g in d["games"]}
    ok, missing = 0, []
    if DEMO:
        return len(cfg["games"]), []
    for x in cfg["games"]:
        g = mine.get(x["exe"].lower())
        if g:
            g["profile"] = {**g["profile"], **x["profile"]}
            ok += 1
        else:
            missing.append(x["name"])
    games.save(d)
    return ok, missing
