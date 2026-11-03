@echo off
setlocal
set "GAME_PYTHON=%~dp0..\.venv\Scripts\pythonw.exe"
set "ARCHIVED_GAME=%~dp02026-11-03-before-restart\game\main.py"
if not exist "%GAME_PYTHON%" (
    echo Python environment missing. See game/README.md in the project root.
    pause
    exit /b 1
)
if not exist "%ARCHIVED_GAME%" (
    echo Archived prototype missing. See archive/README.md.
    pause
    exit /b 1
)
start "" "%GAME_PYTHON%" "%ARCHIVED_GAME%"
