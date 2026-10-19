set root [file normalize [file join [file dirname [info script]] ../..]]
open_project $root/build/work/audio_diag/audio_diag.xpr
launch_runs synth_1 -jobs 2
wait_on_run synth_1
puts "SYNTH_STATUS=[get_property STATUS [get_runs synth_1]]"
if {[get_property PROGRESS [get_runs synth_1]] ne "100%"} {error "Synthesis did not complete"}
open_run synth_1
report_utilization -file $root/build/work/audio_diag/synth_utilization.txt
report_timing_summary -file $root/build/work/audio_diag/synth_timing.txt
puts "AUDIO_SYNTH_COMPLETE"
close_project
exit

