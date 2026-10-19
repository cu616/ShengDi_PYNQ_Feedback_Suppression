set root [file normalize [file join [file dirname [info script]] ../..]]
open_project $root/build/work/audio_bringup/audio_bringup.xpr
open_run impl_1
puts "AUDIO_PORTS=[get_ports {bclk lrclk sdata_i sdata_o audio_clk_10MHz}]"
puts "AUDIO_CLOCKS=[get_clocks]"
puts "BCLK_PORT_CLOCKS=[get_clocks -of_objects [get_ports bclk]]"
puts "BCLK_DIVIDER_PINS=[get_pins -hier -filter {NAME =~ *divider_reg*} -quiet]"
puts "AUDIO_PATH_CLK_PINS=[get_pins -hier -filter {NAME =~ *audio_path*clk*} -quiet]"
puts "AUDIO_TIMING_INSPECTED"
close_project
exit
