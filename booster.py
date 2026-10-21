"""Modo Extremo EN VIVO: mientras está activo, la app
  · pide al reloj de Windows la resolución mínima (≈0,5 ms) → menos latencia de planificación,
  · sube la prioridad de tu juego,
  · baja la prioridad de todo lo que haya de fondo (menos tirones),
  · libera la RAM que usan los programas de fondo,
  · pausa servicios que despiertan al disco/CPU (SysMain, búsqueda, Windows Update…),
y al DESACTIVARLO (o cerrar la app) lo deja todo exactamente como estaba.
Debe seguir abierta mientras juegas."""
import ctypes
import json
import os
import time

import psutil

from util import APP_DIR, DEMO, IS_WIN, is_admin, run_cmd

STATE_FILE = APP_DIR / ("booster_demo.json" if DEMO else "booster_estado.json")

SERVICES_TO_PAUSE = ["SysMain", "WSearch", "wuauserv", "BITS", "DoSvc", "DiagTrack"]

# nunca se tocan (sistema, seguridad, voz/streaming que NO conviene frenar)
NEVER_TOUCH = {
    "system", "registry", "smss.exe", "csrss.exe", "wininit.exe", "services.exe", "lsass.exe", "svchost.exe",
    "winlogon.exe", "dwm.exe", "explorer.exe", "fontdrvhost.exe", "sihost.exe", "ctfmon.exe", "audiodg.exe",
    "msmpeng.exe", "securityhealthservice.exe", "securityhealthsystray.exe", "memcompression", "conhost.exe",
    "discord.exe", "obs64.exe", "obs32.exe", "teamspeak3.exe", "ts3client_win64.exe", "mumble.exe", "voicemeeter.exe",
    "voicemeeter8x64.exe", "nvcontainer.exe", "nvidia share.exe", "nvdisplay.container.exe", "radeonsoftware.exe",
    "python.exe", "pythonw.exe", "pcoptimizer.exe", "hellop.exe", "taskmgr.exe",
}

PRIO = {}
if IS_WIN:
    PRIO = {"high": psutil.HIGH_PRIORITY_CLASS, "above": psutil.ABOVE_NORMAL_PRIORITY_CLASS,
            "normal": psutil.NORMAL_PRIORITY_CLASS, "below": psutil.BELOW_NORMAL_PRIORITY_CLASS,
            "idle": psutil.IDLE_PRIORITY_CLASS}


# --------------------------------------------------------------------------
# Resolución del temporizador de Windows
# --------------------------------------------------------------------------
def _ntdll():
    return ctypes.WinDLL("ntdll") if IS_WIN else None


def query_timer_ms():
    """(actual, la mejor posible) en milisegundos, o (None, None)."""
    if DEMO:
        return (0.5 if _demo_state["timer"] else 15.6), 0.5
    if not IS_WIN:
        return None, None
    try:
        mn, mx, cur = ctypes.c_ulong(), ctypes.c_ulong(), ctypes.c_ulong()
        _ntdll().NtQueryTimerResolution(ctypes.byref(mn), ctypes.byref(mx), ctypes.byref(cur))
        return cur.value / 10000, mx.value / 10000
    except Exception:  # noqa: BLE001
        return None, None


def set_timer(on):
    """Pide (o suelta) la mejor resolución disponible para el temporizador. Devuelve ms actuales."""
    if DEMO:
        _demo_state["timer"] = on
        return 0.5 if on else 15.6
    if not IS_WIN:
        return None
    _cur, best = query_timer_ms()
    if not best:
        return None
    got = ctypes.c_ulong()
    _ntdll().NtSetTimerResolution(ctypes.c_ulong(int(best * 10000)), bool(on), ctypes.byref(got))
    return query_timer_ms()[0]


_demo_state = {"timer": False}


