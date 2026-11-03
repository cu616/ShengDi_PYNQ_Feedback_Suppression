@echo off
rem a06 资源占用：一键打开【实装位流】对应的实现并显示利用率报告（Vivado 2018.3）
rem 双击本文件即可。请耐心等 1~2 分钟，Vivado 打开后会自动弹出 Utilization 报告。
setlocal
set VIVADO=D:\Xilinx\Vivado\2018.3\bin\vivado.bat
set TCL=%~dp0a06_open_utilization_gui.tcl
set DCP=D:\OCadence_Project\Flushbonading_FPGA_Contest\_a_work\wt-int\tmp\vivado\a06_deployed_routed.dcp

if not exist "%VIVADO%" (
  echo [ERROR] 未找到 Vivado 2018.3: %VIVADO%
  pause
  exit /b 1
)
if not exist "%DCP%" (
  echo [ERROR] 未找到实装实现的 checkpoint:
  echo         %DCP%
  echo         请先确认工程目录未被清理。
  pause
  exit /b 1
)
"%VIVADO%" -mode gui -source "%TCL%"
endlocal
