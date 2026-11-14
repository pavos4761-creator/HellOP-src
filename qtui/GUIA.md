# Guía para portar una pantalla de HellOP de Tkinter a Qt (PySide6)

HellOP es una app de optimización de Windows. La lógica (módulos `actions.py`, `booster.py`, `fps.py`, `cuello.py`, `sysinfo.py`, `licencia.py`, `updater.py`…)
NO se toca: solo se reescribe la interfaz. Cada pantalla vieja está en `page_<x>.py` (Tkinter); la nueva va en `qtui/paginas/<modulo>.py` (Qt).

## Reglas
- Prohibido `import tkinter`. Solo PySide6 (`from PySide6.QtCore import …`, `QtWidgets`, `QtGui`) y los componentes de `qtui/`.
- Mantén TODA la funcionalidad y los textos en español de la pantalla Tk (mismos botones, mismas explicaciones, mismos avisos). Puedes mejorar el orden visual.
- Mantén el tono: español sencillo y honesto (no prometas más de lo que hace).
- No ejecutes git. No toques archivos fuera de tu(s) archivo(s) de página. No edites `qtui/shell.py`, `widgets.py`, `theme.py` (si necesitas algo nuevo, impleméntalo localmente en tu archivo).
- El código no se puede ejecutar aquí (no hay PySide6 instalado): escribe con mucho cuidado; compruébalo con `python3 -m py_compile` y relee. Se probará en CI con capturas.
- Modo demo (`util.DEMO`): las funciones de lógica ya devuelven datos de ejemplo; no cambies eso.

## Estructura de una pantalla
```python
from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import QHBoxLayout, QVBoxLayout, QWidget
from ..widgets import Pagina, Tarjeta, Etiqueta, Boton, Insignia, Interruptor, Casilla, Barra, Tabla, Rejilla, Separador, fila, columna, vacia, repulir
from .. import theme
from ..graficos import Anillo, Linea, Medidor

class Miclase(Pagina):                      # el nombre exacto de la clase lo da el encargo
    titulo_texto = "Título"
    sub_texto = "Una frase que explica la pantalla."
    def __init__(self, app):
        super().__init__(app)               # crea título + subtítulo + columna con scroll en self.col
        ...                                  # añade widgets con self.add(w) o self.col.addWidget(w)
    def al_mostrar(self): ...               # equivale a on_show() del Tk (se llama cada vez que se abre la pantalla)
    def al_ocultar(self): ...               # parar timers aquí
    def apaga(self): ...                    # opcional: se llama al cerrar la app (parar hilos/servicios)
```
La clase se construye con `Clase(app)` donde `app` es la ventana principal (ver servicios). Importa la lógica con imports normales
(`import actions`, `import sysinfo`…); desde `qtui/paginas/` el código raíz está en el path (usa `import actions`, NO imports relativos para la lógica).

## Servicios de `self.app`
- `self.app.bg(fn, done=None, fail=None)`: ejecuta `fn()` en un hilo; `done(resultado)` y `fail(excepcion)` se llaman en el hilo de la interfaz.
  Sin `fail`, un error muestra un aviso y se anota en errores.log.
- `self.app.ui(fn, *args)`: llama a `fn(*args)` en el hilo de la interfaz (seguro desde otro hilo; úsalo para progreso dentro de `fn`).
- `self.app.after(ms, fn)`: llamada diferida una vez. Para repetir usa `QTimer(self)` y páralo en `al_ocultar`.
- `self.app.toast("texto", "green")` aviso flotante (tonos: accent, green, yellow, red, teal, muted). `self.app.status("texto")`.
- `self.app.ir("clave")` navega a otra pantalla (claves: home analysis score optimize streaming mando clean shaders arranque games gameprof booster monitor noche movil diag doctor fps tweaks cuello bios oc health debloat history update license).
- `self.app.pregunta(titulo, texto) -> bool` (sí/no), `self.app.info(titulo, texto)`, `self.app.aviso_modal(titulo, texto)`.
- `self.app.pages["clave"]` devuelve (y crea si hace falta) otra pantalla; `self.app.pages.creada("clave")` dice si ya existe.
- `self.app.refresh_license()`, `self.app.restart_now()`, `self.app.restart_admin()`, `self.app.exportar_informe()`, `self.app.mark_update_available(version)`.
- Para pantallas con mucho trabajo asíncrono: guarda `g = self.gen` antes de lanzar `bg` y en el callback haz `if g != self.gen: return`; `self.limpia()` incrementa `self.gen` y vacía la columna.

