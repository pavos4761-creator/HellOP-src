"""Registro de claves (solo para el creador): a quién das cada clave, cuándo caduca y, si hace falta, anularla.

· La lista vive en tu PC (claves_creadas.json en %APPDATA%\\HellOP).
· ANULAR una clave la añade a «revocadas.json» en el repositorio PÚBLICO. Ese archivo solo contiene identificadores cortos
  (no sirven para fabricar claves). Cada HellOP lo descarga al abrirse y cada pocas horas; si su clave está en la lista, se bloquea.
· Para escribir en el repositorio hace falta un token de GitHub con permiso de «Contents: Read and write» sobre el repo público.
  Se guarda solo en tu PC (creador_token.txt) y solo se usa para publicar esa lista.

Límite honesto: la anulación funciona cuando el PC de la otra persona tiene internet. Alguien que bloquee a propósito el acceso
a GitHub podría seguir usando la clave hasta que caduque.
"""
import base64
import json
import re
import time
import urllib.error
import urllib.request
from datetime import date

import licencia
from util import APP_DIR

FILE = APP_DIR / "claves_creadas.json"
TOKEN_FILE = APP_DIR / "creador_token.txt"
API = "https://api.github.com"
PRONTO = 7          # días: a partir de aquí se avisa de que una clave está a punto de caducar


class ClavesError(Exception):
    pass


# --------------------------------------------------------------------------
# Lista local
# --------------------------------------------------------------------------
def load():
    try:
        data = json.loads(FILE.read_text("utf-8"))
        return [e for e in data if isinstance(e, dict) and e.get("id")]
    except Exception:  # noqa: BLE001
        return []


def _save(items):
    APP_DIR.mkdir(parents=True, exist_ok=True)
    FILE.write_text(json.dumps(items, ensure_ascii=False, indent=1), "utf-8")


def add(nombre, key, exp, pc=""):
    """Apunta una clave recién generada. Devuelve la entrada."""
    kid = licencia.key_id(key)
    if not kid:
        raise ClavesError("La clave no tiene un formato válido.")
    items = [e for e in load() if e["id"] != kid]
    e = {"id": kid, "nombre": (nombre or "").strip()[:60] or "Sin nombre", "key": key, "pc": (pc or "").strip()[:30],
         "creada": date.today().isoformat(), "caduca": exp.isoformat(), "anulada": False, "publicada": False}
    items.append(e)
    _save(items)
    return e


def estado(e, hoy=None):
    """('anulada'|'pendiente'|'caducada'|'pronto'|'activa', días que quedan)."""
    hoy = hoy or date.today()
    dias = (date.fromisoformat(e["caduca"]) - hoy).days
    if e.get("anulada"):
        return ("anulada" if e.get("publicada") else "pendiente"), dias
    if dias < 0:
        return "caducada", dias
    return ("pronto" if dias <= PRONTO else "activa"), dias


def por_vencer():
    return [e for e in load() if estado(e)[0] == "pronto"]


def borrar(kid):
    _save([e for e in load() if e["id"] != kid])


# --------------------------------------------------------------------------
# Token y publicación
# --------------------------------------------------------------------------
def token():
    try:
        t = TOKEN_FILE.read_text("utf-8").strip()
        return t if re.fullmatch(r"[A-Za-z0-9_\-]{20,255}", t) else ""
    except OSError:
        return ""


def guardar_token(t):
    t = (t or "").strip()
    if not re.fullmatch(r"[A-Za-z0-9_\-]{20,255}", t):
        raise ClavesError("Eso no parece un token de GitHub (lleva solo letras, números y guiones y es largo).")
    APP_DIR.mkdir(parents=True, exist_ok=True)
    TOKEN_FILE.write_text(t, "utf-8")


def _repo():
    try:
        import version
        return version.UPDATE_REPO or "pavos4761-creator/PCOptimizer"
    except Exception:  # noqa: BLE001
        return "pavos4761-creator/PCOptimizer"


def _api(method, path, tok, body=None):
    req = urllib.request.Request(API + path, method=method, headers={
        "Authorization": "Bearer " + tok, "Accept": "application/vnd.github+json", "User-Agent": "HellOP-Creador",
        "X-GitHub-Api-Version": "2022-11-28"}, data=json.dumps(body).encode() if body is not None else None)
    with urllib.request.urlopen(req, timeout=20) as r:
        return json.loads(r.read().decode("utf-8"))


def _publicar(agregar=(), quitar=()):
    """Cambia revocadas.json en el repo público. Lanza ClavesError con un motivo claro."""
    tok = token()
    if not tok:
        raise ClavesError("Falta el token de GitHub (pégalo abajo, solo hace falta la primera vez).")
    path = f"/repos/{_repo()}/contents/revocadas.json"
    sha, actuales = None, set()
    try:
        cur = _api("GET", path, tok)
        sha = cur.get("sha")
        data = json.loads(base64.b64decode(cur.get("content", "")).decode("utf-8") or "{}")
        actuales = {i for i in data.get("ids", []) if isinstance(i, str)}
    except urllib.error.HTTPError as e:
        if e.code == 401:
            raise ClavesError("GitHub no acepta ese token (¿caducó o está mal copiado?).")
        if e.code not in (404,):
            raise ClavesError(f"GitHub respondió con el error {e.code} al leer la lista.")
    except (urllib.error.URLError, OSError, TimeoutError):
        raise ClavesError("No pude conectar con GitHub. Revisa tu conexión.")
    nuevos = (actuales | set(agregar)) - set(quitar)
    body = {"message": "Actualizar claves anuladas", "branch": "main",
            "content": base64.b64encode(json.dumps({"ids": sorted(nuevos)}, indent=1).encode()).decode()}
    if sha:
        body["sha"] = sha
    try:
        _api("PUT", path, tok, body)
    except urllib.error.HTTPError as e:
        if e.code in (401, 403, 404):
            raise ClavesError("El token no tiene permiso para escribir en el repositorio público "
                              "(necesita «Contents: Read and write» sobre PCOptimizer).")
        raise ClavesError(f"GitHub respondió con el error {e.code} al guardar la lista.")
    except (urllib.error.URLError, OSError, TimeoutError):
        raise ClavesError("No pude conectar con GitHub. Revisa tu conexión.")
    return nuevos


def anular(kid):
    """Marca la clave como anulada y la publica. Devuelve (publicada, mensaje)."""
    items = load()
    e = next((x for x in items if x["id"] == kid), None)
    if not e:
        raise ClavesError("No encuentro esa clave en tu lista.")
    e["anulada"], e["publicada"], e["anulada_el"] = True, False, int(time.time())
    _save(items)
    return publicar_pendientes()


def publicar_pendientes():
    items = load()
    pend = [e["id"] for e in items if e.get("anulada") and not e.get("publicada")]
    if not pend:
        return True, "No hay anulaciones pendientes."
    try:
        _publicar(agregar=pend)
    except ClavesError as ex:
        return False, f"Anulada en tu lista, pero NO publicada todavía: {ex}"
    for e in items:
        if e["id"] in pend:
            e["publicada"] = True
    _save(items)
    return True, "Anulada. Las personas con esa clave quedarán bloqueadas en cuanto su HellOP se conecte (al abrirlo o en unas horas)."


def reactivar(kid):
    """Quita la anulación (por si te equivocaste)."""
    items = load()
    e = next((x for x in items if x["id"] == kid), None)
    if not e:
        raise ClavesError("No encuentro esa clave en tu lista.")
    if e.get("publicada"):
        _publicar(quitar=[kid])
    e["anulada"], e["publicada"] = False, False
    _save(items)
    return "Clave reactivada."
