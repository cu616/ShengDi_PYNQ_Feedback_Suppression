@echo off
setlocal
title a06 run record
set "SHENGDI_SSH_PASSWORD=xilinx"
set "PYTHONUTF8=1"
set "PYTHONIOENCODING=utf-8"
set "PY=C:\Users\lbc\AppData\Roaming\uv\python\cpython-3.12.14-windows-x86_64-none\python.exe"

if not exist "%PY%" (
  echo [ERROR] Python not found:
  echo         %PY%
  goto end
)

"%PY%" "%~dp0a06_live_run_monitor.py"
if errorlevel 1 echo [ERROR] monitor exited with code %errorlevel%

:end
echo.
echo ---------------------------------------------
echo  Monitor ended. Log: %~dp0a06_monitor_last_run.log
echo ---------------------------------------------
pause
endlocal
