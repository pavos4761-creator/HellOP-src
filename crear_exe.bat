@echo off
chcp 65001 >nul
cd /d "%~dp0"
where py >nul 2>nul && (set PY=py) || (set PY=python)
%PY% --version >nul 2>nul
if errorlevel 1 (
  echo No encuentro Python. Instalalo desde https://www.python.org/downloads/
  pause
  exit /b 1
)
%PY% -m pip install -q -r requirements.txt pyinstaller
%PY% -m PyInstaller --noconfirm --onefile --noconsole --uac-admin --name HellOP --icon assets\hellop.ico main.py
if errorlevel 1 (
  echo Algo fallo al crear el .exe.
  pause
  exit /b 1
)
echo.
echo Listo: dist\HellOP.exe  (pide permisos de administrador al abrirse)
pause
