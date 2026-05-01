@echo off
REM Signal Scout 4.0 — Dashboard Launcher
REM The '&' in the parent folder name breaks Turbopack (next dev).
REM This script uses 'next build + next start' (production mode) instead.

cd /d "%~dp0"

REM Get short path to avoid '&' character issues
for %%I in ("%cd%") do set "SHORT_PATH=%%~sI"
cd /d "%SHORT_PATH%"

echo.
echo  Signal Scout 4.0 — Dashboard
echo  =============================
echo.

echo  Building dashboard...
call npx next build
if errorlevel 1 (
    echo  Build failed!
    pause
    exit /b 1
)

echo.
echo  Starting server at http://localhost:3000
echo  Press Ctrl+C to stop.
echo.
npx next start
