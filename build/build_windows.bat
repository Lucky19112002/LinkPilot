@echo off
setlocal
cd /d "%~dp0\.."
set PYTHON=.venv\Scripts\python.exe
if not exist "%PYTHON%" set PYTHON=python
"%PYTHON%" -m pip install -r requirements.txt pyinstaller
"%PYTHON%" -m playwright install chromium
"%PYTHON%" -m PyInstaller build\linkpilot.spec --noconfirm
if exist dist\LinkPilot\LinkPilot.exe copy /Y dist\LinkPilot\LinkPilot.exe dist\LinkPilot.exe
if exist "%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe" "%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe" build\installer.iss
if exist "%ProgramFiles%\Inno Setup 6\ISCC.exe" "%ProgramFiles%\Inno Setup 6\ISCC.exe" build\installer.iss
if not exist dist\LinkPilot-Setup.exe exit /b 1
echo Built dist\LinkPilot.exe and dist\LinkPilot-Setup.exe when Inno Setup is installed
