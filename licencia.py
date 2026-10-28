"""Licencia de HellOP: claves FIRMADAS con caducidad (y, si quieres, atadas a un PC).

· Sin clave (o caducada) HellOP funciona en modo GRATIS: las páginas de PRO_PAGES salen bloqueadas.
· La clave la firmas TÚ con tu llave privada (archivo hellop_privada.key en %APPDATA%\\HellOP). HellOP solo trae la parte
  PÚBLICA, que sirve para comprobar que la clave es auténtica pero no para fabricar otras.
· Con tu llave privada puesta, HellOP se abre completo y aparece el generador de claves.
"""
import base64
import hashlib
import json
import re
import time
import uuid
from datetime import date, timedelta

import ed25519
from util import APP_DIR, DEMO, IS_WIN

PUBLIC_KEY = bytes.fromhex("a4d7673bed9a8a8f525a159820e87bf28f77fa06ef10da11ddfcd1d4277263e1")
PRIVATE_FILE = APP_DIR / "hellop_privada.key"
STATE_FILE = APP_DIR / "licencia.json"
CLOCK_FILE = APP_DIR / "reloj.json"
REVOKED_FILE = APP_DIR / "revocadas_cache.json"       # copia local de la lista de claves anuladas
REVOKED_URL = "https://raw.githubusercontent.com/{repo}/main/revocadas.json"
EPOCH = date(2024, 1, 1)
VERSION = 1

# Páginas GRATIS: todo lo demás necesita clave. (Cámbialo aquí cuando quieras mover algo entre GRATIS y PRO)
FREE_PAGES = {"home", "analysis", "clean", "monitor", "history", "update", "license"}
PRO_PAGES = {"optimize", "games", "booster", "diag", "fps", "gameprof", "tweaks", "bios", "oc", "health", "debloat", "score", "arranque", "shaders", "cuello"}


# --------------------------------------------------------------------------
# ID del PC
# --------------------------------------------------------------------------
def _machine_guid():
    if IS_WIN:
        try:
            import winreg
            with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Cryptography", 0,
                                winreg.KEY_READ | winreg.KEY_WOW64_64KEY) as k:
                return str(winreg.QueryValueEx(k, "MachineGuid")[0])
        except OSError:
            pass
    return f"mac-{uuid.getnode():012x}"


def _pc_hash(guid):
    return hashlib.sha256(("hellop:" + guid.lower()).encode()).digest()[:8]


def pc_id():
    """ID corto del PC (se lo mandas al creador para que te haga una clave atada a tu PC)."""
    h = _pc_hash(_machine_guid() if not DEMO else "demo-pc").hex().upper()
    return "-".join(h[i:i + 4] for i in range(0, 16, 4))


def _parse_pc_id(text):
    t = re.sub(r"[^0-9A-Fa-f]", "", text or "")
    if not t:
        return b"\x00" * 8
    if len(t) != 16:
        raise ValueError("El ID de PC debe tener 16 letras/números (formato XXXX-XXXX-XXXX-XXXX)")
    return bytes.fromhex(t)


# --------------------------------------------------------------------------
# Claves
# --------------------------------------------------------------------------
def _encode(payload, sig):
    raw = base64.b32encode(payload + sig).decode().rstrip("=")
    return "HELLOP-" + "-".join(raw[i:i + 5] for i in range(0, len(raw), 5))


def _decode(key):
    parts = [p for p in re.split(r"[-\s]+", (key or "").strip().upper()) if p]
    if parts and parts[0] == "HELLOP":
        parts = parts[1:]
    raw = "".join(parts)
    try:
        data = base64.b32decode(raw + "=" * (-len(raw) % 8))
    except Exception:  # noqa: BLE001
        return None
    return (data[:-64], data[-64:]) if len(data) > 64 else None


def make_key(secret, pc_text, days):
    """Genera una clave que caduca dentro de `days` días. pc_text vacío = vale en cualquier PC."""
    exp = (date.today() + timedelta(days=int(days)) - EPOCH).days
    payload = bytes([VERSION]) + _parse_pc_id(pc_text) + exp.to_bytes(2, "big") + b"\x00"
    return _encode(payload, ed25519.sign(secret, payload)), date.today() + timedelta(days=int(days))


def key_id(key):
    """Identificador corto y público de una clave (no sirve para reconstruirla). None si no tiene formato válido."""
    d = _decode(key)
    return hashlib.sha256(d[0] + d[1]).hexdigest()[:20] if d else None


def revoked_ids():
    """Claves anuladas según la última copia descargada (no usa la red)."""
    try:
        ids = json.loads(REVOKED_FILE.read_text("utf-8")).get("ids", [])
        return {str(i) for i in ids if isinstance(i, str)}
    except Exception:  # noqa: BLE001
        return set()


