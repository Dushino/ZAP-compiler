@echo off
REM Install ZAP VSCode Extension
REM This script copies the extension to the VSCode extensions directory

echo Installing ZAP VSCode Extension...

powershell -ExecutionPolicy Bypass -File "%~dp0install_vscode_extension.ps1"

if %ERRORLEVEL% EQU 0 (
    echo.
    echo Press any key to exit...
    pause > nul
) else (
    echo.
    echo Installation failed!
    echo Press any key to exit...
    pause > nul
    exit /b 1
)
