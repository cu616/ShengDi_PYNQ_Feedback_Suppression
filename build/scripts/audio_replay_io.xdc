# Pin mapping from Xilinx/PYNQ v2.4 boards/Pynq-Z2/base/vivado/constraints/base.xdc.
set_property -dict {PACKAGE_PIN U9 IOSTANDARD LVCMOS33 PULLUP true} [get_ports IIC_1_scl_io]
set_property -dict {PACKAGE_PIN T9 IOSTANDARD LVCMOS33 PULLUP true} [get_ports IIC_1_sda_io]
set_property -dict {PACKAGE_PIN U5 IOSTANDARD LVCMOS33} [get_ports audio_clk_10MHz]
set_property -dict {PACKAGE_PIN R18 IOSTANDARD LVCMOS33} [get_ports bclk]
set_property -dict {PACKAGE_PIN T17 IOSTANDARD LVCMOS33} [get_ports lrclk]
set_property -dict {PACKAGE_PIN G18 IOSTANDARD LVCMOS33} [get_ports sdata_o]
set_property -dict {PACKAGE_PIN F17 IOSTANDARD LVCMOS33} [get_ports sdata_i]
set_property -dict {PACKAGE_PIN M17 IOSTANDARD LVCMOS33} [get_ports {codec_addr[0]}]
set_property -dict {PACKAGE_PIN M18 IOSTANDARD LVCMOS33} [get_ports {codec_addr[1]}]
# External audio timing constraints remain to be derived from codec specification.
# Do not waive unconstrained I/O warnings or claim timing sign-off from WNS alone.

# PYNQ-Z2 SW0 (M20) and SW1 (M19): physical algorithm switches; either one high forces bypass.
# No internal pull is set: the board has its own switch resistors and the vendor base.xdc
# leaves the pull alone, so PULLUP true can pin the input high and the switch appears dead.
set_property -dict {PACKAGE_PIN M20 IOSTANDARD LVCMOS33} [get_ports sw_bypass]
set_property -dict {PACKAGE_PIN M19 IOSTANDARD LVCMOS33} [get_ports sw_bypass_alt]

# --- buttons and LEDs for the one-click product interface -------------------------------------
set_property -dict {PACKAGE_PIN D19 IOSTANDARD LVCMOS33} [get_ports {btn[0]}]
set_property -dict {PACKAGE_PIN D20 IOSTANDARD LVCMOS33} [get_ports {btn[1]}]
set_property -dict {PACKAGE_PIN L20 IOSTANDARD LVCMOS33} [get_ports {btn[2]}]
set_property -dict {PACKAGE_PIN L19 IOSTANDARD LVCMOS33} [get_ports {btn[3]}]
# No internal pull: PULLUP on a switch pin held it high once and made the switch look dead.
set_property -dict {PACKAGE_PIN R14 IOSTANDARD LVCMOS33} [get_ports {led[0]}]
set_property -dict {PACKAGE_PIN P14 IOSTANDARD LVCMOS33} [get_ports {led[1]}]
set_property -dict {PACKAGE_PIN N16 IOSTANDARD LVCMOS33} [get_ports {led[2]}]
set_property -dict {PACKAGE_PIN M14 IOSTANDARD LVCMOS33} [get_ports {led[3]}]
