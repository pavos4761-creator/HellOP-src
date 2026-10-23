"""Ajustes de gráficos por juego: edita el archivo de configuración del propio juego (con copia y deshacer).

Reglas de seguridad:
  · SOLO se cambian valores que ya existen en el archivo (nunca se inventan claves).
  · Antes de tocar nada se guarda una copia; «Restaurar» la devuelve tal cual.
  · Cierra el juego antes de aplicar: si está abierto, lo reescribe al salir y se pierde el cambio.
"""
import glob
import os
import re
import shutil
import time
from pathlib import Path

import games
from actions import Action
from util import APP_DIR, DEMO, IS_WIN

BACKUP_DIR = APP_DIR / "copias_juegos"
DEMO_DIR = APP_DIR / "demo_juegos"

PRESETS = {
    "max": ("Máximo FPS", "Todo en bajo para ganar todos los FPS posibles. Se ve más simple."),
    "balanced": ("Equilibrado", "Quita solo lo que más cuesta (sombras, efectos) y deja la imagen bonita."),
}

# Calidad estilo Unreal (0 bajo … 3 épico) — la usan Fortnite y Valorant
_UE_MAX = {"sg.ShadowQuality": 0, "sg.TextureQuality": 1, "sg.EffectsQuality": 0, "sg.PostProcessQuality": 0,
           "sg.ViewDistanceQuality": 1, "sg.AntiAliasingQuality": 0, "sg.FoliageQuality": 0,
           "bUseVSync": False, "FrameRateLimit": 0.0}
_UE_BAL = {"sg.ShadowQuality": 1, "sg.TextureQuality": 2, "sg.EffectsQuality": 1, "sg.PostProcessQuality": 1,
           "sg.ViewDistanceQuality": 2, "sg.AntiAliasingQuality": 1, "sg.FoliageQuality": 1,
           "bUseVSync": False, "FrameRateLimit": 144.0}

GAMES = {
    "fortnite": {
        "name": "Fortnite", "sep": "=",
        "presets": {"max": _UE_MAX, "balanced": _UE_BAL},
        "note": "Cierra Fortnite y el lanzador de Epic antes de aplicar.",
    },
    "valorant": {
        "name": "VALORANT", "sep": "=",
        "presets": {"max": _UE_MAX, "balanced": _UE_BAL},
        "note": "Cierra VALORANT y Riot Client antes de aplicar.",
    },
    "minecraft": {
        "name": "Minecraft (Java)", "sep": ":",
        "presets": {
            "max": {"renderDistance": 8, "graphics": "fast", "fancyGraphics": False, "particles": 2,
                    "entityShadows": False, "enableVsync": False, "maxFps": 260, "ao": False,
                    "biomeBlendRadius": 0, "clouds": "off"},
            "balanced": {"renderDistance": 12, "graphics": "fancy", "fancyGraphics": True, "particles": 1,
                         "entityShadows": True, "enableVsync": False, "maxFps": 144, "ao": True,
                         "biomeBlendRadius": 2, "clouds": "fast"},
        },
        "note": "Cierra Minecraft antes de aplicar. Mods como Sodium suben mucho más los FPS.",
    },
    "cs2": {
        "name": "Counter-Strike 2", "sep": " ", "autoexec": True,
        "presets": {"max": {"fps_max": 0}, "balanced": {"fps_max": 144}},
        "note": "Escribe fps_max en tu autoexec.cfg (CS2 lo carga solo). Los gráficos se bajan dentro del juego.",
    },
}

BEGIN, END = "// HellOP begin", "// HellOP end"


# --------------------------------------------------------------------------
# Localizar los archivos de cada juego
# --------------------------------------------------------------------------
def _demo_files():
    DEMO_DIR.mkdir(parents=True, exist_ok=True)
    samples = {
        "fortnite.ini": "[/Script/FortniteGame.FortGameUserSettings]\nsg.ShadowQuality=3\nsg.TextureQuality=3\nsg.EffectsQuality=3\n"
                        "sg.PostProcessQuality=3\nsg.ViewDistanceQuality=3\nsg.AntiAliasingQuality=3\nsg.FoliageQuality=3\n"
                        "bUseVSync=True\nFrameRateLimit=60.000000\n",
        "minecraft.txt": "version:3465\nrenderDistance:16\ngraphics:\"fancy\"\nparticles:0\nentityShadows:true\n"
                         "enableVsync:true\nmaxFps:120\nao:true\n",
    }
    out = {}
    for fn, text in samples.items():
        p = DEMO_DIR / fn
        if not p.exists():
            p.write_text(text, "utf-8")
        out[fn.split(".")[0]] = p
    return out


