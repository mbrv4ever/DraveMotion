@echo off
chcp 65001 >nul
title DraveMotion - Stem herstellen
cd /d "%~dp0"

echo ============================================
echo    DraveMotion - Stem-engine herstellen
echo ============================================
echo.
echo Ik zoek een werkende versie van de stem-engine onnxruntime.
echo Dit kan een paar minuten duren; er wordt zo nodig met meerdere
echo versies getest. Even geduld.
echo.

if not exist ".venv\Scripts\python.exe" (
    echo [FOUT] De lokale omgeving .venv bestaat nog niet.
    echo Start eerst run.bat een keer, en draai daarna dit bestand.
    pause
    exit /b 1
)

for %%V in (1.19.2 1.18.1 1.18.0 1.17.3 1.16.3) do (
    echo --- Probeer onnxruntime %%V ...
    ".venv\Scripts\python.exe" -m pip install --upgrade --force-reinstall "onnxruntime==%%V" >nul 2>&1
    ".venv\Scripts\python.exe" -c "import onnxruntime" >nul 2>&1
    if not errorlevel 1 (
        echo.
        echo GELUKT met onnxruntime %%V.
        echo Sluit dit venster en start DraveMotion opnieuw; de stem werkt nu.
        echo.
        pause
        exit /b 0
    )
)

echo.
echo Geen van de geprobeerde versies werkte. Mogelijk ondersteunt je
echo processor de stem-engine niet, of er speelt iets anders.
echo Maak een schermfoto van dit venster, dan kijken we verder.
echo.
pause
