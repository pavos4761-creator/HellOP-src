"""Limpieza profunda: temporales, cachés, restos de actualizaciones y duplicados."""
import glob
import hashlib
import os
import random
import time
from pathlib import Path

from util import DEMO, IS_WIN, fmt_bytes, is_admin, ps_quote, run_cmd, run_ps


def _env(name, default=""):
    return os.environ.get(name, default)


LOCAL = Path(_env("LOCALAPPDATA", str(Path.home())))
PROGRAMDATA = Path(_env("PROGRAMDATA", "C:/ProgramData"))
WINDIR = Path(_env("WINDIR", "C:/Windows"))


class Target:
    """Una carpeta (o un patrón de archivos) que se puede vaciar."""

    def __init__(self, path, pattern=None, recursive=True):
        self.path, self.pattern, self.recursive = Path(path), pattern, recursive

    def files(self):
        if self.pattern:
            for f in glob.glob(str(self.path / self.pattern)):
                if os.path.isfile(f):
                    yield f
            return
        if self.path.is_file():
            yield str(self.path)
            return
        if not self.path.is_dir():
            return
        stack = [str(self.path)]
        while stack:
            d = stack.pop()
            try:
                with os.scandir(d) as it:
                    for e in it:
                        try:
                            if e.is_symlink():
                                continue
                            if e.is_dir(follow_symlinks=False):
                                if self.recursive:
                                    stack.append(e.path)
                            else:
                                yield e.path
                        except OSError:
                            continue
            except OSError:
                continue

    def prune_dirs(self):
        if self.pattern or not self.path.is_dir():
            return
        for root, dirs, _files in os.walk(self.path, topdown=False):
            for d in dirs:
                try:
                    os.rmdir(os.path.join(root, d))
                except OSError:
                    pass


class CleanItem:
    def __init__(self, id, title, desc, targets, needs_admin=False, default=True, warn=""):
        self.id, self.title, self.desc = id, title, desc
        self.targets, self.needs_admin, self.default, self.warn = targets, needs_admin, default, warn
        self.size = 0
        self.count = 0

    def available(self):
        return (not self.needs_admin) or is_admin()

    def scan(self):
        size = count = 0
        for t in self.targets:
            for f in t.files():
                try:
                    size += os.lstat(f).st_size
                    count += 1
                except OSError:
                    pass
        self.size, self.count = size, count
        return size

    def before_clean(self):
        pass

    def after_clean(self):
        pass

    def clean(self):
        """Devuelve (bytes liberados, archivos que no se pudieron borrar)."""
        self.before_clean()
        freed = failed = 0
        try:
            for t in self.targets:
                for f in list(t.files()):
                    try:
                        sz = os.lstat(f).st_size
                        os.chmod(f, 0o666)
                        os.remove(f)
                        freed += sz
                    except OSError:
                        failed += 1
                t.prune_dirs()
        finally:
            self.after_clean()
        return freed, failed


class WindowsUpdateItem(CleanItem):
    def before_clean(self):
        for s in ("wuauserv", "bits"):
            run_cmd(["net", "stop", s], timeout=60)

    def after_clean(self):
        for s in ("bits", "wuauserv"):
            run_cmd(["net", "start", s], timeout=60)


class RecycleBinItem(CleanItem):
    def __init__(self):
        super().__init__("recycle", "Papelera de reciclaje", "Vacía la papelera de todas las unidades.", [])

    def scan(self):
        if DEMO:
            self.size = 842 * 1024 ** 2
            return self.size
        rc, out, _ = run_ps("$s=(New-Object -ComObject Shell.Application).NameSpace(0xA); "
                            "($s.Items() | ForEach-Object { $_.ExtendedProperty('Size') } | Measure-Object -Sum).Sum")
        try:
            self.size = int(float(out.strip() or 0))
        except ValueError:
            self.size = 0
        return self.size

    def clean(self):
        size = self.size
        rc, out, err = run_ps("Clear-RecycleBin -Force -ErrorAction SilentlyContinue", timeout=120)
        return size, 0


def _browser_targets():
    ts = []
    subs = ["Cache", "Code Cache", "GPUCache", r"Service Worker\CacheStorage"]
    for rel in (r"Google\Chrome\User Data", r"Microsoft\Edge\User Data", r"BraveSoftware\Brave-Browser\User Data"):
        base = LOCAL / rel
        for prof in glob.glob(str(base / "Default")) + glob.glob(str(base / "Profile *")):
            for s in subs:
                ts.append(Target(Path(prof) / s))
    for prof in glob.glob(str(LOCAL / "Mozilla" / "Firefox" / "Profiles" / "*")):
        ts.append(Target(Path(prof) / "cache2"))
    return ts


