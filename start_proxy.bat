@echo off
title Gemini Key Rotation Proxy
echo ============================================================
echo    Gemini Key Rotation Proxy - Nanobot
echo ============================================================
echo.
echo Iniciando proxy en http://localhost:19090 ...
echo Presiona Ctrl+C para detener.
echo.
python "%~dp0gemini_proxy.py"
pause
