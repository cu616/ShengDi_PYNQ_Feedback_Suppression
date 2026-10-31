set root [file normalize [file join [file dirname [info script]] ../..]]
if {[version -short] ne "2018.3"} {error "Validated target: Vivado 2018.3"}
create_project -force audio_replay $root/build/work/audio_replay_sw -part xc7z020clg400-1
set_property board_part tul.com.tw:pynq-z2:part0:1.0 [current_project]
add_files [list $root/src/rtl/audio_pl_replay.v $root/src/rtl/feedback_fir.v $root/src/vendor/pynq_v2_4/iis_ser.vhd $root/src/vendor/pynq_v2_4/iis_deser.vhd]
add_files -fileset constrs_1 $root/build/scripts/audio_replay_sw.xdc
update_compile_order -fileset sources_1
create_bd_design system
create_bd_cell -type ip -vlnv xilinx.com:ip:processing_system7:5.5 ps7
apply_bd_automation -rule xilinx.com:bd_rule:processing_system7 -config {make_external "FIXED_IO, DDR" apply_board_preset "1" Master "Disable" Slave "Disable"} [get_bd_cells ps7]
set_property -dict [list CONFIG.PCW_USE_M_AXI_GP0 {1} CONFIG.PCW_EN_CLK0_PORT {1} CONFIG.PCW_FPGA0_PERIPHERAL_FREQMHZ {100} CONFIG.PCW_I2C1_PERIPHERAL_ENABLE {1} CONFIG.PCW_I2C1_I2C1_IO {EMIO}] [get_bd_cells ps7]
make_bd_intf_pins_external [get_bd_intf_pins ps7/IIC_1]
set_property name IIC_1 [get_bd_intf_ports IIC_1_0]
create_bd_cell -type ip -vlnv xilinx.com:ip:axi_gpio:2.0 audio_control
set_property -dict [list CONFIG.C_GPIO_WIDTH {32} CONFIG.C_ALL_OUTPUTS {1} CONFIG.C_DOUT_DEFAULT {0x00000000} CONFIG.C_IS_DUAL {1} CONFIG.C_GPIO2_WIDTH {32} CONFIG.C_ALL_INPUTS_2 {1}] [get_bd_cells audio_control]
apply_bd_automation -rule xilinx.com:bd_rule:axi4 -config {Master "/ps7/M_AXI_GP0" Clk_master "/ps7/FCLK_CLK0 (100 MHz)" Clk_slave "Auto" Clk_xbar "Auto"} [get_bd_intf_pins audio_control/S_AXI]
create_bd_cell -type module -reference audio_pl_replay audio_path
connect_bd_net [get_bd_pins ps7/FCLK_CLK0] [get_bd_pins audio_path/clk]
connect_bd_net [get_bd_pins audio_control/s_axi_aresetn] [get_bd_pins audio_path/resetn]
connect_bd_net [get_bd_pins audio_control/gpio_io_o] [get_bd_pins audio_path/control]
connect_bd_net [get_bd_pins audio_path/frame_count] [get_bd_pins audio_control/gpio2_io_i]
create_bd_cell -type ip -vlnv xilinx.com:ip:axi_gpio:2.0 audio_samples
set_property -dict [list CONFIG.C_GPIO_WIDTH {24} CONFIG.C_ALL_INPUTS {1} CONFIG.C_IS_DUAL {1} CONFIG.C_GPIO2_WIDTH {24} CONFIG.C_ALL_INPUTS_2 {1}] [get_bd_cells audio_samples]
apply_bd_automation -rule xilinx.com:bd_rule:axi4 -config {Master "/ps7/M_AXI_GP0" Clk_master "/ps7/FCLK_CLK0 (100 MHz)" Clk_slave "Auto" Clk_xbar "Auto"} [get_bd_intf_pins audio_samples/S_AXI]
connect_bd_net [get_bd_pins audio_path/capture_left] [get_bd_pins audio_samples/gpio_io_i]
connect_bd_net [get_bd_pins audio_path/capture_right] [get_bd_pins audio_samples/gpio2_io_i]
create_bd_cell -type ip -vlnv xilinx.com:ip:axi_gpio:2.0 audio_calibrate_cmd
set_property -dict [list CONFIG.C_GPIO_WIDTH {32} CONFIG.C_ALL_OUTPUTS {1} CONFIG.C_DOUT_DEFAULT {0x00000000} CONFIG.C_IS_DUAL {1} CONFIG.C_GPIO2_WIDTH {32} CONFIG.C_ALL_INPUTS_2 {1}] [get_bd_cells audio_calibrate_cmd]
apply_bd_automation -rule xilinx.com:bd_rule:axi4 -config {Master "/ps7/M_AXI_GP0" Clk_master "/ps7/FCLK_CLK0 (100 MHz)" Clk_slave "Auto" Clk_xbar "Auto"} [get_bd_intf_pins audio_calibrate_cmd/S_AXI]
connect_bd_net [get_bd_pins audio_calibrate_cmd/gpio_io_o] [get_bd_pins audio_path/capture_cmd]
connect_bd_net [get_bd_pins audio_path/capture_status] [get_bd_pins audio_calibrate_cmd/gpio2_io_i]
create_bd_cell -type ip -vlnv xilinx.com:ip:axi_gpio:2.0 audio_coefficients
set_property -dict [list CONFIG.C_GPIO_WIDTH {32} CONFIG.C_ALL_OUTPUTS {1} CONFIG.C_DOUT_DEFAULT {0x00000000} CONFIG.C_IS_DUAL {1} CONFIG.C_GPIO2_WIDTH {32} CONFIG.C_ALL_INPUTS_2 {1}] [get_bd_cells audio_coefficients]
apply_bd_automation -rule xilinx.com:bd_rule:axi4 -config {Master "/ps7/M_AXI_GP0" Clk_master "/ps7/FCLK_CLK0 (100 MHz)" Clk_slave "Auto" Clk_xbar "Auto"} [get_bd_intf_pins audio_coefficients/S_AXI]
connect_bd_net [get_bd_pins audio_coefficients/gpio_io_o] [get_bd_pins audio_path/coefficient_cmd]
connect_bd_net [get_bd_pins audio_path/coefficient_status] [get_bd_pins audio_coefficients/gpio2_io_i]
create_bd_cell -type ip -vlnv xilinx.com:ip:axi_gpio:2.0 audio_runtime
set_property -dict [list CONFIG.C_GPIO_WIDTH {32} CONFIG.C_ALL_OUTPUTS {1} CONFIG.C_DOUT_DEFAULT {0x00000000} CONFIG.C_IS_DUAL {1} CONFIG.C_GPIO2_WIDTH {32} CONFIG.C_ALL_INPUTS_2 {1}] [get_bd_cells audio_runtime]
apply_bd_automation -rule xilinx.com:bd_rule:axi4 -config {Master "/ps7/M_AXI_GP0" Clk_master "/ps7/FCLK_CLK0 (100 MHz)" Clk_slave "Auto" Clk_xbar "Auto"} [get_bd_intf_pins audio_runtime/S_AXI]
connect_bd_net [get_bd_pins audio_runtime/gpio_io_o] [get_bd_pins audio_path/frame_limit]
connect_bd_net [get_bd_pins audio_path/completed_count] [get_bd_pins audio_runtime/gpio2_io_i]
create_bd_cell -type ip -vlnv xilinx.com:ip:axi_gpio:2.0 audio_clips
set_property -dict [list CONFIG.C_GPIO_WIDTH {32} CONFIG.C_ALL_INPUTS {1} CONFIG.C_IS_DUAL {1} CONFIG.C_GPIO2_WIDTH {32} CONFIG.C_ALL_INPUTS_2 {1}] [get_bd_cells audio_clips]
apply_bd_automation -rule xilinx.com:bd_rule:axi4 -config {Master "/ps7/M_AXI_GP0" Clk_master "/ps7/FCLK_CLK0 (100 MHz)" Clk_slave "Auto" Clk_xbar "Auto"} [get_bd_intf_pins audio_clips/S_AXI]
connect_bd_net [get_bd_pins audio_path/saturation_counts] [get_bd_pins audio_clips/gpio_io_i]
connect_bd_net [get_bd_pins audio_path/gain_clip_count] [get_bd_pins audio_clips/gpio2_io_i]