def refresh_revoked(timeout=6):
    """Descarga la lista de claves anuladas y guarda una copia. Devuelve el conjunto, o None si no hubo red.
    Un 404 (aún no existe la lista) cuenta como lista vacía."""
    import urllib.error
    import urllib.request
    try:
        import version
        repo = version.UPDATE_REPO or "pavos4761-creator/PCOptimizer"
    except Exception:  # noqa: BLE001
        repo = "pavos4761-creator/PCOptimizer"
    url = REVOKED_URL.format(repo=repo) + f"?t={int(time.time())}"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "HellOP-Licencia"})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            raw = r.read(200_000).decode("utf-8", "replace")
        data = json.loads(raw)
        ids = {i for i in data.get("ids", []) if isinstance(i, str) and re.fullmatch(r"[0-9a-f]{20}", i)} if isinstance(data, dict) else set()
    except urllib.error.HTTPError as e:
        if e.code != 404:
            return None
        ids = set()
    except Exception:  # noqa: BLE001
        return None
    try:
        APP_DIR.mkdir(parents=True, exist_ok=True)
        REVOKED_FILE.write_text(json.dumps({"ids": sorted(ids), "ts": int(time.time())}), "utf-8")
    except OSError:
        pass
    return ids


def inspect(key):
    """Comprueba una clave. Devuelve dict: ok, motivo, caduca (date), pc (bytes)."""
    d = _decode(key)
    if not d or len(d[0]) != 12:
        return {"ok": False, "why": "La clave no tiene un formato válido. Cópiala entera, tal como te la dieron."}
    payload, sig = d
    if not ed25519.verify(PUBLIC_KEY, payload, sig):
        return {"ok": False, "why": "La clave no es auténtica (o está incompleta)."}
    if payload[0] != VERSION:
        return {"ok": False, "why": "Esta clave es de otra versión. Actualiza HellOP."}
    return {"ok": True, "pc": payload[1:9], "exp": EPOCH + timedelta(days=int.from_bytes(payload[9:11], "big"))}


# --------------------------------------------------------------------------
# Estado
# --------------------------------------------------------------------------
def owner_secret():
    """La llave privada si está puesta y es la verdadera; si no, None."""
    try:
        sec = bytes.fromhex(PRIVATE_FILE.read_text().strip())
        return sec if ed25519.public_key(sec) == PUBLIC_KEY else None
    except Exception:  # noqa: BLE001
        return None


def _clock_ok():
    """False si la fecha del PC está claramente atrasada respecto a la última vez que se usó (truco para alargar claves)."""
    today = date.today()
    try:
        last = date.fromisoformat(json.loads(CLOCK_FILE.read_text()).get("max", ""))
    except Exception:  # noqa: BLE001
        last = None
    if last and today < last - timedelta(days=1):
        return False
    try:
        CLOCK_FILE.write_text(json.dumps({"max": str(max(today, last) if last else today)}))
    except OSError:
        pass
    return True


def saved_key():
    try:
        return json.loads(STATE_FILE.read_text("utf-8")).get("key", "")
    except Exception:  # noqa: BLE001
        return ""


def status():
    """{'level': 'owner'|'pro'|'free'|'expired'|'invalid', 'msg': ..., 'exp': date|None, 'days': int|None}"""
    if DEMO:
        return {"level": "owner", "msg": "Modo demo", "exp": None, "days": None}
    if owner_secret():
        return {"level": "owner", "msg": "Modo creador (tu llave privada está puesta)", "exp": None, "days": None}
    key = saved_key()
    if not key:
        return {"level": "free", "msg": "Sin clave: versión GRATIS.", "exp": None, "days": None}
    info = inspect(key)
    if not info["ok"]:
        return {"level": "invalid", "msg": info["why"], "exp": None, "days": None}
    zero = b"\x00" * 8
    if info["pc"] != zero and info["pc"] != _pc_hash(_machine_guid()):
        return {"level": "invalid", "msg": "Esta clave es de otro PC. Pide una para el ID de este equipo.", "exp": None, "days": None}
    if key_id(key) in revoked_ids():
        return {"level": "invalid", "msg": "Esta clave fue anulada por quien te la dio. Pídele una nueva.", "exp": None, "days": None}
    if not _clock_ok():
        return {"level": "invalid", "msg": "La fecha del PC es anterior a la última vez que usaste HellOP. Corrígela.", "exp": None, "days": None}
    left = (info["exp"] - date.today()).days
    if left < 0:
        return {"level": "expired", "msg": f"Tu clave caducó el {info['exp'].strftime('%d/%m/%Y')}.", "exp": info["exp"], "days": left}
    return {"level": "pro", "msg": f"PRO activo hasta el {info['exp'].strftime('%d/%m/%Y')} ({left} días).", "exp": info["exp"], "days": left}


def activate(key):
    """Guarda la clave si es válida para este PC. Devuelve (ok, mensaje)."""
    info = inspect(key)
    if not info["ok"]:
        return False, info["why"]
    if info["pc"] != b"\x00" * 8 and info["pc"] != _pc_hash(_machine_guid()):
        return False, "Esta clave es de otro PC. Pide una para el ID de este equipo."
    if key_id(key) in revoked_ids():
        return False, "Esa clave fue anulada. Pide una nueva a quien te la dio."
    if info["exp"] < date.today():
        return False, f"Esa clave caducó el {info['exp'].strftime('%d/%m/%Y')}."
    STATE_FILE.write_text(json.dumps({"key": key.strip(), "ts": int(time.time())}), "utf-8")
    return True, f"Clave activada. PRO hasta el {info['exp'].strftime('%d/%m/%Y')}."


def is_pro():
    return status()["level"] in ("owner", "pro")


def locked(page_key):
    return page_key not in FREE_PAGES and page_key != "locked" and not is_pro()
