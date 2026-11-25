@echo off
chcp 65001 >nul
cd /d "%~dp0"
title Installation de Bouclier

set "PY="
call :trouver "py -3"
if not defined PY call :trouver "python"
if not defined PY call :trouver "python3"
if not defined PY (
  echo [ERREUR] Python est introuvable ^(ou seul le faux "python" du Microsoft Store est present^).
  echo Installez Python depuis https://www.python.org/downloads/ en cochant "Add python.exe to PATH",
  echo puis relancez Installer.bat.
  pause
  exit /b 1
)

%PY% "%~dp0installer.py" %*
set "CODE=%ERRORLEVEL%"
echo.
if "%CODE%"=="0" (
  echo === Installation terminee. Double-cliquez sur "Bouclier" sur le Bureau. ===
) else (
  echo === Installation terminee avec des avertissements : lisez les lignes ci-dessus ^(journal : installation_log.txt^) ===
)
pause
exit /b %CODE%

:trouver
%~1 -c "import sys; sys.exit(0 if sys.version_info[0] == 3 else 1)" >nul 2>nul
if not errorlevel 1 set "PY=%~1"
exit /b 0
