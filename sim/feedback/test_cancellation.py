import sys
from pathlib import Path
import unittest
import numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'src'))
from feedback.cancellation import cancel_fixed,nlms_open_loop


class CancellationTests(unittest.TestCase):
    def test_hand_rounding_residual_and_bypass(self):
        pred,res,sat=cancel_fixed([1,-1,0],[10,10,10],[2**19],[False,False,True])
        np.testing.assert_array_equal(pred,[0,1,-1])
        np.testing.assert_array_equal(res,[10,9,10])
        self.assertFalse(sat.any())

    def test_saturation(self):
        pred,res,sat=cancel_fixed([2**23-1,0],[0,-2**23],[2**21])
        self.assertEqual(pred[1],2**23-1)
        self.assertEqual(res[1],-2**23)
        self.assertTrue(sat[1])

    def test_nlms_frozen_matches_independent_convolution(self):
        u=np.random.default_rng(1).normal(0,0.1,1000)
        h=np.array([0.5,-0.2,0.1])
        pred,final,stats=nlms_open_loop(u,np.zeros(1000),h,np.zeros(1000,bool))
        np.testing.assert_allclose(pred,np.convolve(u,np.r_[0,h])[:1000],atol=1e-15)
        np.testing.assert_array_equal(final,h); self.assertEqual(stats['updates'],0)

    def test_nlms_recovers_known_path(self):
        u=np.random.default_rng(4).normal(0,0.05,5000)
        h=np.r_[np.zeros(5),0.4,-0.1,np.zeros(9)]
        d=np.convolve(u,np.r_[0,h])[:len(u)]
        _,final,_=nlms_open_loop(u,d,np.zeros(len(h)),np.ones(len(u),bool))
        np.testing.assert_allclose(final,h,atol=1e-9)

    def test_zero_input_freezes_and_bad_parameters_rejected(self):
        _,h,stats=nlms_open_loop(np.zeros(20),np.ones(20),np.zeros(4),np.ones(20,bool))
        self.assertEqual(stats['updates'],0); self.assertFalse(h.any())
        with self.assertRaises(ValueError):
            nlms_open_loop([1],[1],[0],[True],mu=2)

    def test_divergence_guard_rejects_large_update(self):
        _,_,stats=nlms_open_loop([0.1,0],[0,100],[0],[True,True])
        self.assertEqual(stats['rejected_updates'],1)


if __name__=='__main__': unittest.main()
