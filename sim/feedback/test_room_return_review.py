"""Regression checks from A's field failures and the small-gain evidence boundary."""
import copy
from pathlib import Path
import sys
import unittest

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'board/audio_replay'));sys.path.insert(0,str(ROOT/'scripts'))
from model_comparison import flat_trial,pair_models,protection_evidence
from room_experiment import comparison_controls,gate_repeatability,room_model_pairs
from review_room_returns import reported_band_bounds
from test_tail_summary import meta


class RoomReturnReviewTests(unittest.TestCase):
    def test_A_final_outcome_is_evidence_but_generic_missing_guard_stays_unknown(self):
        completed=dict(driver_evidence_version='a-replay-evidence-v2',stop_reason='completed',
                       early_stop=False,capture_status=0x8001,clip_counts_raw=[0,0,0])
        self.assertIs(protection_evidence(completed)[0],False)
        self.assertIs(protection_evidence(dict(completed,stop_reason='guard'))[0],True)
        for change in ({'driver_evidence_version':None},{'stop_reason':'exception'},
                       {'capture_status':0x20000},{'clip_counts_raw':[1,0,0]}):
            self.assertIsNone(protection_evidence(dict(completed,**change))[0])
        self.assertIsNone(protection_evidence({})[0])

    def test_invalid_tail_statistics_do_not_erase_comparison_geometry(self):
        m=meta();m.update(evidence_kind='board_recording',source_pcm16_sha256='b'*64)
        a=dict(category='unknown',evaluation_metadata=m,
               tail_analysis_window=dict(first_frame=70000,end_frame=86384,frames=16384))
        row=flat_trial(dict(analysis=a))
        self.assertFalse(row['tail_valid']);self.assertIsNone(row['tail_rms_dbfs'])
        self.assertEqual(row['tail_first_frame'],70000)
        other=copy.deepcopy(row)
        row.update(model_role='baseline',capture_id='b');other.update(model_role='candidate',capture_id='c')
        pair=pair_models([row,other])[0]
        self.assertTrue(pair['configuration_matches']);self.assertFalse(pair['effect_eligible'])

    def test_5_db_operation_pass_does_not_make_a_4p7_db_path_change_comparable(self):
        def g(level):return dict(passed=True,mic_over_ref_db=level)
        rows=[dict(trial_role='closed_model',analysis={'evaluation_metadata':{'comparison_id':'p'}},
                   amplifier_gate=g(0),post_gate=g(0)),
              dict(trial_role='closed_model',analysis={'evaluation_metadata':{'comparison_id':'p'}},
                   amplifier_gate=g(4.71),post_gate=g(4.71))]
        comparison_controls(rows)
        self.assertFalse(rows[0]['path_comparison_control']['valid'])
        self.assertAlmostEqual(rows[0]['path_comparison_control']['mic_over_ref_range_db'],4.71)
        rows[1]['amplifier_gate']=g(1.49);rows[1]['post_gate']=g(1.49)
        comparison_controls(rows);self.assertTrue(rows[0]['path_comparison_control']['valid'])
        rows[1]['post_gate']={};comparison_controls(rows)
        self.assertFalse(rows[0]['path_comparison_control']['valid'])

    def test_repeatability_uses_population_std_and_reference_does_not_hide_drift(self):
        levels=[-32.85,-34.07,-30.91,-29.36,-31.37,-33.27]
        r=gate_repeatability([dict(rms_dbfs=x,reference_rms_dbfs=-23.01,mic_over_ref_db=x+23.01) for x in levels])
        self.assertAlmostEqual(r['rms_dbfs']['range_db'],4.71)
        self.assertAlmostEqual(r['rms_dbfs']['std_db'],1.59007774)
        self.assertAlmostEqual(r['mic_over_ref_db']['range_db'],4.71)
        self.assertEqual(r['reference_rms_dbfs']['range_db'],0.)

    def test_band_reports_never_create_fullband_or_measured_gain(self):
        r=reported_band_bounds({'improved_calibration':{'bands':{
            '300-1000':{'max_H_minus_Hhat_db':-5.42},
            '8200-8600':{'max_H_minus_Hhat_db':-11.8}}}})
        self.assertEqual(r['bands'][0]['predicted_gain_bound_db'],5.42)
        self.assertFalse(r['bands'][0]['meets_proposed_band_target'])
        self.assertIsNone(r['fullband_predicted_gain_bound_db'])
        self.assertIsNone(r['measured_msg_db']);self.assertIsNone(r['measured_asg_db'])

    def test_incomplete_group_retains_the_actual_capture_and_failure_reason(self):
        row=dict(model_role='candidate',capture_id='present',comparison_id='incomplete')
        state={'trials':[row]};room_model_pairs(state)
        self.assertFalse(state['model_pairs'])
        self.assertEqual(state['incomplete_model_pairs'][0]['candidate_capture_id'],'present')
        self.assertIsNone(state['incomplete_model_pairs'][0]['baseline_capture_id'])
        self.assertEqual(state['comparison_group_count'],1)


if __name__=='__main__':unittest.main()
