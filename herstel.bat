@echo off
chcp 65001 >nul
title DraveMotion - Herstel
cd /d "%~dp0"

echo ============================================
echo    DraveMotion - Herstel / opnieuw installeren
echo ============================================
echo.
echo Dit verwijdert de lokale installatie ^(.venv^) en zet hem schoon opnieuw op.
echo Je projecten in de map "projecten" blijven gewoon staan.
echo.
pause

if exist ".venv" (
    echo Oude installatie verwijderen...
    rmdir /s /q ".venv"
)

echo.
echo Klaar. Ik start run.bat nu opnieuw zodat alles vers wordt geinstalleerd.
echo.
call "%~dp0run.bat"
