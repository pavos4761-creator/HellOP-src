"""Actualizaciones automáticas desde GitHub Releases.

Flujo:  comprobar() → ¿hay una versión más nueva?  →  actualizar() descarga, VERIFICA el SHA256 y se reemplaza.
  · Si la app es un .exe (PyInstaller): descarga HellOP.exe y un script lo cambia cuando la app se cierra.
  · Si se ejecuta como código Python: descarga HellOP-src.zip y sustituye los .py (guarda copia de seguridad).
Solo se descargan archivos de github.com / githubusercontent.com y SIEMPRE se comprueba su hash.
"""
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
import zipfile
from pathlib import Path

import version
from util import APP_DIR, DEMO, IS_WIN

API_BASE = os.environ.get("PCOPT_API_BASE", "https://api.github.com")   # solo se cambia en las pruebas
CONFIG = APP_DIR / "update_config.json"
# Se publican con los dos nombres: HellOP (nuevo) y PCOptimizer (para que la versión 1.0.0 pueda actualizarse).
EXE_ASSETS = ("HellOP.exe", "PCOptimizer.exe")
SRC_ASSETS = ("HellOP-src.zip", "PCOptimizer-src.zip")
FROZEN = bool(getattr(sys, "frozen", False))
SRC_DIR = Path(__file__).resolve().parent
REPO_RE = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")


class UpdateError(Exception):
    pass


# --------------------------------------------------------------------------
# Configuración
# --------------------------------------------------------------------------
def get_repo():
    try:
        r = json.loads(CONFIG.read_text("utf-8")).get("repo", "")
        if r:
            return r
    except Exception:  # noqa: BLE001
        pass
    return version.UPDATE_REPO


def set_repo(repo):
    repo = (repo or "").strip().strip("/")
    repo = re.sub(r"^https?://github\.com/", "", repo)
    if repo and not REPO_RE.match(repo):
        raise UpdateError("Escribe el repositorio como  usuario/nombre  (por ejemplo: mi-usuario/pc-optimizer)")
    CONFIG.write_text(json.dumps({"repo": repo}), "utf-8")
    return repo


def parse_version(s):
    nums = [int(x) for x in re.findall(r"\d+", s or "")[:3]]
    return tuple(nums + [0] * (3 - len(nums)))


def mode():
    return "exe" if FROZEN else "código Python"


# --------------------------------------------------------------------------
# Red
# --------------------------------------------------------------------------
def _allowed(url):
    host = urllib.parse.urlparse(url).hostname or ""
    if API_BASE != "https://api.github.com" and host == (urllib.parse.urlparse(API_BASE).hostname or ""):
        return True                   # solo en pruebas locales
    return urllib.parse.urlparse(url).scheme == "https" and (
        host in ("github.com", "api.github.com") or host.endswith(".githubusercontent.com"))


def _open(url, timeout=20):
    if not _allowed(url):
        raise UpdateError("Dirección de descarga no permitida: " + url)
    req = urllib.request.Request(url, headers={"User-Agent": "HellOP-Updater", "Accept": "application/vnd.github+json"})
    return urllib.request.urlopen(req, timeout=timeout)


def _json(url):
    try:
        with _open(url) as r:
            return json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        if e.code == 404:
            raise UpdateError("No encuentro versiones publicadas en ese repositorio (¿existe, es público y tiene una «Release»?).")
        if e.code == 403:
            raise UpdateError("GitHub limitó las consultas por un rato. Inténtalo dentro de unos minutos.")
        raise UpdateError(f"GitHub respondió con el error {e.code}.")
    except (urllib.error.URLError, OSError, TimeoutError):
        raise UpdateError("No pude conectar con GitHub. Comprueba tu conexión a Internet.")


