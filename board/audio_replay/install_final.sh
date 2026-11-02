#!/bin/bash
# One-time product installation from the final frozen package (C: product-install.sh).
source /etc/profile.d/xrt_setup.sh 2>/dev/null || true
export PYTHONUNBUFFERED=1
cd /home/xilinx/jupyter_notebooks/base/audio/final || exit 1
bash product-install.sh 2>&1 | tail -20
echo "=== INSTALLED ==="
ls -1 /opt/shengdi/current 2>/dev/null | head -8
systemctl is-active shengdi-product.service 2>/dev/null || echo 'service unknown'
