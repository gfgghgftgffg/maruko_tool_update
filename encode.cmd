@echo off
chcp 65001 >nul
if "%~1"=="" (
    call "%~dp0scripts\run-python.cmd" "%~dp0gui.py"
) else (
    call "%~dp0scripts\run-python.cmd" "%~dp0encode.py" %*
)
exit /b %errorlevel%
