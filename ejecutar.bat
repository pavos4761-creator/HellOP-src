@echo off
chcp 65001 >nul
cd /d "%~dp0"
where py >nul 2>nul && (set PY=py) || (set PY=python)
%PY% --version >nul 2>nul
if errorlevel 1 (
  echo No encuentro Python. Instalalo desde https://www.python.org/downloads/
  echo y marca la casilla "Add python.exe to PATH" durante la instalacion.
  pause
  exit /b 1
)
%PY% -m pip install -q -r requirements.txt
if errorlevel 1 (
  echo No pude instalar psutil. Comprueba tu conexion a Internet.
  pause
  exit /b 1
)
rem Abre la app como administrador (hace falta para servicios, energia y restauracion)
powershell -NoProfile -Command "Start-Process -Verb RunAs -WorkingDirectory '%~dp0' -FilePath '%PY%' -ArgumentList 'main.py'"
