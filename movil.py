"""Monitor en el móvil: una mini página que se abre desde el navegador del móvil (misma red Wi-Fi) y enseña CPU, RAM, gráfica y temperaturas en vivo.

Seguridad: está APAGADO por defecto; solo funciona mientras tú lo enciendes; solo lectura; pide una clave al azar que va dentro del enlace
y que cambia cada vez que lo enciendes; no sale de tu red local (no abre puertos en el router). El tráfico en tu Wi-Fi no va cifrado (HTTP),
así que úsalo en tu casa y no en redes públicas.
"""
import json
import secrets
import socket
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

import psutil

from util import DEMO, nvsmi, run_cmd

PAGINA = """<!doctype html><html lang="es"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
<title>HellOP · en vivo</title><style>
:root{--bg:#120d1d;--p:#1f1636;--l:#3a2a63;--fg:#f3eefb;--mu:#a99cc7}
*{box-sizing:border-box}body{margin:0;background:radial-gradient(700px 400px at 0 -10%,#3b2370,transparent 60%),var(--bg);color:var(--fg);font:16px system-ui,sans-serif;padding:max(18px,env(safe-area-inset-top)) 16px 28px}
h1{font-size:18px;margin:0 0 2px}.s{color:var(--mu);font-size:13px;margin-bottom:16px}.g{display:grid;grid-template-columns:1fr 1fr;gap:12px}
.c{background:linear-gradient(160deg,#2a1e47,var(--p));border:1px solid var(--l);border-radius:20px;padding:14px 16px}.c b{display:block;font-size:12px;letter-spacing:.12em;color:var(--mu)}
.v{font-size:36px;font-weight:800;margin:4px 0 8px}.t{height:7px;border-radius:9px;background:#ffffff14;overflow:hidden}.t i{display:block;height:100%;width:0;border-radius:9px;background:#5bff9a;transition:width .6s,background .6s}
.w{grid-column:1/3}.p{display:flex;justify-content:space-between;font-size:14px;padding:5px 0;border-top:1px solid #ffffff10}.p:first-of-type{border:0}
#e{display:none;background:#ff5d73;color:#1a0610;border-radius:12px;padding:8px 12px;margin-bottom:12px;font-weight:700}
</style><body><h1>HellOP · en vivo</h1><div class="s" id="n">Conectando…</div><div id="e">Sin conexión con el PC</div>
<div class="g" id="g"></div><script>
const K=new URLSearchParams(location.search).get('k')||'';const G=document.getElementById('g');
const col=v=>v<60?'#5bff9a':v<85?'#ffc233':'#ff5d73';
function caja(id,t,u){const d=document.createElement('div');d.className='c';d.innerHTML='<b>'+t+'</b><div class="v" id="v'+id+'">–</div><div class="t"><i id="b'+id+'"></i></div>';G.appendChild(d)}
[['cpu','PROCESADOR'],['ram','MEMORIA'],['gpu','GRÁFICA'],['vram','VRAM']].forEach(a=>caja(a[0],a[1]));
const w=document.createElement('div');w.className='c w';w.innerHTML='<b>LO QUE MÁS GASTA</b><div id="pr"></div><b style="margin-top:12px">TEMPERATURAS</b><div id="tm"></div>';G.appendChild(w);
function set(id,v,txt){const e=document.getElementById('v'+id);if(v==null){e.textContent='–';document.getElementById('b'+id).style.width='0';return}
e.textContent=txt||v+' %';const b=document.getElementById('b'+id);b.style.width=Math.min(100,v)+'%';b.style.background=col(v)}
async function t(){try{const r=await fetch('/d?k='+encodeURIComponent(K),{cache:'no-store'});if(!r.ok)throw 0;const d=await r.json();
document.getElementById('e').style.display='none';document.getElementById('n').textContent=d.pc+' · '+new Date().toLocaleTimeString();
set('cpu',d.cpu);set('ram',d.ram);set('gpu',d.gpu);set('vram',d.vram);
document.getElementById('pr').innerHTML=d.top.map(p=>'<div class="p"><span>'+p[0]+'</span><span>'+p[1]+' %</span></div>').join('')||'–';
document.getElementById('tm').innerHTML=d.temps.map(p=>'<div class="p"><span>'+p[0]+'</span><span style="color:'+col(p[1])+'">'+p[1]+' °C</span></div>').join('')||'<div class="p"><span>Sin sensores</span><span></span></div>'}
catch(e){document.getElementById('e').style.display='block'}setTimeout(t,1000)}t();
</script></html>"""


class _Estado:
    def __init__(self):
        self.datos = {"pc": socket.gethostname(), "cpu": 0, "ram": 0, "gpu": None, "vram": None, "top": [], "temps": []}
        self.clave = ""
        self.visto = 0.0
        self.parar = threading.Event()


ESTADO = _Estado()
_srv = {"http": None, "hilo": None, "port": None}


