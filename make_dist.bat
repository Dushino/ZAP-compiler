@echo off
pyinstaller -D -F --onefile -n zapc -c "compiler.py" || exit /b

rem Set ZAPC_INSTALL_DIR to override the default install location.
if "%ZAPC_INSTALL_DIR%"=="" set ZAPC_INSTALL_DIR=%USERPROFILE%\local\bin
if not exist "%ZAPC_INSTALL_DIR%" mkdir "%ZAPC_INSTALL_DIR%"
copy dist\zapc.exe "%ZAPC_INSTALL_DIR%\zapc.exe"
