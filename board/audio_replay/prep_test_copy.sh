#!/bin/bash
# Prepare a writable test copy of the frozen product with the stage timeouts raised, so the one-click
# recalibration can be exercised without waiting for C to re-freeze.
set -u
echo '=== stop product service (it owns the FPGA) ==='
echo xilinx | sudo -S systemctl stop shengdi-product.service 2>&1 | tail -1
sleep 2

echo '=== copy release to a test dir ==='
echo xilinx | sudo -S rm -rf /home/xilinx/shengdi-test
echo xilinx | sudo -S cp -a /opt/shengdi/current /home/xilinx/shengdi-test 2>/dev/null || \
  echo xilinx | sudo -S cp -aL /opt/shengdi/current /home/xilinx/shengdi-test
echo xilinx | sudo -S chown -R xilinx:xilinx /home/xilinx/shengdi-test
ls /home/xilinx/shengdi-test | head -6

echo '=== raise stage timeouts ==='
/usr/local/share/pynq-venv/bin/python - <<'PY'
import json, pathlib
p = pathlib.Path('/home/xilinx/shengdi-test/product-config.json')
d = json.loads(p.read_text(encoding='utf-8'))
before = (d.get('io_timeout_seconds'), d.get('compute_timeout_seconds'))
d['io_timeout_seconds'] = 150
d['compute_timeout_seconds'] = 150
p.write_text(json.dumps(d, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
after = json.loads(p.read_text(encoding='utf-8'))
print('TIMEOUT_BEFORE', before)
print('TIMEOUT_AFTER', (after['io_timeout_seconds'], after['compute_timeout_seconds']))
PY

echo '=== what does --once do? ==='
grep -n "once\|field_trial\|def run_once\|args.once" /home/xilinx/shengdi-test/recal_product.py | head -12
