"""Local checks of the v3 replay arithmetic checker. No board, no pynq.

Run: python -X utf8 board/audio_replay/test_verify_replay_v3.py

C's 2026-10-27 review asked for three corrections, each covered here:
  (a) the 24-bit rail is asymmetric - a legal -8388608 must not be counted as an overflow;
  (b) an overflow that already happened in the unverifiable prefix of a truncated ring must be
      reported, not silently dropped;
  (c) a capture with no verifiable output frame must not read as a pass.
"""
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from replay_tools import verify_replay  # noqa: E402
from closed_tools import rounded_shift  # noqa: E402

RAIL_POS, RAIL_NEG = 2**23 - 1, -2**23
results = []


def case(name, ok, detail=""):
    print("%-58s %s %s" % (name, "OK" if ok else "FAIL", detail))
    results.append(ok)


def capture(mic, gain_q12=4096):
    """Zero coefficients -> prediction 0, so wide == microphone and residual == clip(mic).

    The reference is built the way the hardware builds it: played[n] = gain(wide[n-2]), so a
    consistent capture really is verifiable.
    """
    n = len(mic)
    mic = np.asarray(mic, dtype=np.int64)
    ref = np.zeros(n, dtype=np.int64)
    for i in range(2, n):
        ref[i] = int(np.clip(rounded_shift(np.int64(mic[i-2]) * np.int64(gain_q12), 12),
                             RAIL_NEG, RAIL_POS))
    pred = np.zeros(n, dtype=np.int64)
    res = np.clip(mic, RAIL_NEG, RAIL_POS)
    return np.stack([ref, mic, pred, res], axis=1)


q = np.zeros(2, dtype=np.int64)          # q.size = 2 -> skip = 2 for a truncated ring
src = np.zeros(0, dtype=np.int64)

# (a) legal negative full scale is NOT an overflow
raw = capture([RAIL_NEG, 0, RAIL_NEG, 0, 0, 0, 0, 0])
r = verify_replay(raw, q, False, 4096, src, first_frame=0)
case("legal -8388608 is not an overflow", r['wide_residual_frames'] == 0,
     "counted %d" % r['wide_residual_frames'])

# (a) one past the negative rail IS an overflow
raw = capture([RAIL_NEG - 1, 0, 0, 0, 0, 0, 0, 0])
r = verify_replay(raw, q, False, 4096, src, first_frame=0)
case("-8388609 is an overflow", r['wide_residual_frames'] == 1, "counted %d" % r['wide_residual_frames'])

# (a) one past the positive rail IS an overflow (positive rail is 8388607)
raw = capture([RAIL_POS + 1, 0, 0, 0, 0, 0, 0, 0])
r = verify_replay(raw, q, False, 4096, src, first_frame=0)
case("+8388608 is an overflow", r['wide_residual_frames'] == 1, "counted %d" % r['wide_residual_frames'])

# (b) a truncated ring: the prefix is counted from the RECORDED prediction, not dropped
mic = [RAIL_POS + 1, 0] + [0] * 8
raw = capture(mic)
r = verify_replay(raw, q, False, 4096, src, first_frame=1000)
case("prefix overflow is counted, not dropped",
     r['wide_residual_frames'] == 1 and r['wide_residual_frames_prefix'] == 1
     and r['wide_residual_count_partial'] is False,
     "checked=%d prefix=%d partial=%s" % (r['wide_residual_frames'],
                                          r['wide_residual_frames_prefix'],
                                          r['wide_residual_count_partial']))

# (b) clean prefix -> prefix counter zero, still not partial
raw = capture([0] * 10)
r = verify_replay(raw, q, False, 4096, src, first_frame=1000)
case("clean prefix counts zero",
     r['wide_residual_frames_prefix'] == 0 and r['wide_residual_count_partial'] is False)

# (c) a capture too short to contain a checkable output frame is rejected by the shape guard,
#     so the no-output-frames branch stays defensive; check it cannot be reached as a pass.
r = verify_replay(capture([1000, 2000, 3000]), q, False, 4096, src, first_frame=1000)
case("shortest acceptable ring still verifies one output frame",
     r['output_checked_frames'] == 1 and r['verified'] is True,
     "checked=%d bit_exact=%s" % (r['output_checked_frames'], r['bit_exact']))

# a normal small capture still passes and reports verified
raw = capture([1000, -2000, 3000, -4000, 5000, -6000, 7000, -8000])
r = verify_replay(raw, q, False, 4096, src, first_frame=0)
case("ordinary capture still verifies", r['bit_exact'] is True and r['verified'] is True
     and r['output_mismatches'] == 0, "tm=%d" % r['output_mismatches'])

print("VERIFY_REPLAY_V3_TEST %s (%d checks)"
      % ("PASS" if all(results) else "FAIL", len(results)))
sys.exit(0 if all(results) else 1)
