@echo off
setlocal EnableExtensions DisableDelayedExpansion
chcp 65001 >nul
title MoniK Proven Cloud Multi Identity LAN

cd /d "%~dp0"

where py >nul 2>nul
if not errorlevel 1 (
    py -3 "MONIK_V6_PROVEN_CLOUD_MULTI_IDENTITY_LAN.py"
) else (
    python "MONIK_V6_PROVEN_CLOUD_MULTI_IDENTITY_LAN.py"
)

if errorlevel 1 (
    echo.
    echo [MONIK] The script ended with an error.
)

echo.
echo Press any key to close
pause >nul
endlocal
