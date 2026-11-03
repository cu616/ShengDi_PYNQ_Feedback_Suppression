"""Independent regression cases for the saved-data high-frequency audit."""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import subprocess
import sys

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('hf',ROOT/'scripts/diag_highfreq_phase.py')
hf = importlib.util.module_from_spec(spec)
spec.loader.exec_module(hf)


class PhaseAuditTests(unittest.TestCase):
    def test_complex_identity_and_one_sample_delay(self):
        fs=48828.125; n=4096
        f=np.fft.rfftfreq(n,1/fs)
        h=np.array([.7,-.1,.03])
        Hh=hf.model_H(h,f,fs,1)
        for extra in (-1,0,1):
            H=Hh*np.exp(-2j*np.pi*f/fs*extra)
            sums=np.array([np.ones(len(f)),H,abs(H)**2,Hh])
            r=hf.response_report(sums,1,h,1,fs,n,5786/4096,2)
            self.assertLess(max(row['cosine_identity_error'] for row in r['rows']),1e-7)
            for fit in r['phase_slopes']:
                self.assertAlmostEqual(fit['equivalent_delay_samples'],extra,places=10)
            self.assertTrue(r['phase_slopes'])

    def test_known_fir_window_matched_residual(self):
        rng=np.random.default_rng(10); u=rng.normal(0,.025,32768)
        h=np.zeros(512); h[124]=.65;h[130]=-.15
        m=np.convolve(u,np.r_[0,h])[:len(u)]
        sums,w,warm=hf.spectra(u,m,h,1,4096)
        r=hf.response_report(sums,w,h,1,48828.125,4096,5786/4096,2)
        self.assertEqual(warm,512)
        self.assertLess(max(row['window_matched_residual_abs'] for row in r['rows']),1e-12)
        row=min(r['rows'],key=lambda x:abs(x['grid_hz']-8350))
        self.assertLess(abs(row['H_abs']-row['Hh_abs']),.06)

    def test_gaps_are_not_joined_in_phase_fit(self):
        f=np.arange(0,10001,10.); a=np.ones(len(f),complex)
        coh=np.zeros(len(f));coh[(f>8000)&(f<8070)]=1;coh[(f>8200)&(f<8270)]=1
        self.assertEqual(hf.phase_slopes(f,a,a,coh,48828.125),[])

    def fixture(self, root):
        q=np.zeros(512,dtype=int);q[124]=int(.65*2**20)
        model={'coefficients_q20':q.tolist(),'taps':512,'lag_first':1,
               'sample_rate_hz':48828.125,'fixture_id':'test','hp_volume':40}
        mp=root/'model.json';mp.write_text(json.dumps(model))
        u=np.random.default_rng(12).normal(0,.02,16384)
        m=np.convolve(u,np.r_[0,q/2**20])[:len(u)]
        md={'capture_id':'train','source':'board','forward_path_open':True,'gain_q12':0,
            'zero_coeff':True,'stop_reason':'completed','fixture_id':'test','hp_volume':40,
            'first_frame':0,'source_end_frame_exclusive':16384,'input_full_scale_seen':False}
        return mp,u,m,md

    def save(self,p,u,m,md,fs=48828.125):
        np.savez(p,reference=u,microphone=m,metadata_json=json.dumps(md),sample_rate_hz=fs)

    def test_training_validation_separate_and_run_ignored(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);mp,u,m,md=self.fixture(root)
            self.save(root/'a_training_00.npz',u,m,md)
            self.save(root/'a_validation_00.npz',u,m,dict(md,capture_id='valid'))
            self.save(root/'a_run_00.npz',u,m,dict(md,forward_path_open=False,gain_q12=5786))
            r=hf.analyze(root,mp)
            self.assertEqual(set(r['groups']),{'training','validation'})
            self.assertEqual(len(r['ignored_noncalibration_files']),1)
            self.assertNotIn('microphone',json.dumps(r))
            json.dumps(r,allow_nan=False)

    def test_bad_metadata_and_units_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);mp,u,m,md=self.fixture(root)
            h,l,fs,mi=hf.read_model(mp)
            cases=[dict(md,forward_path_open=False),dict(md,gain_q12=5786),
                   dict(md,input_full_scale_seen=True),dict(md,hp_volume=39),
                   dict(md,source_end_frame_exclusive=0)]
            p=root/'a_training_00.npz'
            for bad in cases:
                self.save(p,u,m,bad)
                with self.assertRaises(ValueError):hf.read_capture(p,fs,mi)
            self.save(p,u,m,md,48000)
            with self.assertRaises(ValueError):hf.read_capture(p,fs,mi)
            self.save(p,(u*32768).astype('int16'),m,md)
            with self.assertRaises(ValueError):hf.read_capture(p,fs,mi)
            with self.assertRaises(ValueError):hf.read_model(mp,'bad')
            with self.assertRaises(ValueError):hf.read_model(mp,None,'bad')

    def test_source_tail_trim_and_unequal_length_rejection(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);mp,u,m,md=self.fixture(root);_,_,fs,mi=hf.read_model(mp)
            p=root/'a_training_00.npz'
            self.save(p,u,m,dict(md,first_frame=2))
            a,b,info=hf.read_capture(p,fs,mi)
            self.assertEqual(len(a),16382)
            self.save(p,u,m[:-1],md)
            with self.assertRaises(ValueError):hf.read_capture(p,fs,mi)

    def receipt_fixture(self, root):
        mp,u,m,md=self.fixture(root)
        _,_,_,mi=hf.read_model(mp)
        io=root/'io';io.mkdir()
        record={'scene_id':'test','bundle':{
            'scene_id':'test','model_sha256':mi['sha256'],
            'coefficients_sha256':mi['coefficients_sha256']}}
        for stage in ('training','validation'):
            f=io/('a_'+stage+'_00.npz')
            self.save(f,u,m,dict(md,capture_id=stage,fixture_id='previous'))
            record[stage]=[{'path':str(f),'sha256':hf.sha(f),'capture_id':'receipt-'+stage}]
        receipt=root/'result.json';receipt.write_text(json.dumps(record))
        return mp,io,receipt,mi,u,m,md

    def test_stale_fixture_accepted_only_with_bound_receipt(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);mp,io,receipt,mi,u,m,md=self.receipt_fixture(root)
            before={p.name:hf.sha(p) for p in io.glob('*.npz')}
            with patch.multiple(hf,SCENE='test',MODEL_SHA=mi['sha256'],
                                COEFF_SHA=mi['coefficients_sha256'],STALE_FIXTURE='previous'):
                with self.assertRaisesRegex(ValueError,'fixture_id'):
                    hf.analyze(io,mp)
                r=hf.analyze(io,mp,scene_receipt=receipt)
                self.assertEqual(len(r['files']),2)
                for f in r['files']:
                    self.assertEqual(f['fixture_id'],'previous')
                    self.assertEqual(f['fixture_annotation']['receipt_scene_id'],'test')
                    self.assertEqual(f['scene_provenance']['receipt_sha256'],hf.sha(receipt))
            self.assertEqual(before,{p.name:hf.sha(p) for p in io.glob('*.npz')})

    def test_other_fixture_mismatch_still_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            mp,io,receipt,mi,u,m,md=self.receipt_fixture(Path(d))
            with self.assertRaisesRegex(ValueError,'fixture_id'):
                hf.analyze(io,mp,scene_receipt=receipt)

    def test_receipt_wrong_model_file_scene_stage_and_source_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            mp,io,receipt,mi,u,m,md=self.receipt_fixture(Path(d))
            original=json.loads(receipt.read_text())
            for variant in ('scene','model','coeff','capture','stage','duplicate_source'):
                r=json.loads(json.dumps(original))
                if variant=='scene':r['scene_id']='wrong'
                if variant=='model':r['bundle']['model_sha256']='wrong'
                if variant=='coeff':r['bundle']['coefficients_sha256']='wrong'
                if variant=='capture':r['training'][0]['sha256']='wrong'
                if variant=='stage':r['training'],r['validation']=r['validation'],r['training']
                if variant=='duplicate_source':
                    r['training'][0]['source_sha256']=r['validation'][0]['source_sha256']='same'
                receipt.write_text(json.dumps(r))
                with self.assertRaises(ValueError):hf.receipt_inputs(receipt,io,mi)

    def test_receipt_excludes_previous_attempt(self):
        with tempfile.TemporaryDirectory() as d:
            mp,io,receipt,mi,u,m,md=self.receipt_fixture(Path(d))
            old=io/'old_training_99.npz'
            self.save(old,u,m,dict(md,capture_id='old',forward_path_open=False,gain_q12=5786))
            with patch.multiple(hf,SCENE='test',MODEL_SHA=mi['sha256'],
                                COEFF_SHA=mi['coefficients_sha256'],STALE_FIXTURE='previous'):
                r=hf.analyze(io,mp,scene_receipt=receipt)
            self.assertEqual(len(r['files']),2)
            self.assertIn(str(old),r['ignored_noncalibration_files'])

    def test_cli_writes_failure_json_without_home_dependency(self):
        with tempfile.TemporaryDirectory() as d:
            out=Path(d)/'failure.json'
            r=subprocess.run([sys.executable,str(ROOT/'scripts/diag_highfreq_phase.py'),
                '--board-scene','--state-root',d,'--out',str(out)],capture_output=True,text=True)
            self.assertEqual(r.returncode,2,r.stderr)
            result=json.loads(out.read_text())
            self.assertEqual(result['status'],'blocked')
            self.assertIn('MATCHING_MODEL_NOT_FOUND',result['error'])
            self.assertTrue(result['run_dir'].startswith(d))


if __name__=='__main__':unittest.main()
