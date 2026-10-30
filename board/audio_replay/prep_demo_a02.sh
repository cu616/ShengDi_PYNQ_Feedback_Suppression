#!/bin/bash
# Record the operator's confirmation for the a02 demo take and select its mode.
# The token is the operator's "I am here and the room is ready" statement; these scripts only
# write it, they never decide anything on their own, and the run script consumes it.
echo "operator on site: video a02 take (real person, zero coefficients, 20 s)" \
  > /home/xilinx/OPERATOR_READY
echo a02 > /home/xilinx/demo_mode.txt
cat /home/xilinx/OPERATOR_READY /home/xilinx/demo_mode.txt
