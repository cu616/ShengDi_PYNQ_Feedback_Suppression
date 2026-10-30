"""Independent analytic cases for the read-only calibration package reviewer."""
import hashlib
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
import zipfile

import numpy as np

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'scripts'))
from audit_lowband_package import inspect_packet,phase_crossing_estimate,spectral_estimate


class LowbandAuditTests(unittest.TestCase):
    def test_positive_real_crossing_does_not_bridge_a_gap_or_negative_real_axis(self):
        f=np.array([0.,100.]);gate=np.array([True,True])
        out=phase_crossing_estimate(f,np.array([1+1j,1-1j]),gate)
        self.assertEqual(out['estimated_db'],0.);self.assertEqual(out['frequency_hz'],50.)
        for response,mask in [(np.array([-1+1j,-1-1j]),gate),
                              (np.array([1+1j,1-1j]),np.array([False,True]))]:
            self.assertIsNone(phase_crossing_estimate(f,response,mask)['estimated_db'])

    def test_scalar_path_and_explicit_window_endpoint(self):
        x=np.random.default_rng(13).normal(size=4096)*.01
        captures=[({'reference':x,'microphone':x*.5},
                   dict(capture_id='analytic',first_frame=1000,source_end_frame_exclusive=5096,
                        source_schedule_verified=True))]
        inclusive=spectral_estimate(captures,np.zeros(8),512)
        legacy=spectral_estimate(captures,np.zeros(8),512,include_last_window=False)
        self.assertAlmostEqual(inclusive['sampled_small_gain_estimate']['estimated_db'],6.020599913,places=7)
        self.assertEqual(inclusive['spectral_windows'],15);self.assertEqual(legacy['spectral_windows'],14)
        self.assertFalse(inclusive['fullband_certified'])
        source_only=spectral_estimate(captures,np.zeros(8),512,source_on_only=True)
        self.assertLess(source_only['spectral_windows'],inclusive['spectral_windows'])

    def test_absent_excitation_cannot_produce_a_finite_gain_claim(self):
        x=np.zeros(1024)
        out=spectral_estimate([({'reference':x,'microphone':x},
                               dict(capture_id='zero',first_frame=0))],np.zeros(4),256)
        self.assertIsNone(out['sampled_small_gain_estimate']['estimated_db'])
        self.assertEqual(out['sampled_small_gain_estimate']['selected_bins'],0)

    def test_hashes_and_unbound_member_inventory(self):
        (ROOT/'tmp').mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir=ROOT/'tmp') as d:
            p=Path(d)/'input.zip';payload=b'raw npz placeholder'
            q=np.array([1,2],dtype='<i4');model=json.dumps({'coefficients_q20':[1,2]}).encode()
            sha=lambda x:hashlib.sha256(x).hexdigest()
            manifest=dict(files=[dict(path='seg_0.npz',sha256=sha(payload),size_bytes=len(payload))],
                          model=dict(file='model.json',sha256=sha(model),coefficients_q20_sha256=sha(q.tobytes())))
            for tamper in (False,True):
                with zipfile.ZipFile(p,'w') as z:
                    z.writestr('manifest.json',json.dumps(manifest));z.writestr('model.json',model)
                    z.writestr('seg_0.npz',payload+b'x' if tamper else payload)
                    z.writestr('script.py','raise RuntimeError("must never execute")')
                if tamper:
                    with self.assertRaisesRegex(ValueError,'hash/size'):inspect_packet(p)
                else:
                    result=inspect_packet(p);self.assertEqual(result[-1],['script.py'])


if __name__=='__main__':unittest.main()
