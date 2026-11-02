@echo off
setlocal
set "GAME_PYTHON=%~dp0..\.venv\Scripts\pythonw.exe"
if not exist "%GAME_PYTHON%" (
    echo Python environment missing. See game/README.md
    pause
    exit /b 1
)
start "" "%GAME_PYTHON%" "%~dp0main.py"
