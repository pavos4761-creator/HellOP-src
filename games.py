"""Biblioteca de juegos, perfil por juego y MODO JUEGO AUTOMÁTICO.

· Detecta tus juegos de Steam y Epic (y puedes añadir cualquier .exe a mano).
· Cada juego tiene su perfil: qué optimizaciones se aplican cuando lo abres.
· El vigilante mira cada pocos segundos si alguno de tus juegos está abierto: al abrirse activa el Modo Extremo
  con SU perfil y, al cerrarlo, lo deja todo como estaba.
"""
import json
import os
import re
import threading
import time
from pathlib import Path

import psutil

from util import APP_DIR, DEMO, IS_WIN

GAMES_FILE = APP_DIR / ("juegos_demo.json" if DEMO else "juegos.json")

# (clave, texto, valor por defecto): las mismas del Modo Extremo
OPTIONS = [
    ("timer", "Temporizador de Windows a 0,5 ms", True),
    ("game_prio", "Prioridad ALTA para el juego", True),
    ("bg_prio", "Prioridad baja para lo de fondo", True),
    ("bg_ram", "Liberar la RAM de los programas de fondo", True),
    ("services", "Pausar servicios que despiertan al disco y la CPU (necesita administrador)", True),
    ("dns", "Vaciar la caché DNS", False),
    ("power", "Plan de energía de Alto rendimiento mientras juegas", True),
    ("affinity", "Dejar los núcleos 0 y 1 libres para Windows (CPU de 6 núcleos o más)", False),
]
DEFAULT_PROFILE = {k: d for k, _t, d in OPTIONS}

# ejecutables auxiliares que NO son el juego (se ignoran al detectar)
IGNORE = ("crash", "unins", "redist", "vc_", "vcredist", "dxsetup", "dotnet", "easyanticheat", "beservice", "battleye",
          "eac", "cefprocess", "helper", "webhelper", "report", "updater", "install", "setup", "uninst", "bootstrap")
SKIP_STEAM_IDS = {"228980"}          # Steamworks Common Redistributables


# --------------------------------------------------------------------------
# Almacenamiento
# --------------------------------------------------------------------------
def load():
    try:
        d = json.loads(GAMES_FILE.read_text("utf-8"))
    except Exception:  # noqa: BLE001
        d = {}
    d.setdefault("auto", False)
    d.setdefault("games", [])
    for g in d["games"]:
        g["profile"] = {**DEFAULT_PROFILE, **(g.get("profile") or {})}
    return d


def save(d):
    try:
        APP_DIR.mkdir(parents=True, exist_ok=True)
        GAMES_FILE.write_text(json.dumps(d, indent=1), "utf-8")
    except OSError:
        pass


def summary(profile):
    on = [t for k, t, _d in OPTIONS if profile.get(k)]
    return f"{len(on)} de {len(OPTIONS)} optimizaciones"


# --------------------------------------------------------------------------
# Búsqueda de juegos
# --------------------------------------------------------------------------
def _steam_root():
    if not IS_WIN:
        return None
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Valve\Steam") as k:
            p = winreg.QueryValueEx(k, "SteamPath")[0]
            if p and Path(p).exists():
                return Path(p)
    except OSError:
        pass
    for c in (r"C:\Program Files (x86)\Steam", r"C:\Program Files\Steam"):
        if Path(c).exists():
            return Path(c)
    return None


