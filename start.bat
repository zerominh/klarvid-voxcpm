@echo off
setlocal

cd /d "%~dp0"

where powershell.exe >nul 2>&1
if errorlevel 1 (
    echo [error] Khong tim thay powershell.exe.
    exit /b 1
)

powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\start.ps1" %*
set "START_EXIT_CODE=%ERRORLEVEL%"

if not "%START_EXIT_CODE%"=="0" (
    echo [error] start.ps1 ket thuc voi ma loi %START_EXIT_CODE%.
)

exit /b %START_EXIT_CODE%
