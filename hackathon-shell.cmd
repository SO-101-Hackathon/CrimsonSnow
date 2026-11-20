@echo off
rem ---------------------------------------------------------------------------
rem  Double-click me (or run .\hackathon-shell.cmd from any terminal).
rem  Opens a terminal in this folder with the `lerobot` environment active, so
rem  `so ...`, `lerobot-...` and `hf ...` commands just work.
rem  Needs no PowerShell execution-policy change and no `conda init`.
rem
rem    hackathon-shell.cmd          new interactive shell (double-click)
rem    hackathon-shell.cmd --here   activate inside the calling cmd.exe (VS Code profile)
rem ---------------------------------------------------------------------------
set "SO_ROOT=%~dp0"
set "CONDA_ACT="
for %%B in ("%USERPROFILE%\miniforge3" "%LOCALAPPDATA%\miniforge3" "%USERPROFILE%\miniconda3" "C:\ProgramData\miniforge3") do (
    if not defined CONDA_ACT if exist "%%~B\Scripts\activate.bat" set "CONDA_ACT=%%~B\Scripts\activate.bat"
)
if not defined CONDA_ACT (
    echo Miniforge not found. Install it first - see README.md, section Setup.
    pause
    exit /b 1
)
set "PYTHONUTF8=1"
set "HF_HUB_DISABLE_SYMLINKS_WARNING=1"

if /i "%~1"=="--here" goto :here
cmd /k "call "%~f0" --here"
exit /b 0

:here
call "%CONDA_ACT%" lerobot
if errorlevel 1 (
    echo Could not activate the 'lerobot' environment. See README.md, section Setup.
    exit /b 1
)
cd /d "%SO_ROOT%"
title SO-101 hackathon
echo.
echo   Environment: lerobot     Folder: %SO_ROOT%
echo   Try:   so doctor     so --help     so show
echo.
