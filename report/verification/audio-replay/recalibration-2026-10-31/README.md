{
  "what": "First end-to-end run of the one-click recalibration on hardware (2026-10-31)",
  "board": "pynq / 192.168.2.99, package audio_switch (bit 2113a454), driver pinned to it",
  "command": "prep_recalibrate.sh then recalibrate_oneclick.sh",
  "flow_result": {
    "phases_completed": 6,
    "verdict": "FAIL",
    "capture": "6/6 segments completed, bit22=0, excitation -8.0 dBFS, no gate and no human speech",
    "convert": "our capture format rewritten to the fitter's packet format (added sample_rate_hz and coefficients_q20)",
    "fit": "returncode 0, taps=512, lag_first=1, candidate sha256 741da19c63fc46635cbd572adadfc3f605ed8bdde3a3071e45bb2be4a3103c01",
    "verify_arms": "open/bypass/cancel all completed, capture_status 0x00008001 each",
    "reject_path": "candidate renamed model_candidate_20250511-103038.rejected.json; the deployed model was not touched"
  },
  "three_point_with_the_refit": {
    "cd_322_db": 8.2643,
    "loop_boost_db": 1.9756,
    "acoustic_difference_db": -0.2187,
    "overshoot_db": -2.1944,
    "rule": "acoustic_difference >= loop_boost - 1.5 and |overshoot| <= 1.5",
    "verdict": "FAIL (needs >= 0.4756 dB, measured -0.2187; |overshoot| 2.19 > 1.5)"
  },
  "reading": [
    "The plumbing works: six phases, one verdict, and the reject path leaves no half-installed state.",
    "The refit itself did not pass. CD(322) is healthy at 8.26 dB, so the fitted model does cancel the "
    "residual, but that did not turn into a microphone-level reduction: the cancel arm sits 0.22 dB "
    "ABOVE the bypass arm and 2.19 dB above the no-loop path.",
    "loop_boost measured only 1.98 dB this run, against 3.70 dB in C's 322 Hz round. The loop boost is a "
    "property of room+gain, not of the model, so today's arrangement is not the same as that round. Any "
    "comparison across the two must say so.",
    "Open questions for B: was the excitation (0.45 s x 6 at -8 dBFS) enough for this fitter's protocol, "
    "and does the alignment/lag found here differ from the deployed model's? A residual depth of 8 dB "
    "with no acoustic effect is consistent with a prediction that is right in magnitude but wrong in "
    "timing or phase."
  ],
  "not_claimed": [
    "one-click recalibration is verified as a PROCEDURE, not as a successful refit",
    "no statement about the audible benefit at any distance",
    "the 50 cm / 200 cm cases were not measured"
  ],
  "next": [
    "compare the refit's coefficients and alignment against models/room_v1/rewired_512_20261026.json",
    "ask B whether the excitation level/duration matches the protocol the fitter was built for",
    "retry with a longer excitation (or more segments) once B answers; the flow needs no change"
  ]
}
