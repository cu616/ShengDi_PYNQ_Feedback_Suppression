set root [file normalize [file join [file dirname [info script]] ../..]]
create_project -force audio_replay_wide_test $root/build/work/audio_replay_wide_test -part xc7z020clg400-1
add_files [list $root/src/rtl/audio_pl_replay.v $root/src/rtl/feedback_fir.v $root/src/vendor/pynq_v2_4/iis_ser.vhd $root/src/vendor/pynq_v2_4/iis_deser.vhd]
add_files -fileset sim_1 $root/sim/audio/tb_replay_wide.v
set_property file_type SystemVerilog [get_files tb_replay_wide.v]
set_property top tb_replay_wide [get_filesets sim_1]
set_property xsim.simulate.runtime all [get_filesets sim_1]
launch_simulation
close_sim
set fh [open $root/build/work/audio_replay_wide_test/audio_replay_wide_test.sim/sim_1/behav/xsim/simulate.log r]
set result [read $fh]
close $fh
if {[string first "RESIDUAL_REPLAY_WIDE_PASS" $result] < 0 || [string first "Fatal:" $result] >= 0} {error "Wide residual replay simulation failed"}
close_project
exit