def find_files():
    """Devuelve {id_juego: ruta_del_archivo} de los juegos encontrados en este PC."""
    if DEMO:
        return {k: v for k, v in _demo_files().items()}
    if not IS_WIN:
        return {}
    out = {}
    local, roam = os.environ.get("LOCALAPPDATA", ""), os.environ.get("APPDATA", "")
    cands = {
        "fortnite": [Path(local) / "FortniteGame" / "Saved" / "Config" / "WindowsClient" / "GameUserSettings.ini"],
        "minecraft": [Path(roam) / ".minecraft" / "options.txt"],
        "valorant": [Path(p) for p in glob.glob(str(Path(local) / "VALORANT" / "Saved" / "Config" / "*" / "Windows" / "GameUserSettings.ini"))],
    }
    for gid, paths in cands.items():
        for p in paths:
            if p.is_file():
                out[gid] = p
                break
    try:
        for g in games.scan_steam():
            if g["id"] == "steam:730":
                out["cs2"] = Path(g["path"]) / "game" / "csgo" / "cfg" / "autoexec.cfg"
    except Exception:  # noqa: BLE001
        pass
    return out


# --------------------------------------------------------------------------
# Leer / calcular cambios
# --------------------------------------------------------------------------
def _fmt(old, new):
    """Escribe `new` con el mismo estilo que tenía `old` (comillas, mayúsculas, decimales)."""
    o = old.strip()
    q = len(o) >= 2 and o[0] == '"' and o[-1] == '"'
    core = o[1:-1] if q else o
    if isinstance(new, bool):
        if core.lower() in ("true", "false"):
            s = ("True" if new else "False") if core[:1].isupper() else ("true" if new else "false")
        else:
            s = "1" if new else "0"
    elif isinstance(new, float) or (isinstance(new, int) and re.fullmatch(r"-?\d+\.\d+", core)):
        dec = len(core.split(".")[1]) if re.fullmatch(r"-?\d+\.\d+", core) else 0
        s = f"{float(new):.{dec}f}"
    else:
        s = str(new)
    return f'"{s}"' if q else s


def _same(old, new):
    return old.strip().strip('"').lower() == new.strip().strip('"').lower()


def plan(gid, preset):
    """Lista de cambios [(clave, valor_actual, valor_nuevo)] que se harían. Vacío = ya está así / no aplica."""
    path = find_files().get(gid)
    g = GAMES[gid]
    if not path:
        return []
    want = g["presets"][preset]
    changes = []
    if g.get("autoexec"):
        cur = {}
        try:
            text = Path(path).read_text("utf-8", "replace")
            for k in want:
                m = re.search(rf"^\s*{re.escape(k)}\s+(\S+)", text, re.M)
                if m:
                    cur[k] = m.group(1)
        except OSError:
            pass
        for k, v in want.items():
            if cur.get(k) != str(v):
                changes.append((k, cur.get(k, "(sin definir)"), str(v)))
        return changes
    try:
        text = Path(path).read_text("utf-8", "replace")
    except OSError:
        return []
    sep = g["sep"]
    for k, v in want.items():
        m = re.search(rf"^{re.escape(k)}{re.escape(sep)}(.*?)\s*$", text, re.M | re.I)
        if not m:
            continue
        new = _fmt(m.group(1), v)
        if not _same(m.group(1), new):
            changes.append((k, m.group(1).strip(), new))
    return changes


# --------------------------------------------------------------------------
# Acción reversible (aparece en el Historial)
# --------------------------------------------------------------------------
class GameConfigAction(Action):
    group = "gaming"
    reversible = True
    effect = "real"

    def __init__(self, gid, preset):
        self.gid, self.preset = gid, preset
        g = GAMES[gid]
        self.id = f"gameprof:{gid}:{preset}"
        self.title = f"{g['name']}: perfil «{PRESETS[preset][0]}»"
        self.desc = PRESETS[preset][1]

    def apply(self):
        path = find_files().get(self.gid)
        if not path:
            raise RuntimeError("No encuentro la configuración de ese juego")
        path = Path(path)
        g = GAMES[self.gid]
        want = g["presets"][self.preset]
        existed = path.exists()
        BACKUP_DIR.mkdir(parents=True, exist_ok=True)
        backup = BACKUP_DIR / f"{self.gid}_{time.strftime('%Y%m%d_%H%M%S')}.bak"
        text = path.read_text("utf-8", "replace") if existed else ""
        if existed:
            shutil.copy2(path, backup)
        if g.get("autoexec"):
            block = "\n".join([BEGIN] + [f"{k} {v}" for k, v in want.items()] + [END]) + "\n"
            text = re.sub(rf"{re.escape(BEGIN)}.*?{re.escape(END)}\n?", "", text, flags=re.S)
            text = text.rstrip("\n") + ("\n" if text.strip() else "") + block
            path.parent.mkdir(parents=True, exist_ok=True)
        else:
            sep = g["sep"]
            for k, v in want.items():
                def rep(m, v=v):
                    return f"{k}{sep}{_fmt(m.group(1), v)}"
                text = re.sub(rf"^{re.escape(k)}{re.escape(sep)}(.*?)(?=\r?$)", rep, text, flags=re.M | re.I)
        path.write_text(text, "utf-8")
        return {"gid": self.gid, "path": str(path), "backup": str(backup) if existed else "", "existed": existed,
                "_msg": f"Aplicado en {g['name']}. Copia guardada para restaurar."}

    @classmethod
    def undo_data(cls, data):
        path = Path(data["path"])
        if data.get("existed") and data.get("backup") and Path(data["backup"]).exists():
            shutil.copy2(data["backup"], path)
        elif not data.get("existed") and path.exists():
            path.unlink()
