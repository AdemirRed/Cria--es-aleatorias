@echo off
title Provador de Unhas AR - servidor local
cd /d "%~dp0"

echo ============================================
echo   Provador de Unhas AR
echo   Subindo servidor local em http://localhost:8080
echo ============================================
echo.

REM Abre o navegador apos um instante
start "" cmd /c "timeout /t 2 >nul & start http://localhost:8080"

REM 1) Tenta Python (py launcher)
where py >nul 2>nul
if %errorlevel%==0 (
    py -m http.server 8080
    goto :eof
)

REM 2) Tenta python no PATH
where python >nul 2>nul
if %errorlevel%==0 (
    python -m http.server 8080
    goto :eof
)

REM 3) Tenta Node (npx serve)
where npx >nul 2>nul
if %errorlevel%==0 (
    npx --yes serve -l 8080
    goto :eof
)

echo.
echo [ERRO] Nao encontrei Python nem Node.js.
echo Instale um deles:
echo   Python: https://www.python.org/downloads/
echo   Node:   https://nodejs.org/
echo.
pause