# --------------------------------------------------------------------------
# Comprobar
# --------------------------------------------------------------------------
def check():
    """Devuelve dict: current, latest, newer, notes, assets{nombre:url}, page."""
    if DEMO:
        time.sleep(0.8)
        return {"current": version.__version__, "latest": "9.9.9", "newer": True, "page": "",
                "notes": "• Novedad de ejemplo 1\n• Novedad de ejemplo 2\n(esto es el modo demo: no descarga nada)",
                "assets": {}, "published": "2026-10-21"}
    repo = get_repo()
    if not repo:
        raise UpdateError("Aún no has indicado el repositorio de GitHub. Escríbelo abajo en «Dónde se publican las versiones».")
    data = _json(f"{API_BASE}/repos/{repo}/releases/latest")
    tag = data.get("tag_name") or ""
    latest = ".".join(str(x) for x in parse_version(tag))
    assets = {a["name"]: a["browser_download_url"] for a in data.get("assets", []) if a.get("browser_download_url")}
    return {"current": version.__version__, "latest": latest, "tag": tag, "page": data.get("html_url", ""),
            "newer": parse_version(tag) > parse_version(version.__version__),
            "notes": (data.get("body") or "").strip() or "(Sin notas de versión)", "assets": assets,
            "published": (data.get("published_at") or "")[:10]}


