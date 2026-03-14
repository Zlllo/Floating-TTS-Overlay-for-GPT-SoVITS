@echo off
set "SCRIPT_DIR=%~dp0"
cd /d "%SCRIPT_DIR%"

echo Starting GPT-SoVITS API Backend...
:: Start the API in a new minimized window so it doesn't block this script
start /min "TTS-API-Backend" runtime\python.exe api_v2.py -a 127.0.0.1 -p 9880

echo.
echo Starting Floating TTS Overlay UI...
echo (Please wait a few seconds for the API to initialize in the background)
echo.
runtime\python.exe floating_tts.py

pause
