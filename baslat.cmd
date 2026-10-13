@echo off
chcp 65001 >nul
title Jarvis Server
cd /d "%~dp0"

echo ============================================
echo    JARVIS baslatiliyor...
echo ============================================
echo.

where python >nul 2>nul
if errorlevel 1 (
  echo [HATA] Python bulunamadi. Once Python 3 kurun: https://www.python.org/downloads/
  echo.
  pause
  exit /b 1
)

echo Tarayici 3 saniye icinde otomatik acilacak (PC icin).
echo.
echo   PC  : http://localhost:8000
echo   Telefon: yukaridaki "Telefonda" adresi (ayni Wi-Fi)
echo.
echo Bu pencereyi KAPATMAYIN - sunucu burada calisir.
echo Kapatmak icin bu pencereyi kapatin.
echo.

start "" cmd /c "timeout /t 3 >nul & start "" http://localhost:8000"

python server.py

echo.
echo Sunucu durdu.
pause
