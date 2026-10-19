set root [file normalize [file join [file dirname [info script]] ../..]]
set out $root/report/verification/feedback_fir
file mkdir $out
read_verilog $root/src/rtl/feedback_fir.v
synth_design -top feedback_fir -part xc7z020clg400-1 -mode out_of_context
create_clock -name core_clk -period 10 [get_ports clk]
opt_design
place_design
route_design
report_timing_summary -file $out/core-timing.txt
report_utilization -file $out/core-utilization.txt
report_drc -file $out/core-drc.txt
set path [get_timing_paths -delay_type max -max_paths 1]
if {[llength $path]==0} {error "No timed core path"}
set slack [get_property SLACK $path]
puts "FIR_CORE_ROUTED_WNS $slack"
if {$slack < 0} {error "100MHz core timing not met"}
exit
