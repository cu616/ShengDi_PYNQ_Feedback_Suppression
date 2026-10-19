set root [file normalize [file join [file dirname [info script]] ../..]]
create_project -force diag_test $root/build/work/diag_test -part xc7z020clg400-1
add_files [list $root/src/rtl/audio_frame_path.v $root/src/rtl/audio_pl_diag.v $root/src/vendor/pynq_v2_4/iis_ser.vhd $root/src/vendor/pynq_v2_4/iis_deser.vhd]
add_files -fileset sim_1 $root/sim/audio/tb_audio_diag.v
set_property file_type SystemVerilog [get_files tb_audio_diag.v]
set_property top tb_audio_diag [get_filesets sim_1]
set_property xsim.simulate.runtime all [get_filesets sim_1]
launch_simulation
close_sim
close_project
exit