foreach {name width out_pin in_pin} {
    audio_source 32 source_cmd source_status
    audio_source_length 32 source_length mix_clip_count
} {
    create_bd_cell -type ip -vlnv xilinx.com:ip:axi_gpio:2.0 $name
    set_property -dict [list CONFIG.C_GPIO_WIDTH $width CONFIG.C_ALL_OUTPUTS {1} CONFIG.C_DOUT_DEFAULT {0x00000000} CONFIG.C_IS_DUAL {1} CONFIG.C_GPIO2_WIDTH {32} CONFIG.C_ALL_INPUTS_2 {1}] [get_bd_cells $name]
    apply_bd_automation -rule xilinx.com:bd_rule:axi4 -config {Master "/ps7/M_AXI_GP0" Clk_master "/ps7/FCLK_CLK0 (100 MHz)" Clk_slave "Auto" Clk_xbar "Auto"} [get_bd_intf_pins $name/S_AXI]
    connect_bd_net [get_bd_pins $name/gpio_io_o] [get_bd_pins audio_path/$out_pin]
    connect_bd_net [get_bd_pins audio_path/$in_pin] [get_bd_pins $name/gpio2_io_i]
}
foreach p {sdata_i sdata_o bclk lrclk sw_bypass} {
    make_bd_pins_external [get_bd_pins audio_path/$p]
    set_property name $p [get_bd_ports ${p}_0]
}
create_bd_cell -type ip -vlnv xilinx.com:ip:clk_wiz:6.0 audio_mclk
set_property -dict [list CONFIG.PRIM_IN_FREQ {100.000} CONFIG.CLKOUT1_REQUESTED_OUT_FREQ {10.000} CONFIG.RESET_TYPE {ACTIVE_LOW} CONFIG.RESET_PORT {resetn}] [get_bd_cells audio_mclk]
connect_bd_net [get_bd_pins ps7/FCLK_CLK0] [get_bd_pins audio_mclk/clk_in1]
connect_bd_net [get_bd_pins audio_control/s_axi_aresetn] [get_bd_pins audio_mclk/resetn]
make_bd_pins_external [get_bd_pins audio_mclk/clk_out1]
set_property name audio_clk_10MHz [get_bd_ports clk_out1_0]
create_bd_cell -type ip -vlnv xilinx.com:ip:xlconstant:1.1 codec_address
set_property -dict [list CONFIG.CONST_WIDTH {2} CONFIG.CONST_VAL {3}] [get_bd_cells codec_address]
make_bd_pins_external [get_bd_pins codec_address/dout]
set_property name codec_addr [get_bd_ports dout_0]
assign_bd_address
validate_bd_design
save_bd_design
generate_target all [get_files system.bd]
make_wrapper -files [get_files system.bd] -top
add_files $root/build/work/audio_replay_sw/audio_replay.srcs/sources_1/bd/system/hdl/system_wrapper.v
set_property top system_wrapper [current_fileset]
update_compile_order -fileset sources_1
report_ip_status -file $root/build/work/audio_replay_sw/ip_status.txt
puts "AUDIO_SW_PROJECT_CREATED"
if {$argc > 0 && [lindex $argv 0] eq "build"} {
    launch_runs synth_1 -jobs 2
    wait_on_run synth_1
    if {[get_property PROGRESS [get_runs synth_1]] ne "100%"} {error "Synthesis failed"}
    launch_runs impl_1 -to_step write_bitstream -jobs 2
    wait_on_run impl_1
    if {[get_property PROGRESS [get_runs impl_1]] ne "100%"} {error "Implementation failed"}
    open_run impl_1
    report_timing_summary -file $root/build/work/audio_replay_sw/timing.txt
    report_utilization -file $root/build/work/audio_replay_sw/utilization.txt
    report_drc -file $root/build/work/audio_replay_sw/drc.txt
    if {[get_property SLACK [get_timing_paths -delay_type max -max_paths 1]] < 0} {error "Replay setup timing failed"}
    if {[get_property SLACK [get_timing_paths -delay_type min -max_paths 1]] < 0} {error "Replay hold timing failed"}
    puts "AUDIO_SW_BITSTREAM_CREATED"
}
close_project
exit




