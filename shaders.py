"""Limpiar cachés de shaders (DirectX, NVIDIA, AMD, Intel y Steam).

Los juegos guardan ahí «trozos» de gráficos ya compilados para no recompilarlos cada vez. A veces se corrompen o se quedan
viejos tras actualizar el driver o el juego y dan tirones raros, parpadeos o artefactos. Borrarlos obliga a regenerarlos.

Honestidad: limpiar esto NO sube los FPS. Solo arregla fallos. La primera partida después irá algo peor (tirones al
compilar de nuevo) y luego vuelve a la normalidad. Se borra solo el CONTENIDO de estas carpetas concretas.
"""
import os
import shutil
from pathlib import Path

import actions
from actions import Action
from util import DEMO, IS_WIN, fmt_bytes


def _env(name):
    return Path(os.environ.get(name, "") or "nonexistent-env")


def _caches():
    la, pd = _env("LOCALAPPDATA"), _env("PROGRAMDATA")
    steam = []
    try:
        import games
        root = games._steam_root()
        if root:
            steam.append(Path(root) / "steamapps" / "shadercache")
    except Exception:  # noqa: BLE001
        pass
    return [
        ("d3d", "DirectX (Windows)", "Caché de shaders que crea Windows para todos los juegos.", [la / "D3DSCache"]),
        ("nvidia", "NVIDIA", "Cachés de DirectX y OpenGL de tu gráfica NVIDIA.",
         [la / "NVIDIA" / "DXCache", la / "NVIDIA" / "GLCache", pd / "NVIDIA Corporation" / "NV_Cache"]),
        ("amd", "AMD", "Cachés de DirectX, OpenGL y Vulkan de tu gráfica AMD.",
         [la / "AMD" / "DxCache", la / "AMD" / "DxcCache", la / "AMD" / "GLCache", la / "AMD" / "VkCache"]),
        ("intel", "Intel", "Caché de shaders de la gráfica Intel.", [la / "Intel" / "ShaderCache"]),
        ("steam", "Steam", "Shaders precompilados que descarga Steam para algunos juegos.", steam),
    ]


def _is_link(p):
    try:
        return p.is_symlink() or (hasattr(p, "is_junction") and p.is_junction())
    except OSError:
        return True


def _size(path):
    total = 0
    for root, dirs, files in os.walk(path, followlinks=False):
        dirs[:] = [d for d in dirs if not _is_link(Path(root) / d)]
        for f in files:
            try:
                total += os.path.getsize(os.path.join(root, f))
            except OSError:
                pass
    return total


def scan():
    """Lista de cachés que existen en este PC: [{id, label, desc, paths, size}]."""
    if DEMO:
        return [{"id": "d3d", "label": "DirectX (Windows)", "desc": "Caché de shaders que crea Windows para todos los juegos.",
                 "paths": ["D3DSCache"], "size": 412 * 1048576},
                {"id": "nvidia", "label": "NVIDIA", "desc": "Cachés de DirectX y OpenGL de tu gráfica NVIDIA.",
                 "paths": ["DXCache", "GLCache"], "size": 1900 * 1048576},
                {"id": "steam", "label": "Steam", "desc": "Shaders precompilados que descarga Steam para algunos juegos.",
                 "paths": ["shadercache"], "size": 640 * 1048576}]
    out = []
    for cid, label, desc, paths in _caches():
        ex = [p for p in paths if p.is_dir() and not _is_link(p)]
        if ex:
            out.append({"id": cid, "label": label, "desc": desc, "paths": [str(p) for p in ex], "size": sum(_size(p) for p in ex)})
    return out


def _running_game():
    try:
        import fps
        import psutil
        known = {n.lower() for n in fps.KNOWN_GAMES}
        for p in psutil.process_iter(["name"]):
            if (p.info.get("name") or "").lower() in known:
                return p.info["name"]
    except Exception:  # noqa: BLE001
        pass
    return None


def _empty(path):
    """Borra el contenido de la carpeta (no la carpeta). Devuelve (bytes liberados, archivos que no se pudieron borrar)."""
    freed = fail = 0
    for child in list(path.iterdir()):
        if _is_link(child):
            continue
        size = _size(child) if child.is_dir() else (child.stat().st_size if child.exists() else 0)
        try:
            if child.is_dir():
                shutil.rmtree(child)
            else:
                child.unlink()
            freed += size
        except OSError:
            fail += 1
    return freed, fail


class ShaderCleanAction(Action):
    group = "deep"
    reversible = False
    effect = "mínimo"

    def __init__(self, cid, label):
        self.cid = cid
        self.id = f"shaders:{cid}"
        self.title = f"Limpiar caché de shaders: {label}"
        self.desc = "Se vuelve a generar sola al abrir los juegos."

    def apply(self):
        if DEMO:
            return {"_msg": "(Demo) no se ha borrado nada"}
        game = _running_game()
        if game:
            raise RuntimeError(f"Cierra «{game}» antes de limpiar los shaders")
        target = next((c for c in _caches() if c[0] == self.cid), None)
        if not target:
            raise RuntimeError("Caché desconocida")
        freed = fail = 0
        for p in target[3]:
            if p.is_dir() and not _is_link(p):
                f, x = _empty(p)
                freed += f
                fail += x
        msg = f"Liberados {fmt_bytes(freed)}" + (f" ({fail} archivos en uso, se quedaron)" if fail else "")
        return {"freed": freed, "_msg": msg}


def clean(items):
    """Limpia las cachés indicadas [{id,label,size}…]. Devuelve (bytes aprox. liberados, [errores])."""
    freed, errs = 0, []
    for it in items:
        r = actions.execute(ShaderCleanAction(it["id"], it["label"]))
        if r.ok:
            freed += int(it.get("size", 0))
        else:
            errs.append(f"{it['label']}: {r.msg}")
    return freed, errs
