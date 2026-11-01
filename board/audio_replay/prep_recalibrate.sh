#!/bin/bash
# Record the operator's go for one recalibration round and set its parameters.
# Recalibration is a machine-only procedure: nobody has to speak, and there is no gate to wait for.
# The token is consumed by the run script.
echo "operator on site: one-click recalibration (machine-only, no speech)" \
  > /home/xilinx/OPERATOR_READY
{
  echo "level_db=-5.0"
  echo "segments=6"
  echo "seconds=0.3357"
  echo "gain_db=0.0"
} > /home/xilinx/recal.txt
cat /home/xilinx/OPERATOR_READY /home/xilinx/recal.txt
echo "--- prerequisites ---"
ls -1 /home/xilinx/shengdi_repo/scripts/fit_newlayout_candidate.py 2>/dev/null || \
  echo "MISSING: upload the fitter sources to /home/xilinx/shengdi_repo/scripts/"
