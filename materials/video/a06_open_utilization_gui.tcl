# a06 资源占用：打开【实装位流】对应实现并显示 Utilization 报告（Vivado 2018.3）
# 用法（Windows）：双击本文件无法直接运行，请在命令行执行：
#   D:\Xilinx\Vivado\2018.3\bin\vivado.bat -mode gui -source "D:\OCadence_Project\Flushbonading_FPGA_Contest\materials\video\a06_open_utilization_gui.tcl"
# 或先打开 Vivado，在 Tcl Console 里 source 本文件。

set dcp "D:/OCadence_Project/Flushbonading_FPGA_Contest/_a_work/wt-int/tmp/vivado/a06_deployed_routed.dcp"

puts "=== a06: opening deployed-bitstream routed checkpoint ==="
puts $dcp
open_checkpoint $dcp

# 显示资源占用报告（GUI 模式下会以报告视图打开）
report_utilization -name a06_utilization

puts "=== a06: utilization report opened ==="
puts "画面上应看到：Block RAM Tile 112 / 140 = 80.00%，DSPs 3，Slice LUTs 3587，Slice Registers 5030"
puts "如需放大字体：报告窗口内 Ctrl + 鼠标滚轮，或用 View 菜单缩放。"
