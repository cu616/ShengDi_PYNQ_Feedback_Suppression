# Exploratory, in-memory timing model only. It does not alter the implemented bitstream.
# Codec numbers: ADAU1761 Rev. F Table 7. Board trace skew is not yet included.
set root [file normalize [file join [file dirname [info script]] ../..]]
open_project $root/build/work/audio_bringup/audio_bringup.xpr
open_run impl_1

set bclk_source [get_pins {system_i/audio_path/inst/divider_reg[4]/C}]
set lrclk_source [get_pins {system_i/audio_path/inst/divider_reg[10]/C}]
if {[llength $bclk_source] != 1 || [llength $lrclk_source] != 1} {
    error "Divider source pin not unique"
}
create_generated_clock -name audio_bclk -source $bclk_source -divide_by 32 -invert [get_ports bclk]
create_generated_clock -name audio_lrclk -source $lrclk_source -divide_by 2048 -invert [get_ports lrclk]

# ADC_SDATA is valid no later than 50 ns after BCLK falling (full IOVDD range).
# A 0 ns earliest change is conservative because no minimum is specified.
set_input_delay -clock [get_clocks audio_bclk] -clock_fall -max 50 [get_ports sdata_i]
set_input_delay -clock [get_clocks audio_bclk] -clock_fall -min 0 [get_ports sdata_i]

# Codec requires LRCLK and DAC_SDATA stable 5 ns before/after BCLK rising.
# These 5 ns values exclude PCB skew; therefore this is not sign-off.
set_output_delay -clock [get_clocks audio_bclk] -max 5 [get_ports {lrclk sdata_o}]
set_output_delay -clock [get_clocks audio_bclk] -min -5 [get_ports {lrclk sdata_o}]

puts "BCLK_CLOCK=[get_clocks -of_objects [get_ports bclk]]"
puts "LRCLK_CLOCK=[get_clocks -of_objects [get_ports lrclk]]"
check_timing -verbose -file $root/report/verification/audio_bringup/io_probe_check_timing.txt
report_timing_summary -file $root/report/verification/audio_bringup/io_probe_timing.txt
puts "AUDIO_IO_TIMING_PROBED"
close_project
exit
