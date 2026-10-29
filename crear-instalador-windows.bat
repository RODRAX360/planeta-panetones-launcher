@echo off
setlocal
cd /d "%~dp0"
if "%~1"=="" (
  echo Uso: crear-instalador-windows.bat URL_MANIFIESTOS URL_RELEASE_INSTALADOR
  exit /b 2
)
if "%~2"=="" (
  echo Falta la URL de la Release del instalador.
  exit /b 2
)
py -3 -m pip install -r requirements.txt pyinstaller pillow
if errorlevel 1 exit /b 1
py -3 build_release_windows.py --base-url "%~1" --installer-base-url "%~2"
if errorlevel 1 exit /b 1
echo.
echo El instalador y launcher-update.json estan en la carpeta dist.
