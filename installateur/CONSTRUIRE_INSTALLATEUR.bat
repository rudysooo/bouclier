@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo === 1/3 Dependances de construction ===
py -3 -m pip install -r ..\requirements.txt pyinstaller pillow || goto :err
echo === 2/3 Application (PyInstaller) ===
py -3 make_wizard_images.py
cd ..
py -3 -m PyInstaller installateur\Bouclier.spec --noconfirm --distpath dist --workpath build || goto :err
cd installateur
echo === 3/3 Installateur (Inno Setup) ===
set "ISCC=%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe"
if not exist "%ISCC%" set "ISCC=%ProgramFiles%\Inno Setup 6\ISCC.exe"
if not exist "%ISCC%" set "ISCC=%ProgramFiles(x86)%\Inno Setup 7\ISCC.exe"
if not exist "%ISCC%" set "ISCC=%ProgramFiles%\Inno Setup 7\ISCC.exe"
if not exist "%ISCC%" (echo Inno Setup 6 ou 7 introuvable : voir jrsoftware.org & goto :err)
"%ISCC%" Bouclier_Setup.iss || goto :err
echo.
echo TERMINE : dist_installateur\Bouclier_Installer.exe
pause & exit /b 0
:err
echo ECHEC - voir les messages ci-dessus.
pause & exit /b 1
