@echo off
setlocal
title a06 vivado utilization
set "VIVADO=D:\Xilinx\Vivado\2018.3\bin\vivado.bat"
set "TCL=%~dp0a06_open_utilization_gui.tcl"
set "DCP=D:\OCadence_Project\Flushbonading_FPGA_Contest\_a_work\wt-int\tmp\vivado\a06_deployed_routed.dcp"

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

echo Starting Vivado 2018.3, please wait 1-2 minutes...
"%VIVADO%" -mode gui -source "%TCL%"

:end
echo.
echo ---------------------------------------------
echo  Vivado closed.
echo ---------------------------------------------
pause
endlocal
