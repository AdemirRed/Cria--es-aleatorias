@echo off
title Controle do PC por Gestos
cd /d "%~dp0"

echo ============================================
echo   Controle do PC por Gestos
echo   Instalando dependencias...
echo ============================================
echo.

REM Instala dependencias
pip install -r requirements.txt

echo.
echo ============================================
echo   Iniciando o programa...
echo   Pressione Q ou ESC na janela para sair
echo ============================================
echo.

python gestos.py

echo.
pause
