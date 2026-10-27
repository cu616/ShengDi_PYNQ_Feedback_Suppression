"""Local check of the replay stop semantics. No board, no pynq.

Run: python -X utf8 board/audio_replay/test_runtime_stop.py

The driver itself imports pynq, so the three pynq modules are stubbed before importing it. Only
runtime_stop() and decode_counts() are exercised; everything hardware-facing is untouched.

What has to hold (captain 2026-10-28):
  * input full scale (capture_status bit22) STOPS the run and is reported as "input_clip";
  * a pre-gain residual overflow alone does NOT stop it (it is diagnostic only);
  * prediction saturation, post-gain saturation and mix saturation keep the "guard" path;
  * the four saturation counts still decode from the packed word unchanged.
"""
import sys
import types
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

# ---- stub the Unix-only and board-only imports so the driver can be imported off-board -------
pynq = types.ModuleType("pynq")
pynq.MMIO = type("MMIO", (), {})
pynq.Overlay = type("Overlay", (), {})
overlays = types.ModuleType("pynq.overlays")
base = types.ModuleType("pynq.overlays.base")
base.BaseOverlay = type("BaseOverlay", (), {})
sys.modules.setdefault("pynq", pynq)
sys.modules.setdefault("pynq.overlays", overlays)
sys.modules.setdefault("pynq.overlays.base", base)
sys.modules.setdefault("fcntl", types.ModuleType("fcntl"))

import replay_trial as rt  # noqa: E402


def case(name, status, clip, gain, mix, want):
    got = rt.runtime_stop(status, clip, gain, mix)
    ok = got == want
    print("%-52s status=0x%08x clip=0x%04x gain=%d mix=%d -> %-11s %s"
          % (name, status, clip, gain, mix, got, "OK" if ok else "FAIL want " + repr(want)))
    return ok


results = []
# quiet run
results.append(case("quiet", 0x00000000, 0, 0, 0, None))
# input full scale only
results.append(case("input full scale -> input_clip", 1 << 22, 0, 0, 0, "input_clip"))
# input full scale together with everything else: input wins the label
results.append(case("input full scale + prediction + gain + mix", (1 << 22) | 1, 0x0001, 5, 7,
                    "input_clip"))
# prediction half of the packed word
results.append(case("prediction saturation -> guard", 0, 0x0001, 0, 0, "guard"))
# residual half only: this is the whole point of v3, it must NOT stop
results.append(case("pre-gain residual only -> keep running", 0, 0x0001 << 16, 0, 0, None))
results.append(case("pre-gain residual only, many counts", 0, 0xFFFF << 16, 0, 0, None))
# post-gain and mix keep their stop path
results.append(case("post-gain saturation -> guard", 0, 0, 1, 0, "guard"))
results.append(case("mix saturation -> guard", 0, 0, 0, 1, "guard"))
# a completed run with the done bit set and nothing else
results.append(case("done, nothing else", 1, 0, 0, 0, None))
# fault bits are handled by the caller's loop condition, not by runtime_stop
results.append(case("fault bit18 set (caller handles)", 1 << 18, 0, 0, 0, None))
results.append(case("config rejected bit17 set (caller)", 1 << 17, 0, 0, 0, None))

# decode_counts must still split the packed word the same way (residual high, prediction low)
pred, res, gw, mw = rt.decode_counts(0x0008_0003, 4, 5)
ok = (pred, res, gw, mw) == (3, 8, 4, 5)
print("%-52s %s" % ("decode_counts split unchanged", "OK" if ok else "FAIL"))
results.append(ok)

print("RUNTIME_STOP_TEST %s (%d checks)" % ("PASS" if all(results) else "FAIL", len(results)))
sys.exit(0 if all(results) else 1)
