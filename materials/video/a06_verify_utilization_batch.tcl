# a06 资源占用：批处理核对（无窗口，仅打印/写报告，用于提前确认数字）
set root "D:/OCadence_Project/Flushbonading_FPGA_Contest"
set dcp "$root/_a_work/wt-int/tmp/vivado/a06_deployed_routed.dcp"
set out "$root/_a_work/wt-int/tmp/vivado/a06_deployed_utilization_routed.rpt"

open_checkpoint $dcp
report_utilization -file $out
set fh [open "$root/_a_work/wt-int/tmp/vivado/a06_batch_result.txt" w]
puts $fh "DCP=$dcp"
puts $fh "RPT=$out"
close $fh
puts "A06_BATCH_DONE"
exit
