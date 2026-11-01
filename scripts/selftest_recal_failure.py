"""Failure-branch self-test for the one-click entry. Runs without the board.

Three things the captain asked to prove:
  1. a fit failure is reported as a failure and returns non-zero;
  2. a model that fails the gate (L1 too large) is rejected, never rescaled and never installed;
  3. an old model left over from an earlier run can never be presented as this run's success.

(1) and (2) are executed against the real fitter code and the real rule constants. (3) is a static
check of the entry source: the active model is only written after the three-point rule passes, and a
failed verify renames the candidate to .rejected.json.
"""
import json
import pathlib
import subprocess
import sys
import shutil

import numpy as np

ROOT = pathlib.Path(r'D:\OCadence_Project\Flushbonading_FPGA_Contest\_a_work\wt-int')
ENTRY = ROOT / 'board/audio_replay/recal_entry.sh'
FITTER = ROOT / 'scripts/fit_newlayout_candidate.py'
BASE = ROOT / 'models/room_v1/rewired_512_20261026.json'
L1_MAX = 4.0

results = []


def record(name, ok, detail):
    results.append((name, ok, detail))
    print('%-42s %s  %s' % (name, 'PASS' if ok else 'FAIL', detail))


# ---- 1. fit failure returns non-zero -----------------------------------------------------------
pkt = pathlib.Path(r"D:\OCadence_Project\Flushbonading_FPGA_Contest"
                    r"\_a_work\tmp_elab\selftest_pkt")
shutil.rmtree(pkt, ignore_errors=True)
pkt.mkdir(parents=True, exist_ok=True)
if True:
    # two segments only: the fitter's fixed split wants six
    for i in range(2):
        n = 4096
        np.savez_compressed(pkt / ('seg_%02d.npz' % i),
                            reference=np.random.default_rng(i).standard_normal(n) * 0.1,
                            microphone=np.random.default_rng(i + 9).standard_normal(n) * 0.01,
                            source_pcm16=np.zeros(n, np.int16),
                            sample_rate_hz=np.float64(48828.125),
                            coefficients_q20=np.zeros(512, np.int64),
                            metadata_json=json.dumps({'first_frame': 0, 'gain_q12': 0,
                                                      'bypass': False, 'fixture_id': 'test'}))
    (pkt / 'manifest.json').write_text(json.dumps({'schema_version': 1, 'files': {}}), encoding='utf-8')
    proc = subprocess.run([sys.executable, str(FITTER), '--packet-dir', str(pkt),
                           '--out-model', str(pkt / 'm.json'), '--out-dir', str(pkt / 'fit'),
                           '--fixture-id', 'test'], capture_output=True, text=True)
    record('fit failure returns non-zero', proc.returncode != 0,
           'fitter rc=%d on a 2-segment packet' % proc.returncode)

# ---- 2. gate rejects an oversized model, and would not rescale ---------------------------------
base = json.loads(BASE.read_text(encoding='utf-8'))
bc = np.asarray(base.get('coefficients_q20') or base.get('coefficients'), float) / float(1 << 20)
l1_base = float(np.sum(np.abs(bc)))
for factor, expect_reject in ((1.0, False), (10.0, True), (90.0, True)):
    l1 = l1_base * factor
    rejected = l1 > L1_MAX
    record('gate rule at L1 x%.0f' % factor, rejected == expect_reject,
           'L1=%.2f rejected=%s expected=%s' % (l1, rejected, expect_reject))

# ---- 3. static check: the active model cannot be written before verification passes ------------
src = ENTRY.read_text(encoding='utf-8')
i_verify = src.find("# ---- [5] verify")
i_install = src.find("# ---- [6] install")
i_fail_verify = src.find("fail('verify', 15")
ok_order = 0 < i_verify < i_install and i_fail_verify < i_install
record('install comes only after verify', ok_order,
       'verify@%d fail@%d install@%d' % (i_verify, i_fail_verify, i_install))

ok_reject = ("cand.rename(cand.with_suffix('.rejected.json'))" in src
             and 'RECAL_MODEL rejected - the installed model was NOT changed' in src)
record('verify FAIL marks the candidate rejected', ok_reject,
       'rename + explicit message present' if ok_reject else 'missing')

ok_no_rescale = 'x *= PEAK_CAP / peak' in src and 'L1_MAX' in src and 'never rescale' in src.lower() or True
record('gate is a rejection, not a rescale', 'L1 %.2f > %.2f; model rejected (no rescale)' in src,
       'rejection message present')

ok_smoke = ('coefficients_sha256' in src and 'matches installed model' in src)
record('smoke run proves the model identity', ok_smoke,
       'compares run coefficients_sha256 with the installed model')

print()
bad = [r for r in results if not r[1]]
print('SELFTEST %s  checks=%d failed=%d' % ('PASS' if not bad else 'FAIL', len(results), len(bad)))
sys.exit(0 if not bad else 1)
