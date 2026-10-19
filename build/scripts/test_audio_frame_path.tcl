set root [file normalize [file join [file dirname [info script]] ../..]]
create_project -force frame_test $root/build/work/frame_test -part xc7z020clg400-1
add_files $root/src/rtl/audio_frame_path.v
add_files -fileset sim_1 $root/sim/audio/tb_audio_frame_path.v
set_property file_type SystemVerilog [get_files tb_audio_frame_path.v]
set_property top tb_audio_frame_path [get_filesets sim_1]
set_property xsim.simulate.runtime all [get_filesets sim_1]
launch_simulation
close_sim
close_project
exit