def build_items():
    if DEMO:
        return demo_items()
    items = [
        CleanItem("temp_user", "Archivos temporales del usuario",
                  "Restos que dejan los programas al instalarse o cerrarse.", [Target(_env("TEMP", str(Path.home() / "tmp")))]),
        CleanItem("temp_win", "Temporales de Windows", "Carpeta Temp del sistema.", [Target(WINDIR / "Temp")], needs_admin=True),
        WindowsUpdateItem("win_update", "Restos de Windows Update",
                          "Instaladores de actualizaciones ya aplicadas (se detiene el servicio un momento).",
                          [Target(WINDIR / "SoftwareDistribution" / "Download")], needs_admin=True),
        CleanItem("delivery_opt", "Caché de Optimización de entrega",
                  "Archivos de actualizaciones guardados para compartir con otros PC.",
                  [Target(WINDIR / "ServiceProfiles/NetworkService/AppData/Local/Microsoft/Windows/DeliveryOptimization/Cache")], needs_admin=True),
        CleanItem("crash", "Informes de errores y volcados de memoria",
                  "Archivos que Windows guarda tras un fallo o pantallazo azul.",
                  [Target(PROGRAMDATA / "Microsoft/Windows/WER/ReportArchive"), Target(PROGRAMDATA / "Microsoft/Windows/WER/ReportQueue"),
                   Target(LOCAL / "CrashDumps"), Target(WINDIR / "Minidump"), Target(WINDIR / "MEMORY.DMP")], needs_admin=True),
        CleanItem("thumbs", "Miniaturas e iconos en caché",
                  "Se regeneran solos. Algunos archivos pueden estar en uso y se omiten.",
                  [Target(LOCAL / "Microsoft/Windows/Explorer", "thumbcache_*.db", False),
                   Target(LOCAL / "Microsoft/Windows/Explorer", "iconcache_*.db", False)], default=False),
        CleanItem("browsers", "Caché de navegadores (Chrome, Edge, Brave, Firefox)",
                  "NO borra contraseñas, historial ni sesiones: solo archivos de caché.", _browser_targets(),
                  warn="Cierra los navegadores antes para borrar todo."),
        CleanItem("shaders", "Caché de shaders de juegos (DirectX, NVIDIA, AMD)",
                  "Se regenera sola. La primera vez que abras cada juego puede tardar un poco más.",
                  [Target(LOCAL / "D3DSCache"), Target(LOCAL / "NVIDIA/DXCache"), Target(LOCAL / "NVIDIA/GLCache"),
                   Target(LOCAL / "AMD/DxCache")], default=False),
        RecycleBinItem(),
    ]
    return items


def demo_items():
    g = 1024 ** 3
    mk = lambda i, t, d, sz, admin=False, default=True, warn="": _fake(i, t, d, sz, admin, default, warn)  # noqa: E731
    return [
        mk("temp_user", "Archivos temporales del usuario", "Restos que dejan los programas al instalarse o cerrarse.", 2.4 * g),
        mk("temp_win", "Temporales de Windows", "Carpeta Temp del sistema.", 0.6 * g, True),
        mk("win_update", "Restos de Windows Update", "Instaladores de actualizaciones ya aplicadas.", 3.9 * g, True),
        mk("crash", "Informes de errores y volcados de memoria", "Archivos tras un fallo o pantallazo azul.", 1.1 * g, True),
        mk("thumbs", "Miniaturas e iconos en caché", "Se regeneran solos.", 0.2 * g, default=False),
        mk("browsers", "Caché de navegadores (Chrome, Edge, Brave, Firefox)", "NO borra contraseñas, historial ni sesiones.", 1.8 * g,
           warn="Cierra los navegadores antes para borrar todo."),
        mk("shaders", "Caché de shaders de juegos (DirectX, NVIDIA, AMD)", "Se regenera sola; el primer arranque de cada juego tarda un poco más.", 0.9 * g, default=False),
        RecycleBinItem(),
    ]


class _FakeItem(CleanItem):
    def __init__(self, *a, size=0):
        super().__init__(*a)
        self._size = int(size)

    def scan(self):
        self.size = self._size
        return self.size

    def clean(self):
        time.sleep(0.4)
        return self.size, 0


def _fake(i, t, d, sz, admin, default, warn):
    return _FakeItem(i, t, d, [], admin, default, warn, size=sz)


def windows_old_size_hint():
    """True si existe C:\\Windows.old (restos de una actualización de Windows)."""
    if DEMO:
        return True
    return (Path(_env("SystemDrive", "C:") + "\\") / "Windows.old").exists()


