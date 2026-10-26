@echo off
chcp 65001 >nul
title DraveMotion - een Dravenlock product
cd /d "%~dp0"
set "LOG=%~dp0start-log.txt"

echo ============================================
echo    DraveMotion - een Dravenlock product
echo ============================================
echo.

> "%LOG%" echo DraveMotion start-log
>> "%LOG%" echo Datum: %date% %time%
>> "%LOG%" echo Map: %~dp0

REM --- Zoek een ONDERSTEUNDE Python (3.10 t/m 3.13; 3.14 is te nieuw) ----
set "PY="
for %%V in (3.13 3.12 3.11 3.10) do (
    if not defined PY (
        py -%%V --version >nul 2>&1 && set "PY=py -%%V"
    )
)

if not defined PY (
    echo [FOUT] Geen ondersteunde Python gevonden ^(nodig: 3.10 t/m 3.13^).
    echo.
    echo Je hebt waarschijnlijk alleen Python 3.14 - en dat is nog te nieuw
    echo voor de grafische bibliotheek PyQt5.
    echo.
    echo Installeer Python 3.13 ^(3.14 mag gewoon blijven staan^):
    echo    https://www.python.org/downloads/release/python-31313/
    echo Kies "Windows installer 64-bit" en vink "Add python.exe to PATH" aan.
    echo Start daarna run.bat opnieuw.
    >> "%LOG%" echo FOUT: geen ondersteunde Python 3.10-3.13 gevonden.
    echo.
    pause
    exit /b 1
)
echo Gebruikte Python: %PY%
>> "%LOG%" echo Python-commando: %PY%
%PY% --version >> "%LOG%" 2>&1

REM --- Oude/kapotte .venv (bv. met 3.14 gebouwd) opnieuw opbouwen --------
if exist ".venv\Scripts\python.exe" (
    ".venv\Scripts\python.exe" -c "import PyQt5" >nul 2>&1
    if errorlevel 1 (
        echo Oude installatie onbruikbaar - wordt schoon opnieuw opgebouwd...
        >> "%LOG%" echo --- oude .venv verwijderd - PyQt5 ontbrak ---
        rmdir /s /q ".venv"
    )
)

REM --- .venv aanmaken indien nodig ---------------------------------------
if not exist ".venv\Scripts\python.exe" (
    echo Eenmalige installatie ^(internet nodig, even geduld^)...
    >> "%LOG%" echo --- venv aanmaken ---
    %PY% -m venv ".venv" >> "%LOG%" 2>&1
    if errorlevel 1 (
        echo [FOUT] Kon de lokale omgeving .venv niet maken. Stuur start-log.txt.
        pause
        exit /b 1
    )
    >> "%LOG%" echo --- pip install ---
    ".venv\Scripts\python.exe" -m pip install --upgrade pip >> "%LOG%" 2>&1
    ".venv\Scripts\python.exe" -m pip install --only-binary=:all: -r requirements.txt >> "%LOG%" 2>&1
    if errorlevel 1 (
        echo [FOUT] Installatie van de pakketten mislukt. Stuur start-log.txt.
        pause
        exit /b 1
    )
)

REM --- Optioneel: stem (tekst-naar-spraak) eenmalig installeren ----------
".venv\Scripts\python.exe" -c "import importlib.util,sys; sys.exit(0 if importlib.util.find_spec('neuvoice') else 1)" >nul 2>&1
if errorlevel 1 (
    echo Stem ^(tekst-naar-spraak^) wordt eenmalig geinstalleerd ^(optioneel, internet nodig^)...
    >> "%LOG%" echo --- neuvoice install optioneel - mag mislukken ---
    ".venv\Scripts\python.exe" -m pip install neuvoice >> "%LOG%" 2>&1
)

REM --- Starten (eventuele crash gaat naar het log) ----------------------
echo DraveMotion wordt gestart...
>> "%LOG%" echo --- start app ---
".venv\Scripts\python.exe" dravemotion.py >> "%LOG%" 2>&1
if errorlevel 1 (
    echo.
    echo [FOUT] DraveMotion is met een fout gestopt. Stuur start-log.txt.
    pause
)