## Componentes (`qtui/widgets.py`)
- `Etiqueta(texto, role=None, tone=None, wrap=True)`: roles `title h2 h3 muted small mono big`; tonos `accent teal green yellow red muted`. `.setText()`, `.tono("red")`.
- `Boton(texto, cmd, kind="primary|soft|ghost|link", tone=None|"green"|"yellow"|"red"|"teal")`; `.set_text()`, `.set_enabled(bool)` (o `setEnabled`).
- `Insignia(texto, tone)` etiqueta pequeña tipo «RIESGO BAJO» (`.pon(texto, tone)`).
- `Interruptor(on=False, tone="accent")` con `.isChecked()`, `.poner(bool)`, señal `.cambio(bool)`. `Casilla(texto, marcada=False)` (QCheckBox: `.isChecked()`, `.toggled`).
- `Tarjeta(tone=None, titulo=None, margen=16, espacio=8, soft=False)`: marco redondeado; `.lay` es su QVBoxLayout; `.add(w)`; `.tono("green")` filo de color; `.marcada(True)` borde verde.
- `Barra(valor, tone=None)` barra de progreso fina (`.pon(v, tone)`). `Separador()`.
- `Tabla(columnas, anchos=None)` + `.rellena(lista_de_filas, tonos=None)`; `.seleccion()` índice de fila.
- `Rejilla(columnas=3, espacio=12)` cuadrícula de columnas iguales: `.add(widget)`, `.limpia()`.
- `fila(*widgets)` / `columna(*widgets)` ayudan a montar layouts (usa `None` como separador elástico).
- `vacia(layout)` borra todos los hijos de un layout.
- `Pagina.barra_inferior()` devuelve un QHBoxLayout de una barra fija bajo el scroll (p. ej. para botones de «Aplicar»).
- Gráficos (`qtui/graficos.py`): `Anillo(valor, tone, texto, sub, tam)` `.pon(v, tone, texto, sub)`; `Linea(tone, maximo=100, alto=70, n=60)` `.añade(v)`/`.pon(lista)`; `Medidor(nombre, tone)` `.pon(v, texto)`.
- Campos de texto: `QLineEdit`, `QComboBox`, `QPlainTextEdit`, `QSpinBox` normales de Qt (ya tienen estilo). Diálogos: `QFileDialog`, `QMessageBox` normales.

## Colores y estilo
- NUNCA pongas colores fijos en hexadecimal. Usa tonos (`tone="green"`) o `theme.C["panel"]`, `theme.C["muted"]`, `theme.color("accent")`, `theme.hexa("green", 0.15)`.
  (Claves de theme.C: bg side panel panel2 border fg muted accent teal green yellow red on_accent hover track.)
- No uses `setStyleSheet` con colores incrustados salvo que los leas de `theme.C` en el momento de crear el widget (al cambiar de modo las pantallas se vuelven a crear).
- Márgenes: la columna ya tiene márgenes; espacio entre tarjetas 12 px. Rejillas de tarjetas de 2–3 columnas.
- Anchura de la ventana: 980–1400 px. Evita anchos fijos grandes; deja que los textos largos hagan wrap (`Etiqueta` ya hace wrap).
- Textos de más de una línea: `Etiqueta(...)` con wrap. Los iconos son glifos Unicode sencillos (⚡ ✓ ✗ ⚠ ● ▶ ■ ↻), nada de emojis a color si se puede evitar.

## Patrones del Tk viejo → Qt
- `NeonButton(parent, "txt", cmd, color=CYAN, filled=True)` → `Boton("txt", cmd, kind="primary")`; sin `filled` → `kind="soft"`.
- `Card(parent, accent=GREEN, title=…)` → `Tarjeta(tone="green", titulo=…)`; contenido en `.lay`.
- `badge(parent, text, color)` → `Insignia(text, tone)`.
- `checkbox(parent, text, var)` → `Casilla(text)`.
- `ScrollFrame` → ya lo da `Pagina` (`self.col`).
- `WrapLabel` → `Etiqueta` (wrap por defecto).
- `app.bg/ui/toast/show` → `self.app.bg/ui/toast/ir`.
- `self.after(ms, fn)` → `self.app.after(ms, fn)`; bucles repetidos → `QTimer`.
- Canvas dibujado a mano → `QWidget` con `paintEvent` y `QPainter` (usa `theme.color(...)`), o los gráficos de `qtui/graficos.py`.