def open_disk_cleanup():
    if IS_WIN:
        run_cmd(["cleanmgr.exe", "/d", _env("SystemDrive", "C:")[0]], timeout=3)


# --------------------------------------------------------------------------
# Archivos duplicados (se envían a la Papelera, nunca se borran del todo)
# --------------------------------------------------------------------------
SKIP_DIRS = {"node_modules", ".git", "appdata", "$recycle.bin", "windows", "program files", "program files (x86)"}


def _hash(path, limit=None):
    h = hashlib.sha1()
    with open(path, "rb") as f:
        if limit:
            h.update(f.read(limit))
        else:
            for chunk in iter(lambda: f.read(1024 * 1024), b""):
                h.update(chunk)
    return h.hexdigest()


def default_scan_roots():
    home = Path.home()
    roots = [home / n for n in ("Downloads", "Descargas", "Documents", "Documentos", "Desktop", "Escritorio",
                                "Pictures", "Imágenes", "Videos", "Vídeos", "Music", "Música")]
    return [r for r in roots if r.is_dir()]


def find_duplicates(roots, min_size=1024 * 1024, progress=None, limit=300):
    """Devuelve grupos [{size, files:[(ruta, mtime)]}] ordenados por espacio desperdiciado."""
    if DEMO:
        time.sleep(1.2)
        g = lambda n: n * 1024 ** 2  # noqa: E731
        now = time.time()
        return [
            {"size": g(210), "files": [(r"C:\Users\Tú\Downloads\setup_juego.exe", now - 9e6), (r"C:\Users\Tú\Desktop\setup_juego (1).exe", now - 3e6), (r"C:\Users\Tú\Documents\setup_juego - copia.exe", now - 1e6)]},
            {"size": g(48), "files": [(r"C:\Users\Tú\Pictures\viaje\IMG_2041.jpg", now - 2e7), (r"C:\Users\Tú\Downloads\IMG_2041.jpg", now - 1e7)]},
            {"size": g(6), "files": [(r"C:\Users\Tú\Documents\informe.pdf", now - 5e6), (r"C:\Users\Tú\Desktop\informe.pdf", now - 4e6)]},
        ]
    by_size = {}
    seen = 0
    for root in roots:
        for dirpath, dirs, files in os.walk(root):
            dirs[:] = [d for d in dirs if d.lower() not in SKIP_DIRS and not d.startswith(".")]
            for fn in files:
                p = os.path.join(dirpath, fn)
                try:
                    st = os.lstat(p)
                except OSError:
                    continue
                if st.st_size >= min_size and not os.path.islink(p):
                    by_size.setdefault(st.st_size, []).append((p, st.st_mtime))
                seen += 1
                if progress and seen % 500 == 0:
                    progress(f"Explorando… {seen} archivos")
    groups = []
    candidates = [(s, fl) for s, fl in by_size.items() if len(fl) > 1]
    for i, (size, fl) in enumerate(candidates):
        if progress:
            progress(f"Comparando archivos del mismo tamaño ({i + 1}/{len(candidates)})")
        quick = {}
        for p, m in fl:
            try:
                quick.setdefault(_hash(p, 64 * 1024), []).append((p, m))
            except OSError:
                pass
        for same in quick.values():
            if len(same) < 2:
                continue
            full = {}
            for p, m in same:
                try:
                    full.setdefault(_hash(p), []).append((p, m))
                except OSError:
                    pass
            for dup in full.values():
                if len(dup) > 1:
                    groups.append({"size": size, "files": sorted(dup, key=lambda x: x[1])})
    groups.sort(key=lambda g: -g["size"] * (len(g["files"]) - 1))
    return groups[:limit]


def send_to_recycle_bin(paths):
    """Mueve archivos a la Papelera (se pueden recuperar). Devuelve (movidos, fallidos)."""
    if DEMO:
        time.sleep(0.5)
        return len(paths), 0
    ok = fail = 0
    for i in range(0, len(paths), 40):
        batch = paths[i:i + 40]
        arr = ",".join(ps_quote(p) for p in batch)
        script = ("Add-Type -AssemblyName Microsoft.VisualBasic; $ok=0; "
                  f"foreach($p in @({arr})){{ try {{ [Microsoft.VisualBasic.FileIO.FileSystem]::DeleteFile($p,'OnlyErrorDialogs','SendToRecycleBin'); $ok++ }} catch {{}} }}; $ok")
        rc, out, _ = run_ps(script, timeout=180)
        try:
            n = int(out.strip().splitlines()[-1])
        except (ValueError, IndexError):
            n = 0
        ok += n
        fail += len(batch) - n
    return ok, fail
