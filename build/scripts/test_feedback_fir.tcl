set root [file normalize [file join [file dirname [info script]] ../..]]
create_project -force feedback_fir_test $root/build/work/feedback_fir_test -part xc7z020clg400-1
add_files $root/src/rtl/feedback_fir.v
add_files -fileset sim_1 $root/sim/audio/tb_feedback_fir.v
set_property file_type SystemVerilog [get_files tb_feedback_fir.v]
set_property top tb_feedback_fir [get_filesets sim_1]
set_property -name xsim.simulate.xsim.more_options -value "-testplusarg vectors=$root/tmp/fir_vectors" -objects [get_filesets sim_1]
set_property xsim.simulate.runtime all [get_filesets sim_1]
launch_simulation
close_sim
set fh [open $root/build/work/feedback_fir_test/feedback_fir_test.sim/sim_1/behav/xsim/simulate.log r]
set result [read $fh]
close $fh
if {[string first "FEEDBACK_FIR_PASS" $result] < 0 || [string first "Fatal:" $result] >= 0} {error "FIR simulation did not pass; inspect simulate.log"}
close_project
exit
