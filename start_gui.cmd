@echo off
chcp 65001 >nul
call "%~dp0scripts\run-python.cmd" "%~dp0gui.py" %*
if errorlevel 1 pause
