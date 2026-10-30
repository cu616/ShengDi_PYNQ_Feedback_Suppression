#!/bin/bash
# Record the operator's confirmation for the a05 continuous-run take.
echo "operator on site: video a05 take (continuous run, zero coefficients, 60 s)" \
  > /home/xilinx/OPERATOR_READY
echo a05 > /home/xilinx/demo_mode.txt
cat /home/xilinx/OPERATOR_READY /home/xilinx/demo_mode.txt
