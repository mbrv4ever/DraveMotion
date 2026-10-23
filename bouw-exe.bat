@echo off
chcp 65001 >nul
title DraveMotion - .exe bouwen (alles in een)
echo ============================================
echo    DraveMotion - een zelfstandige .exe bouwen
echo    (alles erin, ook ffmpeg - geen losse bestanden)
echo ============================================
echo.
cd /d "%~dp0"

rem --- Zoek een Python met PyQt5-wheels (3.13..3.10). 3.14 is nu nog te nieuw. ---
set "PY="
for %%V in (3.13 3.12 3.11 3.10) do (
    if not defined PY ( py -%%V -c "import sys" >nul 2>&1 && set "PY=py -%%V" )
)
if not defined PY ( where python >nul 2>&1 && set "PY=python" )
if not defined PY (
    echo [FOUT] Geen geschikte Python gevonden.
    echo   Installeer Python 3.12 van https://www.python.org/downloads/
    echo   ^(PyQt5 heeft nog geen versie voor Python 3.14^)
    pause & exit /b 1
)
echo Gekozen Python: %PY%

rem --- Ruim een oude/kapotte bouw-omgeving op (bv. van een mislukte 3.14-poging) ---
if exist ".build-venv\Scripts\python.exe" ( ".build-venv\Scripts\python.exe" -c "import PyQt5" >nul 2>&1 || ( echo Oude bouw-omgeving opruimen... & rmdir /s /q .build-venv 2>nul ) )

if not exist ".build-venv\Scripts\python.exe" ( echo [1/3] Bouw-omgeving aanmaken... & %PY% -m venv .build-venv )
set "VPY=.build-venv\Scripts\python.exe"

echo [2/3] Benodigdheden installeren (eerste keer duurt even)...
"%VPY%" -m pip install --upgrade pip >nul
"%VPY%" -m pip install --only-binary=:all: pyinstaller PyQt5 numpy imageio-ffmpeg soundfile opencv-python-headless Pillow
if errorlevel 1 (
    echo.
    echo [FOUT] Installeren mislukt.
    echo   Je Python is waarschijnlijk te nieuw voor PyQt5 ^(bv. 3.14^).
    echo   Installeer Python 3.12 van https://www.python.org/downloads/
    echo   en start dit bestand opnieuw. ^(De bouw-omgeving is opgeruimd.^)
    rmdir /s /q .build-venv 2>nul
    pause & exit /b 1
)
echo [3/3] Een zelfstandige .exe bouwen (ffmpeg zit erin)...
"%VPY%" -m PyInstaller --noconfirm dravemotion.spec
if errorlevel 1 ( echo [FOUT] Bouwen mislukt. & pause & exit /b 1 )

echo.
echo KLAAR! Een enkel bestand, alles erin:
echo     dist\DraveMotion.exe
echo Config/projecten/cache maakt de app zelf aan naast de .exe.
echo.
pause
