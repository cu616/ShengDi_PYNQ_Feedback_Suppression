"""Analytic tail ratios, literal configuration mismatches, and read-only batch QA."""
import contextlib
import csv
import hashlib
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
import numpy as np

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'board/audio_replay'));sys.path.insert(0,str(ROOT/'scripts'))
from evaluation import analyze_npz
from tail_metrics import tail_statistics
from model_comparison import load_registry,flat_trial,pair_models,validate_model,select_model,RETIRED_BITS
from summarize_tail_batch import summarize

RATE=48828.125; BIT='8b2426f4fbcf27425731899557b179d2aea8a4ec2fa26dcc11b60102ecb45339'


def signal(slope=0):
    t=np.arange(16384)/RATE
    return np.rint(2**23*.01*10**(slope*t/20)*(np.sin(2*np.pi*500*t)+np.sin(2*np.pi*2000*t)+np.sin(2*np.pi*8400*t))).astype(np.int64)


def meta():
    return dict(first_frame=70000,completed_frames=86384,frames=16384,
                source_end_frame_exclusive=48828,source_frames=48828,source_schedule_verified=True,
                transition_frames=2442,external_source_off_verified=True,
                external_source_active=False,positive_control_valid=True,
                gain_q12=0,hp_volume=40,bit_sha256=BIT,sample_rate_hz=RATE,
                fixture_id='room_v1_20261021',session_id='software-session',
                comparison_id='software-room-pair',repeat_id=1,scene_sha256='a'*64,
                guard_tripped=False,mute_applied=True,mute_during_observation=False,bypass=False,
                prediction_saturations=0,residual_saturations=0,gain_saturations=0,mix_saturations=0,
                clip_counts_raw=[0,0,0],verification={'bit_exact':True},evidence_kind='software_fixture')


def make_example(folder):
    """g=0 and zero reference make prediction/output exactly zero for ANY q.

    These captures test the schema, not a candidate improvement or field gain.
    A 256 baseline is explicitly zero-extended for the synthetic 512 memory only.
    """
    folder=Path(folder);folder.mkdir(parents=True,exist_ok=True)
    pcm=signal();source=np.zeros(48828,dtype='<i2')
    for role,name in [('baseline','room_v1/baseline_256.json'),('candidate','room_v1/candidate_512.json')]:
        path=ROOT/'models'/name;model=json.loads(path.read_text(encoding='utf8'))
        q=np.asarray(model['coefficients_q20'],dtype='<i4');q=np.pad(q,(0,512-len(q)))
        m=meta();m.update(capture_id='software-'+role,model_role=role,
                         model_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
                         coefficients_sha256=hashlib.sha256(q.astype('<i4').tobytes()).hexdigest(),
                         source_pcm16_sha256=hashlib.sha256(source.tobytes()).hexdigest())
        np.savez_compressed(folder/(role+'.npz'),reference=np.zeros(16384),microphone=pcm/2**23,
                            prediction_pcm=np.zeros(16384,dtype=np.int64),residual_pcm=pcm,
                            coefficients_q20=q,source_pcm16=source,sample_rate_hz=RATE,
                            metadata_json=json.dumps(m))