# --------------------------------------------------------------------------
# Descargar y verificar
# --------------------------------------------------------------------------
def _sha256_of(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _download(url, dest, progress=lambda pct, msg: None, label="Descargando"):
    with _open(url, timeout=30) as r:
        total = int(r.headers.get("Content-Length") or 0)
        got = 0
        with open(dest, "wb") as f:
            while True:
                chunk = r.read(256 * 1024)
                if not chunk:
                    break
                f.write(chunk)
                got += len(chunk)
                if total:
                    progress(int(got * 100 / total), f"{label}… {got / 1048576:.1f} / {total / 1048576:.1f} MB")
    return got


def _expected_hash(info, asset):
    url = info["assets"].get(asset + ".sha256")
    if not url:
        raise UpdateError(f"La versión publicada no incluye el archivo de verificación «{asset}.sha256». "
                          "Por seguridad no instalo nada sin comprobar su hash.")
    with _open(url) as r:
        txt = r.read().decode("utf-8", "replace")
    m = re.search(r"\b([0-9a-fA-F]{64})\b", txt)
    if not m:
        raise UpdateError("El archivo de verificación está mal formado.")
    return m.group(1).lower()


def _fetch_verified(info, names, dest, progress):
    asset = next((n for n in names if n in info["assets"]), names[0])
    url = info["assets"].get(asset)
    if not url:
        raise UpdateError(f"La versión {info['latest']} no incluye el archivo «{asset}».")
    want = _expected_hash(info, asset)
    _download(url, dest, progress, f"Descargando {asset}")
    progress(100, "Verificando que el archivo no está corrupto…")
    if _sha256_of(dest) != want:
        try:
            os.remove(dest)
        except OSError:
            pass
        raise UpdateError("El archivo descargado NO coincide con su hash de verificación. No se ha instalado nada.")


# --------------------------------------------------------------------------
# Aplicar
# --------------------------------------------------------------------------
def actualizar(info, progress=lambda pct, msg: None):
    """Descarga e instala. Devuelve 'restart' si la app debe cerrarse para terminar de actualizarse."""
    if DEMO:
        for i in range(0, 101, 20):
            progress(i, "Descargando (demo)…")
            time.sleep(0.25)
        return "demo"
    if not info.get("newer"):
        raise UpdateError("Ya tienes la última versión.")
    return _apply_exe(info, progress) if FROZEN else _apply_source(info, progress)


def clean_env():
    """Entorno para lanzar la app de nuevo desde el .exe: sin las variables internas de PyInstaller.
    Si las hereda, el .exe nuevo cree que sigue siendo «hijo» del anterior (ya cerrado) y muestra
    «Security validation failure: invalid originating onefile parent process»."""
    env = {k: v for k, v in os.environ.items() if not k.startswith("_PYI") and k != "_MEIPASS2"}
    env["PYINSTALLER_RESET_ENVIRONMENT"] = "1"
    return env


def _apply_exe(info, progress):
    exe = Path(sys.executable).resolve()
    if re.search(r"[%!^&]", str(exe)):
        raise UpdateError("La ruta del programa tiene caracteres especiales (% ! ^ &). Muévelo a una carpeta sencilla y vuelve a intentarlo.")
    new = exe.with_name(exe.name + ".new")
    try:
        _fetch_verified(info, EXE_ASSETS, str(new), progress)
    except PermissionError:
        raise UpdateError("No tengo permiso para escribir en la carpeta del programa. Muévelo a una carpeta tuya (Escritorio o Documentos).")
    bat = Path(tempfile.gettempdir()) / "hellop_update.bat"
    bat.write_text(
        "@echo off\r\n"
        f'set "OLD={exe}"\r\nset "NEW={new}"\r\n'
        'copy /y "%OLD%" "%OLD%.bak" >nul 2>&1\r\n'
        "for /l %%i in (1,1,90) do (\r\n"
        '  move /y "%NEW%" "%OLD%" >nul 2>&1 && goto ok\r\n'
        "  timeout /t 1 /nobreak >nul\r\n"
        ")\r\n"
        "exit /b 1\r\n"
        ":ok\r\n"
        'set "PYINSTALLER_RESET_ENVIRONMENT=1"\r\n'
        'set "_PYI_APPLICATION_HOME_DIR="\r\nset "_PYI_ARCHIVE_FILE="\r\nset "_PYI_PARENT_PROCESS_LEVEL="\r\nset "_MEIPASS2="\r\n'
        'start "" "%OLD%"\r\n'
        '(goto) 2>nul & del "%~f0"\r\n', "utf-8")
    if IS_WIN:
        subprocess.Popen(["cmd", "/c", str(bat)], creationflags=0x00000008 | 0x00000200 | 0x08000000, close_fds=True,
                         env=clean_env())
    return "restart"


def _apply_source(info, progress):
    tmp = Path(tempfile.mkdtemp(prefix="pcopt_upd_"))
    z = tmp / "paquete.zip"
    _fetch_verified(info, SRC_ASSETS, str(z), progress)
    out = tmp / "new"
    with zipfile.ZipFile(z) as zf:
        for n in zf.namelist():                       # protección contra rutas peligrosas dentro del zip
            p = (out / n).resolve()
            if not str(p).startswith(str(out.resolve())) or n.startswith(("/", "\\")):
                raise UpdateError("El paquete contiene rutas no válidas. No se instala.")
        zf.extractall(out)
    root = next((p.parent for p in out.rglob("main.py")), None)
    if not root or not (root / "version.py").exists():
        raise UpdateError("El paquete descargado no parece una versión válida de la app.")
    backup = APP_DIR / f"copia_{version.__version__}"
    backup.mkdir(parents=True, exist_ok=True)
    for f in SRC_DIR.glob("*.py"):
        shutil.copy2(f, backup / f.name)
    n = 0
    for f in root.glob("*.py"):
        shutil.copy2(f, SRC_DIR / f.name)
        n += 1
    req = root / "requirements.txt"
    if req.exists():
        shutil.copy2(req, SRC_DIR / "requirements.txt")
        subprocess.run([sys.executable, "-m", "pip", "install", "-q", "-r", str(req)], capture_output=True,
                       creationflags=0x08000000 if IS_WIN else 0)
    shutil.rmtree(tmp, ignore_errors=True)
    progress(100, f"{n} archivos actualizados")
    return "restart"


def restart_app():
    """Cierra esta instancia y abre la nueva (modo código Python). En modo exe lo hace el script."""
    if FROZEN:
        return
    subprocess.Popen([sys.executable] + sys.argv, close_fds=True)
