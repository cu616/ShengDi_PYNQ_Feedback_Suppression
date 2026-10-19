set root [file normalize [file join [file dirname [info script]] ../..]]
create_project -force audio_closed_test $root/build/work/audio_closed_test -part xc7z020clg400-1
add_files [list $root/src/rtl/audio_pl_closed.v $root/src/rtl/feedback_fir.v $root/src/vendor/pynq_v2_4/iis_ser.vhd $root/src/vendor/pynq_v2_4/iis_deser.vhd]
add_files -fileset sim_1 $root/sim/audio/tb_audio_closed.v
set_property file_type SystemVerilog [get_files tb_audio_closed.v]
set_property top tb_audio_closed [get_filesets sim_1]
set_property xsim.simulate.runtime all [get_filesets sim_1]
launch_simulation
close_sim
set fh [open $root/build/work/audio_closed_test/audio_closed_test.sim/sim_1/behav/xsim/simulate.log r]
set result [read $fh]
close $fh
if {[string first "AUDIO_CLOSED_PASS" $result] < 0 || [string first "Fatal:" $result] >= 0} {error "Closed integration simulation failed"}
close_project
exit
