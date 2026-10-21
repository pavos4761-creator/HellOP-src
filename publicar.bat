@echo off
chcp 65001 >nul
rem Uso: publicar.bat 1.0.1   (sube los cambios y crea la versión; GitHub compila el .exe solo)
if "%1"=="" (echo Escribe la version, por ejemplo: publicar.bat 1.0.1 & exit /b 1)
powershell -NoProfile -Command "(Get-Content version.py) -replace '__version__ = \".*\"', '__version__ = \"%1\"' | Set-Content version.py"
git add -A
git commit -m "Version %1"
git push
git tag v%1
git push origin v%1
echo Listo. En unos minutos aparecera la version v%1 en GitHub (pestana Actions / Releases).
pause
