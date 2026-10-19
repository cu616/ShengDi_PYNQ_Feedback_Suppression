set root [file normalize [file join [file dirname [info script]] ../..]]
open_project $root/build/work/audio_probe/audio_probe.xpr
if {[get_property PROGRESS [get_runs synth_1]] ne "100%"} {error "Run synthesis first"}
launch_runs impl_1 -to_step write_bitstream -jobs 2
wait_on_run impl_1
puts "IMPL_STATUS=[get_property STATUS [get_runs impl_1]]"
if {[get_property PROGRESS [get_runs impl_1]] ne "100%"} {error "Implementation did not complete"}
open_run impl_1
report_timing_summary -file $root/build/work/audio_probe/impl_timing.txt
report_utilization -file $root/build/work/audio_probe/impl_utilization.txt
report_drc -file $root/build/work/audio_probe/impl_drc.txt
puts "AUDIO_BITSTREAM_CREATED"
close_project
exit

