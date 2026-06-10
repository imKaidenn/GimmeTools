@echo off
REM ============================================================
REM   GimmeTools launcher  (PowerShell-free)
REM   Double-click to open the GimmeTools desktop UI.
REM ============================================================
setlocal EnableDelayedExpansion
cd /d "%~dp0"

set "VENV_PY=tools\venv\Scripts\python.exe"
set "VENV_PYW=tools\venv\Scripts\pythonw.exe"

REM ---- If the environment exists, skip straight to launch ----
if exist "%VENV_PY%" goto :launch

echo.
echo   First-time setup. Finding Python...

REM ---- 1) Look for Python on PATH (py launcher is most reliable) ----
set "BOOT="
for %%P in (py.exe python.exe python3.exe) do (
    if not defined BOOT (
        where %%P >nul 2>nul && set "BOOT=%%P"
    )
)

REM ---- 2) Fall back to common install locations ----
if not defined BOOT (
    for %%D in (
        "%LocalAppData%\Programs\Python\Python313\python.exe"
        "%LocalAppData%\Programs\Python\Python312\python.exe"
        "%LocalAppData%\Programs\Python\Python311\python.exe"
        "%LocalAppData%\Programs\Python\Python310\python.exe"
        "%ProgramFiles%\Python313\python.exe"
        "%ProgramFiles%\Python312\python.exe"
        "%ProgramFiles%\Python311\python.exe"
        "%ProgramFiles%\Python310\python.exe"
    ) do (
        if not defined BOOT if exist "%%~D" set "BOOT=%%~D"
    )
)

if not defined BOOT (
    echo.
    echo   Python was not found.
    echo   Install Python 3.10+ from https://www.python.org/downloads/
    echo   IMPORTANT: tick "Add Python to PATH" during install, then re-run this.
    echo.
    pause
    exit /b 1
)

echo   Using: !BOOT!
echo   Setting up GimmeTools (this can take a few minutes)...
echo.
"!BOOT!" "install\setup.py"

if not exist "%VENV_PY%" (
    echo.
    echo   Setup did not complete. See the messages above.
    pause
    exit /b 1
)

:launch
REM ---- Make sure the UI library is present ----
"%VENV_PY%" -c "import customtkinter" 2>nul
if errorlevel 1 (
    echo   Installing UI library (one time)...
    "%VENV_PY%" -m pip install --quiet customtkinter
)

REM ---- Open the app with no console window ----
start "" "%VENV_PYW%" "ui\gimmetools.py"
endlocal
