@echo off
rem a06 素材①：真实运行记录实时监视（只读，不操作硬件）
rem 双击运行。窗口打开后按提示操作板子，记录会自动刷新；结束时给出完整运行记录。
title a06 run record
chcp 65001 >nul
setlocal
set SHENGDI_SSH_PASSWORD=xilinx
set PYTHONIOENCODING=utf-8
set PYTHONUTF8=1
set PY=C:\Users\lbc\AppData\Roaming\uv\python\cpython-3.12.14-windows-x86_64-none\python.exe
"%PY%" "%~dp0a06_live_run_monitor.py"
echo.
echo 监视已结束。关闭本窗口即可。
pause
endlocal
