@echo off
setlocal
title a06 vivado utilization
set "VIVADO=D:\Xilinx\Vivado\2018.3\bin\vivado.bat"
set "TCL=%~dp0a06_open_utilization_gui.tcl"
set "DCP=D:\OCadence_Project\Flushbonading_FPGA_Contest\_a_work\wt-int\tmp\vivado\a06_deployed_routed.dcp"

rem Report text is small on 1080p; make the whole Vivado UI 1.5x.
rem If it is too large, change 1.5 to 1.25; if still small, use 1.75/2.0.
set "QT_SCALE_FACTOR=1.5"

if not exist "%VIVADO%" (
  echo [ERROR] Vivado 2018.3 not found:
  echo         %VIVADO%
  goto end
)
if not exist "%TCL%" (
  echo [ERROR] Tcl script not found:
  echo         %TCL%
  goto end
)
if not exist "%DCP%" (
  echo [ERROR] Routed checkpoint not found:
  echo         %DCP%
  goto end
)

echo Starting Vivado 2018.3 (UI scale 1.5x), please wait 1-2 minutes...
"%VIVADO%" -mode gui -source "%TCL%"

:end
echo.
echo ---------------------------------------------
echo  Vivado closed.
echo ---------------------------------------------
pause
endlocal
