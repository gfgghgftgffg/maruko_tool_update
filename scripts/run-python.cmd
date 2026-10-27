@echo off
setlocal
set "PYTHONUTF8=1"
if defined MARUKO_PYTHON (
    set "PYTHON=%MARUKO_PYTHON%"
) else if exist "%VIRTUAL_ENV%\Scripts\python.exe" (
    set "PYTHON=%VIRTUAL_ENV%\Scripts\python.exe"
) else if exist "%CONDA_PREFIX%\python.exe" (
    set "PYTHON=%CONDA_PREFIX%\python.exe"
) else if exist "%~dp0..\.venv\Scripts\python.exe" (
    set "PYTHON=%~dp0..\.venv\Scripts\python.exe"
) else if exist "%USERPROFILE%\.conda\envs\codex\python.exe" (
    set "PYTHON=%USERPROFILE%\.conda\envs\codex\python.exe"
) else (
    set "PYTHON=python"
)
"%PYTHON%" %*
exit /b %errorlevel%