def _muestrea():
    """Hilo: renueva los datos cada segundo (la lectura de la gráfica cada 2 s, las temperaturas cada 15 s)."""
    exe = None if DEMO else nvsmi()
    psutil.cpu_percent(None)
    for p in psutil.process_iter():
        try:
            p.cpu_percent(None)
        except (psutil.Error, OSError):
            pass
    n, ultimo_t, temps = 0, 0.0, []
    while not ESTADO.parar.wait(1.0):
        d = ESTADO.datos
        d["cpu"], d["ram"] = round(psutil.cpu_percent(None)), round(psutil.virtual_memory().percent)
        if DEMO:
            import random
            d["gpu"], d["vram"] = random.randint(30, 80), random.randint(40, 60)
            d["top"] = [["Game.exe", random.randint(10, 30)], ["chrome.exe", random.randint(2, 9)]]
            d["temps"] = [["CPU", random.randint(55, 70)], ["GPU", random.randint(50, 65)]]
            continue
        if exe and n % 2 == 0:
            rc, o, _ = run_cmd([exe, "--query-gpu=utilization.gpu,memory.used,memory.total,temperature.gpu", "--format=csv,noheader,nounits"], timeout=5)
            try:
                u, mu, mt, tg = (float(x) for x in o.splitlines()[0].split(","))
                d["gpu"], d["vram"] = round(u), round(mu / mt * 100)
                temps = [t for t in temps if t[0] != "GPU"] + [["GPU", round(tg)]]
            except Exception:  # noqa: BLE001
                pass
        if time.time() - ultimo_t > 15:
            ultimo_t = time.time()
            try:
                import sysinfo
                cpu_t = [t for t in sysinfo.read_temps() if t.get("kind") == "cpu"]
                temps = [t for t in temps if t[0] == "GPU"] + ([["CPU", round(max(x["value"] for x in cpu_t))]] if cpu_t else [])
            except Exception:  # noqa: BLE001
                pass
        d["temps"] = temps
        if n % 3 == 0:
            filas = []
            for p in psutil.process_iter(["name"]):
                try:
                    filas.append((p.cpu_percent(None) / (psutil.cpu_count() or 1), p.info["name"] or "?"))
                except (psutil.Error, OSError):
                    continue
            filas.sort(reverse=True)
            d["top"] = [[nom, round(c)] for c, nom in filas[:4] if c >= 1]
        n += 1


class _Manejador(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _ok(self, cuerpo, tipo):
        b = cuerpo.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", tipo + "; charset=utf-8")
        self.send_header("Content-Length", str(len(b)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(b)

    def do_GET(self):
        u = urlparse(self.path)
        k = (parse_qs(u.query).get("k") or [""])[0]
        if not ESTADO.clave or not secrets.compare_digest(k, ESTADO.clave):
            self.send_response(403)
            self.end_headers()
            return
        ESTADO.visto = time.time()
        if u.path == "/d":
            self._ok(json.dumps(ESTADO.datos), "application/json")
        else:
            self._ok(PAGINA, "text/html")


def ip_local():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("10.255.255.255", 1))        # no envía nada: solo averigua qué tarjeta de red usaría
        return s.getsockname()[0]
    except OSError:
        return "127.0.0.1"
    finally:
        s.close()


def encendido():
    return _srv["http"] is not None


def enlace():
    return f"http://{ip_local()}:{_srv['port']}/?k={ESTADO.clave}" if encendido() else None


def encender():
    if encendido():
        return enlace()
    ESTADO.parar.clear()
    ESTADO.clave = secrets.token_urlsafe(6)
    host = "127.0.0.1" if DEMO else "0.0.0.0"
    for port in range(8765, 8786):
        try:
            _srv["http"] = ThreadingHTTPServer((host, port), _Manejador)
            _srv["port"] = port
            break
        except OSError:
            continue
    else:
        raise OSError("No encontré un puerto libre (8765-8785).")
    _srv["hilo"] = threading.Thread(target=_srv["http"].serve_forever, daemon=True)
    _srv["hilo"].start()
    threading.Thread(target=_muestrea, daemon=True).start()
    return enlace()


def apagar():
    ESTADO.parar.set()
    ESTADO.clave = ""
    if _srv["http"]:
        try:
            _srv["http"].shutdown()
            _srv["http"].server_close()
        except Exception:  # noqa: BLE001
            pass
    _srv["http"], _srv["port"] = None, None


def conectado():
    return encendido() and time.time() - ESTADO.visto < 5


def matriz_qr(texto):
    """Matriz de módulos del QR (lista de listas de bool) o None si falta la librería."""
    try:
        import qrcode
        q = qrcode.QRCode(border=0, error_correction=qrcode.constants.ERROR_CORRECT_L)
        q.add_data(texto)
        q.make(fit=True)
        return q.get_matrix()
    except Exception:  # noqa: BLE001
        return None