class TailSummaryTests(unittest.TestCase):
    def work(self):
        (ROOT/'tmp').mkdir(exist_ok=True)
        return tempfile.TemporaryDirectory(dir=ROOT/'tmp')

    def test_analytic_three_band_ratio_and_slope(self):
        x=signal();y=np.rint(x/2).astype(np.int64)
        out=tail_statistics(x,y,meta(),RATE)
        self.assertTrue(out['tail_valid'])
        for v in out['tail_residual_over_mic_db'].values():self.assertAlmostEqual(v,-6.020599913,delta=.002)
        self.assertAlmostEqual(out['tail_slope_db_per_s'],0,delta=.1)
        growth=tail_statistics(signal(30),signal(30),meta(),RATE)
        self.assertAlmostEqual(growth['tail_slope_db_per_s'],30,delta=.1)

    def test_gate_rejects_active_unknown_external_and_short(self):
        for change in ({'source_end_frame_exclusive':80000}, {'source_schedule_verified':False},
                       {'external_source_off_verified':False},{'external_source_active':True},
                       {'dropped_frames':1},{'frames':1}):
            m=meta();m.update(change)
            out=tail_statistics(signal(),signal(),m,RATE)
            self.assertFalse(out['tail_valid']);self.assertIsNone(out['tail_slope_db_per_s'])
        m=meta();m.update(first_frame=86000,frames=384)
        self.assertIn('tail_too_short',tail_statistics(signal()[:384],signal()[:384],m,RATE)['tail_reasons'])

    def test_clipping_zero_and_missing_bands_are_not_finite_performance(self):
        x=signal();x[30]=2**23-1
        self.assertIn('tail_clipped',tail_statistics(x,signal(),meta(),RATE)['tail_reasons'])
        zero=np.zeros(16384,dtype=np.int64)
        self.assertFalse(tail_statistics(zero,zero,meta(),RATE)['tail_valid'])
        self.assertFalse(tail_statistics(signal(),zero,meta(),RATE)['tail_valid'])

    def test_registry_hashes_and_rejection_conditions(self):
        registry=load_registry(ROOT/'models');self.assertEqual(len(registry),4)
        selected=select_model(registry,'room_v1_20261021')
        self.assertEqual(selected,'c8be7f78e7ccb73c8b023aa9e74ddaa0914bc4dabf1e2de91ce46114a0679f9a')
        self.assertEqual(registry[selected]['role'],'baseline')
        with self.assertRaisesRegex(ValueError,'no old-session fallback'):
            select_model({k:v for k,v in registry.items() if k!=selected},'room_v1_20261021')
        self.assertEqual(registry[select_model(registry,'box_v1_20261016')]['logical_taps'],256)
        with self.assertRaises(ValueError):select_model(registry,'unregistered')
        path=ROOT/'models/room_v1/candidate_512.json'
        validate_model(path,'room_v1_20261021',512)
        with self.assertRaises(ValueError):validate_model(path,'room_v1_20261021',256)
        with self.assertRaises(ValueError):validate_model(path,'box_v1_20261016',512)
        for field,value in [('lag_first',0),('sample_rate_hz',48000)]:
            with self.work() as d:
                m=json.loads(path.read_text(encoding='utf8'));m[field]=value
                bad=Path(d)/'bad.json';bad.write_text(json.dumps(m))
                with self.assertRaises(ValueError):validate_model(bad,'room_v1_20261021',512)

    def test_same_gain_pair_and_read_only_csv(self):
        with self.work() as d:
            source=Path(d)/'raw';make_example(source)
            before={p.name:p.read_bytes() for p in source.glob('*.npz')}
            with contextlib.redirect_stdout(io.StringIO()):state=summarize(source,Path(d)/'derived',ROOT/'models')
            self.assertEqual(state['schema_version'],3)
            self.assertEqual(state['configuration_matched_pairs'],1)
            self.assertEqual(state['effect_eligible_pairs'],0)
            rows=state['trials'];self.assertEqual({r['gain_q12'] for r in rows},{0})
            self.assertTrue(all(r['evidence_kind']=='software_fixture' for r in rows))
            self.assertEqual({r['model_role'] for r in rows},{'baseline','candidate'})
            baseline=next(r for r in rows if r['model_role']=='baseline')
            self.assertEqual((baseline['logical_taps'],baseline['loaded_taps']),(256,512))
            self.assertEqual(before,{p.name:p.read_bytes() for p in source.glob('*.npz')})
            with (Path(d)/'derived/summary.csv').open(encoding='utf-8-sig',newline='') as f:csv_rows=list(csv.DictReader(f))
            for key in ('gain_q12','hp_volume','bit_sha256','coefficients_sha256','tail_rms_dbfs',
                        'tail_slope_db_per_s','tail_residual_over_mic_db_8200_8600','mute_applied',
                        'positive_control_valid','eligibility_reasons','derived_loaded_taps'):
                self.assertTrue(all(r[key]!='' for r in csv_rows),key)
            rows[1]['gain_q12']=1
            pair=pair_models(rows)[0]
            self.assertFalse(pair['configuration_matches'])
            self.assertTrue(all(r['category']=='invalid' for r in rows))
            self.assertEqual({r['gain_q12'] for r in rows},{0,1})

    def test_padding_cannot_be_called_candidate_and_unknown_events_stay_null(self):
        with self.work() as d:
            source=Path(d);make_example(source)
            a=analyze_npz(source/'baseline.npz');a['evaluation_metadata']['model_role']='candidate'
            row=flat_trial({'analysis':a},load_registry(ROOT/'models'))
            self.assertEqual(row['model_role'],'baseline');self.assertEqual(row['category'],'invalid')
            del a['evaluation_metadata']['guard_tripped'];del a['evaluation_metadata']['mute_applied']
            row=flat_trial({'analysis':a})
            self.assertIsNone(row['protection_triggered']);self.assertIsNone(row['mute_applied'])
            a['evaluation_metadata'].update(guard_tripped=False,protection_triggered=True)
            self.assertTrue(flat_trial({'analysis':a})['protection_triggered'])

    def test_missing_tail_safety_only_and_evidence_binding(self):
        with self.work() as d:
            source=Path(d);make_example(source)
            a=analyze_npz(source/'baseline.npz',external_source_active=True)
            row=flat_trial({'analysis':a},load_registry(ROOT/'models'))
            self.assertFalse(row['effect_eligible']);self.assertIsNone(row['tail_rms_dbfs'])
            bad={'input_sha256':'0'*64,'provenance':'wrong file','metadata':{}}
            self.assertEqual(analyze_npz(source/'baseline.npz',metadata_evidence=bad)['category'],'invalid')
            blob=(source/'baseline.npz').read_bytes()
            bad={'input_sha256':hashlib.sha256(blob).hexdigest(),'provenance':'cannot edit actual gain',
                 'metadata':{'gain_q12':700}}
            out=analyze_npz(source/'baseline.npz',metadata_evidence=bad)
            self.assertEqual(out['category'],'invalid')
            self.assertEqual(out['original_metadata']['gain_q12'],0)

    def test_scene_and_ambiguous_repeats_not_paired(self):
        with self.work() as d:
            make_example(d);registry=load_registry(ROOT/'models')
            rows=[flat_trial({'analysis':analyze_npz(Path(d)/(r+'.npz'))},registry) for r in ('baseline','candidate')]
            rows[1]['scene_sha256']='b'*64
            self.assertFalse(pair_models(rows)[0]['configuration_matches'])
            rows.append(dict(rows[0]));self.assertIn('ambiguous',pair_models(rows)[0]['reasons'][0])

    def test_corrupt_archive_preserved_as_invalid_row(self):
        with self.work() as d:
            source=Path(d)/'raw';make_example(source)
            (source/'corrupt.npz').write_bytes((source/'baseline.npz').read_bytes()[:64])
            with contextlib.redirect_stdout(io.StringIO()):state=summarize(source,Path(d)/'out',ROOT/'models')
            self.assertEqual(len(state['trials']),3)
            bad=next(r for r in state['trials'] if r['file']=='corrupt.npz')
            self.assertEqual(bad['category'],'invalid');self.assertIsNone(bad['tail_slope_db_per_s'])

    def test_legacy_capacity_and_hash_inference_preserve_unknown_load(self):
        registry=load_registry(ROOT/'models')
        digest,model=next((k,v) for k,v in registry.items() if v['file']=='box_v1/baseline_256.json')
        m=meta();m.update(fixture_id='box_v1_20261016',model_sha256=digest,
                         coefficients_sha256=model['coefficients_sha256'],
                         bit_sha256='dadbbbabd75ec5c641b337819d33a5845e54da6b89bf6507b5323807d9ddcb05')
        a=dict(original_metadata=m,category='invalid')
        before=json.dumps(a,sort_keys=True)
        row=flat_trial({'analysis':a},registry)
        self.assertEqual(row['bitstream_capacity'],256)
        self.assertNotIn('bitstream_capacity_unverified',row['comparison_reasons'])
        self.assertIsNone(row['loaded_taps'])
        self.assertEqual(row['derived_loaded_taps'],256)
        self.assertIn('metadata',row['derived_loaded_taps_basis'])
        self.assertFalse(row['effect_eligible'])
        self.assertEqual(json.dumps(a,sort_keys=True),before)
        m.update(bit_sha256=BIT,coefficients_sha256=model['padded_512_sha256'])
        self.assertEqual(flat_trial({'analysis':a},registry)['derived_loaded_taps'],512)
        m['coefficients_sha256']='f'*64
        self.assertIsNone(flat_trial({'analysis':a},registry)['derived_loaded_taps'])

    def test_retired_overlay_never_enters_acoustic_pairs(self):
        with self.work() as d:
            make_example(d);registry=load_registry(ROOT/'models');rows=[]
            for role in ('baseline','candidate'):
                a=analyze_npz(Path(d)/(role+'.npz'))
                a['evaluation_metadata'].update(bit_sha256=next(iter(RETIRED_BITS)),evidence_kind='board_recording')
                row=flat_trial({'analysis':a},registry);rows.append(row)
                self.assertEqual(row['evidence_scope'],'pl_arithmetic_only')
                self.assertFalse(row['acoustic_evidence_eligible'])
                self.assertIn('retired_overlay_no_dac_output',row['comparison_reasons'])
                self.assertFalse(row['effect_eligible'])
            self.assertEqual(pair_models(rows),[])

    def test_positive_control_is_independent_of_tail_and_safety(self):
        with self.work() as d:
            make_example(d);a=analyze_npz(Path(d)/'baseline.npz')
            m=a['evaluation_metadata'];m['evidence_kind']='board_recording'
            good=flat_trial({'analysis':a},load_registry(ROOT/'models'))
            self.assertTrue(good['effect_eligible'])
            m['positive_control_valid']=False
            failed=flat_trial({'analysis':a})
            self.assertFalse(failed['positive_control_valid'])
            self.assertEqual(failed['eligibility_reasons'],['positive_control_failed'])
            del m['positive_control_valid']
            unknown=flat_trial({'analysis':a})
            self.assertIsNone(unknown['positive_control_valid'])
            self.assertEqual(unknown['eligibility_reasons'],['positive_control_not_validated'])
            m['guard_tripped']=True;a['tail_statistics']['tail_valid']=False
            blocked=flat_trial({'analysis':a})
            self.assertIn('tail_not_validated',blocked['eligibility_reasons'])
            self.assertIn('safety_not_validated',blocked['eligibility_reasons'])
            self.assertIn('positive_control_not_validated',blocked['eligibility_reasons'])

    def test_derived_artifacts_do_not_register_and_claimed_hashes_are_checked(self):
        with self.work() as d:
            import shutil
            folder=Path(d)/'models';shutil.copytree(ROOT/'models',folder)
            manifest=json.loads((folder/'manifest.json').read_text(encoding='utf8'))
            registry=load_registry(folder)
            for item in manifest['models']:
                item.update({k:registry[item['sha256']][k] for k in ('coefficients_sha256','padded_512_sha256')})
            manifest['derived_artifacts']=[{'file':'missing-padded.json','sha256':'0'*64}]
            (folder/'manifest.json').write_text(json.dumps(manifest))
            self.assertEqual(load_registry(folder),registry)
            manifest['models'][0]['coefficients_sha256']='0'*64
            (folder/'manifest.json').write_text(json.dumps(manifest))
            with self.assertRaises(ValueError):load_registry(folder)


if __name__=='__main__':unittest.main()