# --------------------------------------------------------------------------
# Procesos
# --------------------------------------------------------------------------
def candidate_games(limit=40):
    """Procesos del usuario ordenados por RAM, para que elijas tu juego."""
    me = os.getpid()
    out = []
    if DEMO:
        return [("Cyberpunk2077.exe", 6.1 * 1024 ** 3, 4111), ("VALORANT-Win64-Shipping.exe", 3.4 * 1024 ** 3, 5230),
                ("cs2.exe", 2.8 * 1024 ** 3, 6122), ("FortniteClient-Win64-Shipping.exe", 4.2 * 1024 ** 3, 7001),
                ("chrome.exe", 1.4 * 1024 ** 3, 2210), ("steam.exe", 0.4 * 1024 ** 3, 1888)]
    try:
        user = psutil.Process().username()
    except psutil.Error:
        user = None
    agg = {}
    for p in psutil.process_iter(["pid", "name", "memory_info", "username"]):
        try:
            i = p.info
            n = (i["name"] or "")
            if i["pid"] == me or n.lower() in NEVER_TOUCH or not n.lower().endswith(".exe"):
                continue
            if user and i["username"] != user:
                continue
            e = agg.setdefault(n, [0, i["pid"]])
            e[0] += i["memory_info"].rss
        except (psutil.NoSuchProcess, psutil.AccessDenied, AttributeError, TypeError):
            continue
    for n, (rss, pid) in agg.items():
        out.append((n, rss, pid))
    out.sort(key=lambda x: -x[1])
    return out[:limit]


def _trim(pid):
    """Vacía el working set de un proceso (Windows lo vuelve a cargar si lo necesita)."""
    if not IS_WIN:
        return
    try:
        h = ctypes.windll.kernel32.OpenProcess(0x0100 | 0x0400, False, pid)   # SET_QUOTA | QUERY_INFORMATION
        if h:
            ctypes.windll.psapi.EmptyWorkingSet(h)
            ctypes.windll.kernel32.CloseHandle(h)
    except Exception:  # noqa: BLE001
        pass


