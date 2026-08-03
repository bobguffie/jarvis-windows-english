@echo off
REM JARVIS Windows v2.1 - Setup & Launch Script
REM Run: setup.bat

setlocal enabledelayedexpansion

echo.
echo ========================================
echo    J.A.R.V.I.S  Windows v2.1 Setup
echo ========================================
echo.

REM Python check
where python >nul 2>nul
if errorlevel 1 (
    echo ERROR: Python not found. Install Python 3.10+ from https://www.python.org/downloads/windows/
    pause
    exit /b 1
)

for /f "tokens=*" %%v in ('python --version') do set "PYVERSION=%%v"
echo Python: %PYVERSION%

REM Virtual environment
if not exist "venv\" (
    echo Creating virtual environment...
    python -m venv venv
)

call venv\Scripts\activate.bat

REM API key file
if not exist "config\api_keys.json" (
    if exist "config\api_keys.example.json" (
        copy /Y "config\api_keys.example.json" "config\api_keys.json" >nul
        echo config\api_keys.json created - Enter your Gemini API key here.
    )
)

REM Copy fonts to user directory
if exist "Fonts\" (
    echo Installing Grift fonts...
    powershell -NoProfile -Command "$d = Join-Path $env:LOCALAPPDATA 'Microsoft\Windows\Fonts'; New-Item -ItemType Directory -Force -Path $d | Out-Null; Get-ChildItem -Path '.\Fonts\*.ttf' | ForEach-Object { $t = Join-Path $d $_.Name; if (-not (Test-Path $t)) { Copy-Item $_.FullName $t -Force } }"
)

echo.
echo Installing packages...
python -m pip install --upgrade pip
python -m pip install -r requirements.txt

echo.
echo If PyAudio fails to install: pip install pipwin && pipwin install pyaudio
echo.
echo ========================================
echo        Setup Complete
echo ========================================
echo.
echo To start JARVIS:
echo    venv\Scripts\activate
echo    python main.py
echo.

set /p choice="Start now? (y/n): "
if /i "!choice!"=="y" (
    python main.py
)

endlocal