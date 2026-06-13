@echo off
title Sistema de Seguranca Facial que Aprende
cd /d "%~dp0"

echo ============================================
echo   Sistema de Seguranca Facial que Aprende
echo   Instalando/conferindo dependencias...
echo ============================================
echo.

pip install -r requirements.txt

echo.
echo ============================================
echo   Iniciando...
echo   (Na 1a vez vai pedir o CADASTRO do rosto)
echo.
echo   Saidas de emergencia (sempre funcionam):
echo     Ctrl+Alt+Home  = destravar agora
echo     Ctrl+Alt+P     = pausar
echo     Ctrl+Alt+End   = desativar tudo
echo     Ctrl+Alt+Q     = sair
echo   ...ou digite sua senha de emergencia.
echo ============================================
echo.

python main.py

echo.
pause