class Booster:
    def __init__(self):
        self.active = False
        self.game_name = None
        self.saved = {}                  # pid -> prioridad original
        self.stopped = []                # servicios que paramos
        self.freed = 0
        self.lowered = 0
        self.started = None
        self.game_pids = []
        self.timer_ms = None

    # ------------------------------------------------------------------
    def start(self, game_name, opts, log=lambda m: None):
        """opts: timer, game_prio, bg_prio, bg_ram, services, dns (bool)."""
        if self.active:
            return
        self.active = True
        self.started = time.time()
        self.game_name = game_name
        self.saved.clear()
        self.stopped.clear()
        self.freed = self.lowered = 0

        if opts.get("timer"):
            ms = set_timer(True)
            self.timer_ms = ms
            log(f"⏱  Temporizador de Windows a {ms:.2f} ms" if ms else "⏱  No pude cambiar el temporizador")

        self.game_pids = []
        if game_name and not DEMO:
            for p in psutil.process_iter(["pid", "name"]):
                if (p.info["name"] or "").lower() == game_name.lower():
                    self.game_pids.append(p.info["pid"])
        if opts.get("game_prio") and game_name and DEMO:
            log(f"🎮  {game_name}: prioridad ALTA (demo)")
        elif opts.get("game_prio") and game_name:
            n = 0
            for pid in self.game_pids:
                try:
                    pr = psutil.Process(pid)
                    self.saved.setdefault(pid, pr.nice())
                    pr.nice(PRIO["high"])
                    n += 1
                except (psutil.Error, KeyError):
                    pass
            log(f"🎮  {game_name}: prioridad ALTA ({n} proceso{'s' if n != 1 else ''})" if n else
                f"🎮  {game_name} no está abierto: ábrelo y vuelve a activar")

        bg = self._background(game_name)
        if opts.get("bg_prio"):
            for pid, name, cpu in bg:
                if DEMO:
                    self.lowered += 1
                    continue
                try:
                    pr = psutil.Process(pid)
                    cur = pr.nice()
                    if cur != PRIO["normal"]:
                        continue                      # no tocamos lo que ya tiene prioridad especial
                    self.saved.setdefault(pid, cur)
                    pr.nice(PRIO["idle"] if cpu > 3 else PRIO["below"])
                    self.lowered += 1
                except (psutil.Error, KeyError):
                    pass
            log(f"⬇  {self.lowered} programas de fondo con prioridad baja")
        if opts.get("bg_ram"):
            freed = 0
            for pid, name, cpu in ([] if DEMO else bg):
                try:
                    before = psutil.Process(pid).memory_info().rss
                    _trim(pid)
                    freed += max(0, before - psutil.Process(pid).memory_info().rss)
                except psutil.Error:
                    pass
            self.freed = freed if not DEMO else 1.1 * 1024 ** 3
            log(f"🧹  RAM liberada de programas de fondo: {self.freed / 1024 ** 2:.0f} MB")
        if opts.get("services") and (is_admin() or DEMO):
            for name in SERVICES_TO_PAUSE:
                try:
                    if DEMO:
                        self.stopped.append(name)
                        continue
                    if psutil.win_service_get(name).status() == "running":
                        rc, out, err = run_cmd(["sc", "stop", name], timeout=30)
                        if rc == 0:
                            self.stopped.append(name)
                except Exception:  # noqa: BLE001
                    pass
            log(f"⏸  Servicios en pausa: {', '.join(self.stopped) or 'ninguno'}")
        elif opts.get("services"):
            log("⏸  Servicios: necesitas administrador para pausarlos")
        if opts.get("dns") and not DEMO:
            run_cmd(["ipconfig", "/flushdns"])
            log("🌐  Caché DNS vaciada")
        self._save_state()
        log("✔  MODO EXTREMO ACTIVO. Deja esta ventana abierta mientras juegas.")

    # ------------------------------------------------------------------
    def _background(self, game_name):
        """[(pid, nombre, cpu%)] de procesos del usuario que NO son el juego ni críticos."""
        if DEMO:
            return [(1, "chrome.exe", 4.0), (2, "msedge.exe", 1.0), (3, "Teams.exe", 2.0), (4, "OneDrive.exe", 0.2)]
        me = os.getpid()
        try:
            user = psutil.Process().username()
        except psutil.Error:
            user = None
        procs = []
        for p in psutil.process_iter(["pid", "name", "username"]):
            try:
                n = (p.info["name"] or "")
                nl = n.lower()
                if p.info["pid"] == me or nl in NEVER_TOUCH or not nl.endswith(".exe"):
                    continue
                if game_name and nl == game_name.lower():
                    continue
                if user and p.info["username"] != user:
                    continue
                p.cpu_percent(None)
                procs.append(p)
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
        time.sleep(0.4)
        out = []
        for p in procs:
            try:
                out.append((p.pid, p.name(), p.cpu_percent(None)))
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
        return out

    # ------------------------------------------------------------------
    def stop(self, log=lambda m: None):
        if not self.active:
            return
        restored = 0
        if not DEMO:
            for pid, prio in list(self.saved.items()):
                try:
                    psutil.Process(pid).nice(prio)
                    restored += 1
                except psutil.Error:
                    pass
            for name in self.stopped:
                run_cmd(["sc", "start", name], timeout=30)
        set_timer(False)
        log(f"↩  Prioridades restauradas ({restored or len(self.saved)}), servicios reanudados ({len(self.stopped)}), "
            "temporizador devuelto a su valor normal.")
        self.saved.clear()
        self.stopped.clear()
        self.active = False
        try:
            STATE_FILE.unlink()
        except OSError:
            pass

    # ------------------------------------------------------------------
    def stats(self):
        cur, best = query_timer_ms()
        game_prio = "—"
        if self.active and self.game_pids and not DEMO:
            try:
                v = psutil.Process(self.game_pids[0]).nice()
                game_prio = next((k for k, x in PRIO.items() if x == v), "?").upper()
            except (psutil.Error, IndexError):
                pass
        elif DEMO and self.active:
            game_prio = "HIGH"
        return {"timer": cur, "best": best, "lowered": self.lowered, "freed": self.freed,
                "services": len(self.stopped), "game_prio": game_prio,
                "elapsed": int(time.time() - self.started) if self.started and self.active else 0}

    def _save_state(self):
        try:
            STATE_FILE.write_text(json.dumps({"stopped": self.stopped, "ts": time.time()}), "utf-8")
        except OSError:
            pass


def recover_after_crash():
    """Si la app se cerró de golpe con el modo activo, vuelve a arrancar los servicios pausados."""
    try:
        data = json.loads(STATE_FILE.read_text("utf-8"))
    except Exception:  # noqa: BLE001
        return []
    if not DEMO:
        for name in data.get("stopped", []):
            run_cmd(["sc", "start", name], timeout=30)
    try:
        STATE_FILE.unlink()
    except OSError:
        pass
    return data.get("stopped", [])