def scan_steam():
    root = _steam_root()
    if not root:
        return []
    libs = {root}
    vdf = root / "steamapps" / "libraryfolders.vdf"
    try:
        for m in re.finditer(r'"path"\s+"([^"]+)"', vdf.read_text("utf-8", "replace")):
            libs.add(Path(m.group(1).replace("\\\\", "\\")))
    except OSError:
        pass
    out = []
    for lib in libs:
        apps = lib / "steamapps"
        try:
            manifests = list(apps.glob("appmanifest_*.acf"))
        except OSError:
            continue
        for mf in manifests:
            try:
                t = mf.read_text("utf-8", "replace")
                appid = re.search(r'"appid"\s+"(\d+)"', t).group(1)
                name = re.search(r'"name"\s+"([^"]+)"', t).group(1)
                inst = re.search(r'"installdir"\s+"([^"]+)"', t).group(1)
            except (OSError, AttributeError):
                continue
            folder = apps / "common" / inst
            if appid in SKIP_STEAM_IDS or not folder.exists() or re.search(r"proton|steam linux runtime|steamworks", name, re.I):
                continue
            out.append({"id": f"steam:{appid}", "name": name, "source": "Steam", "path": str(folder),
                        "launch": f"steam://rungameid/{appid}"})
    return out


def scan_epic():
    base = Path(os.environ.get("PROGRAMDATA", r"C:\ProgramData")) / "Epic" / "EpicGamesLauncher" / "Data" / "Manifests"
    out = []
    try:
        items = list(base.glob("*.item"))
    except OSError:
        return []
    for it in items:
        try:
            d = json.loads(it.read_text("utf-8", "replace"))
            name, loc, app = d["DisplayName"], d["InstallLocation"], d["AppName"]
        except (OSError, ValueError, KeyError):
            continue
        if loc and Path(loc).exists():
            out.append({"id": f"epic:{app}", "name": name, "source": "Epic", "path": loc,
                        "launch": f"com.epicgames.launcher://apps/{app}?action=launch&silent=true"})
    return out


def _demo_found():
    return [{"id": "steam:730", "name": "Counter-Strike 2", "source": "Steam", "path": r"C:\Steam\steamapps\common\CS2", "launch": ""},
            {"id": "steam:1091500", "name": "Cyberpunk 2077", "source": "Steam", "path": r"C:\Steam\steamapps\common\Cyberpunk", "launch": ""},
            {"id": "epic:Fortnite", "name": "Fortnite", "source": "Epic", "path": r"C:\Epic\Fortnite", "launch": ""},
            {"id": "epic:Sugar", "name": "Valorant", "source": "Riot", "path": r"C:\Riot Games\VALORANT", "launch": ""}]


def scan_all():
    """Busca juegos y los junta con tu biblioteca (conserva los perfiles que ya hubieras editado). Devuelve cuántos son nuevos."""
    d = load()
    have = {g["id"] for g in d["games"]}
    found = _demo_found() if DEMO else scan_steam() + scan_epic()
    new = 0
    for g in found:
        if g["id"] not in have:
            g["profile"] = dict(DEFAULT_PROFILE)
            d["games"].append(g)
            have.add(g["id"])
            new += 1
    d["games"].sort(key=lambda g: g["name"].lower())
    save(d)
    return new


def add_manual(exe_path):
    exe = Path(exe_path)
    d = load()
    gid = "exe:" + str(exe).lower()
    if any(g["id"] == gid for g in d["games"]):
        return False
    d["games"].append({"id": gid, "name": exe.stem, "source": "Manual", "path": "", "exe": str(exe), "launch": str(exe),
                       "profile": dict(DEFAULT_PROFILE)})
    d["games"].sort(key=lambda g: g["name"].lower())
    save(d)
    return True


def remove(gid):
    d = load()
    d["games"] = [g for g in d["games"] if g["id"] != gid]
    save(d)


def set_profile(gid, profile, everyone=False):
    d = load()
    for g in d["games"]:
        if everyone or g["id"] == gid:
            g["profile"] = dict(profile)
    save(d)


def set_auto(on):
    d = load()
    d["auto"] = bool(on)
    save(d)


# --------------------------------------------------------------------------
# Detección de juegos en marcha
# --------------------------------------------------------------------------
def _norm_dir(p):
    return (p or "").lower().replace("/", "\\").rstrip("\\") + "\\"


