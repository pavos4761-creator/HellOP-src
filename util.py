"""Utilidades comunes: PowerShell, permisos de administrador, formatos y rutas."""
import base64
import ctypes
import json
import os
import subprocess
import sys
import time
from pathlib import Path

IS_WIN = sys.platform == "win32"
DEMO = "--demo" in sys.argv          # modo demo: no toca nada, datos de ejemplo

APP_NAME = "HellOP"
_BASE = Path(os.environ.get("APPDATA") or Path.home())
APP_DIR = _BASE / "HellOP"
_OLD = _BASE / "PCOptimizer"
try:                                   # conserva el historial de la versión anterior
    if _OLD.exists() and not APP_DIR.exists():
        _OLD.rename(APP_DIR)
except OSError:
    pass
try:
    APP_DIR.mkdir(parents=True, exist_ok=True)
except OSError:
    APP_DIR = Path.home()

_NO_WINDOW = 0x08000000 if IS_WIN else 0


# --------------------------------------------------------------------------
# Ejecución de comandos
# --------------------------------------------------------------------------
def run_ps(script, timeout=90):
    """Ejecuta un script de PowerShell. Devuelve (código, stdout, stderr)."""
    if not IS_WIN:
        return 1, "", "PowerShell solo está disponible en Windows"
    full = ("[Console]::OutputEncoding=[System.Text.Encoding]::UTF8; "
            "$ProgressPreference='SilentlyContinue'; " + script)
    encoded = base64.b64encode(full.encode("utf-16-le")).decode("ascii")
    try:
        p = subprocess.run(
            ["powershell.exe", "-NoProfile", "-NonInteractive",
             "-ExecutionPolicy", "Bypass", "-EncodedCommand", encoded],
            capture_output=True, timeout=timeout, creationflags=_NO_WINDOW)
        return (p.returncode, p.stdout.decode("utf-8", "replace").strip(),
                p.stderr.decode("utf-8", "replace").strip())
    except subprocess.TimeoutExpired:
        return 124, "", "Tiempo de espera agotado"
    except Exception as e:  # noqa: BLE001
        return 1, "", str(e)


def run_ps_json(script, timeout=90, default=None):
    """Ejecuta PowerShell y devuelve el JSON que imprime (o `default`)."""
    rc, out, _ = run_ps(script, timeout)
    if not out:
        return default
    try:
        return json.loads(out)
    except ValueError:
        for line in reversed(out.splitlines()):
            line = line.strip()
            if line[:1] in "[{":
                try:
                    return json.loads(line)
                except ValueError:
                    break
    return default


def run_cmd(args, timeout=60):
    """Ejecuta un programa sin ventana. Devuelve (código, stdout, stderr)."""
    try:
        p = subprocess.run(args, capture_output=True, timeout=timeout,
                           creationflags=_NO_WINDOW)
        dec = lambda b: b.decode("cp850" if IS_WIN else "utf-8", "replace").strip()  # noqa: E731
        return p.returncode, dec(p.stdout), dec(p.stderr)
    except subprocess.TimeoutExpired:
        return 124, "", "Tiempo de espera agotado"
    except Exception as e:  # noqa: BLE001
        return 1, "", str(e)


def ps_quote(s):
    """Escapa texto para meterlo entre comillas simples de PowerShell."""
    return "'" + str(s).replace("'", "''") + "'"


def as_list(x):
    if x is None:
        return []
    return x if isinstance(x, list) else [x]


# --------------------------------------------------------------------------
# Administrador
# --------------------------------------------------------------------------
def is_admin():
    if DEMO:
        return True
    if not IS_WIN:
        return False
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:  # noqa: BLE001
        return False


def relaunch_as_admin():
    """Vuelve a lanzar la app pidiendo permisos de administrador (UAC)."""
    if not IS_WIN:
        return False
    if getattr(sys, "frozen", False):
        params = " ".join(f'"{a}"' for a in sys.argv[1:])
    else:
        params = " ".join(f'"{a}"' for a in sys.argv)
    try:
        rc = ctypes.windll.shell32.ShellExecuteW(None, "runas", sys.executable, params, None, 1)
        return rc > 32
    except Exception:  # noqa: BLE001
        return False


# --------------------------------------------------------------------------
# Formatos
# --------------------------------------------------------------------------
def fmt_bytes(n):
    n = float(n or 0)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if n < 1024 or unit == "TB":
            return f"{n:.0f} {unit}" if unit == "B" else f"{n:.1f} {unit}"
        n /= 1024


def fmt_gb(n):
    n = float(n or 0) / (1024 ** 3)
    return f"{n:.0f} GB" if n >= 10 or abs(n - round(n)) < 0.05 else f"{n:.1f} GB"


def days_since(date_str):
    """Días desde una fecha 'YYYY-MM-DD' (o None)."""
    if not date_str:
        return None
    try:
        y, m, d = (int(p) for p in date_str[:10].split("-"))
        return (time.time() - time.mktime((y, m, d, 0, 0, 0, 0, 0, -1))) / 86400
    except (ValueError, OverflowError):
        return None


def age_text(days):
    if days is None:
        return "fecha desconocida"
    if days < 60:
        return f"hace {int(days)} días"
    if days < 700:
        return f"hace {int(days // 30)} meses"
    return f"hace {days / 365:.1f} años"


def nvsmi():
    """Ruta de nvidia-smi (está en el PATH o en la carpeta del driver) o None."""
    import shutil
    p = shutil.which("nvidia-smi")
    if p:
        return p
    for c in (r"C:\Windows\System32\nvidia-smi.exe", r"C:\Program Files\NVIDIA Corporation\NVSMI\nvidia-smi.exe"):
        if os.path.exists(c):
            return c
    return None
