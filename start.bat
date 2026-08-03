@echo off
REM JARVIS Windows v2.1 - Quick Start
REM If setup has been run, starts directly. Run: start.bat

setlocal

if not exist "venv\Scripts\activate.bat" (
    echo ERROR: venv not found. Run setup.bat first.
    pause
    exit /b 1
)

call venv\Scripts\activate.bat
python main.py

endlocal