def find_running(games):
    """(juego, nombre_del_exe_principal) del primer juego de tu biblioteca que esté abierto, o None."""
    if not games:
        return None
    rules = []
    for g in games:
        if g.get("exe"):
            rules.append((g, None, g["exe"].lower().replace("/", "\\")))
        elif g.get("path"):
            rules.append((g, _norm_dir(g["path"]), None))
    best = None
    for p in psutil.process_iter(["pid", "name", "exe", "memory_info"]):
        try:
            exe = (p.info["exe"] or "").lower().replace("/", "\\")
            name = p.info["name"] or ""
            if not exe or any(w in name.lower() for w in IGNORE):
                continue
            for g, folder, only in rules:
                if (only and exe == only) or (folder and exe.startswith(folder)):
                    rss = p.info["memory_info"].rss if p.info["memory_info"] else 0
                    if not best or rss > best[2]:
                        best = (g, name, rss)
        except (psutil.NoSuchProcess, psutil.AccessDenied, AttributeError, TypeError):
            continue
    return (best[0], best[1]) if best else None


# --------------------------------------------------------------------------
# Vigilante (modo juego automático)
# --------------------------------------------------------------------------
class Watcher:
    POLL = 3.0

    def __init__(self, booster, log=lambda m: None, on_change=lambda: None):
        self.b = booster
        self.log = log
        self.on_change = on_change
        self.running = False
        self.current = None          # juego que tenemos optimizado
        self.since = None
        self._thread = None
        self._hits = self._miss = 0
        self._t0 = 0.0

    def start(self):
        if self.running:
            return
        self.running = True
        self._t0 = time.time()
        self._hits = self._miss = 0
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()
        self.log("👁  Modo automático ACTIVO: vigilo tus juegos.")
        self.on_change()

    def stop(self):
        if not self.running:
            return
        self.running = False
        if self.current:
            self._release()
        self.log("Modo automático desactivado.")
        self.on_change()

    # ------------------------------------------------------------------
    def _detect(self):
        d = load()
        if DEMO:      # simulación: el primer juego «se abre» a los 5 s y «se cierra» a los 24 s
            t = time.time() - self._t0
            return (d["games"][0], "cs2.exe") if d["games"] and 5 < t < 24 else None
        return find_running(d["games"])

    def _loop(self):
        while self.running:
            try:
                found = self._detect()
                if found and not self.current:
                    self._hits += 1
                    self._miss = 0
                    if self._hits >= 2:                       # visto dos veces seguidas = ya está abierto
                        self._engage(*found)
                elif not found and self.current:
                    self._miss += 1
                    self._hits = 0
                    if self._miss >= 3:                       # cerrado de verdad (no un parpadeo del launcher)
                        self._release()
                else:
                    self._hits = self._miss = 0
            except Exception as e:  # noqa: BLE001
                self.log(f"⚠ Vigilante: {type(e).__name__}: {e}")
            for _ in range(int(self.POLL * 5)):
                if not self.running:
                    return
                time.sleep(0.2)

    def _engage(self, game, proc_name):
        if self.b.active:
            return                                           # ya hay un Modo Extremo manual en marcha
        self.log(f"🎮  Detectado «{game['name']}»: activo su perfil.")
        self.current, self.since = game, time.time()
        try:
            self.b.start(proc_name, game["profile"], self.log)
        except Exception as e:  # noqa: BLE001
            self.log(f"✗ No pude activar el modo: {e}")
            self.current = None
        self.on_change()

    def _release(self):
        game = self.current
        self.current = None
        self.log(f"🏁  «{game['name']}» se cerró: lo dejo todo como estaba.")
        try:
            self.b.stop(self.log)
        except Exception as e:  # noqa: BLE001
            self.log(f"✗ Error al restaurar: {e}")
        self.on_change()

    def status(self):
        if not self.running:
            return "Desactivado", None
        if self.current:
            return f"Jugando a «{self.current['name']}» · Modo Extremo activo", int(time.time() - (self.since or time.time()))
        return "Vigilando tus juegos…", None
