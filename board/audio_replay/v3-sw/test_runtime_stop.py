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

# ---- mixed bitstream/driver must be refused before arming -----------------------------------
# Scratch files live next to this test (a workspace path) instead of the OS temp directory: the
# confined sandbox refuses the permission reset that TemporaryDirectory performs on cleanup.
import hashlib  # noqa: E402

scratch = HERE / "._idcheck"
scratch.mkdir(exist_ok=True)
good_bit = scratch / "good.bit"
good_hwh = scratch / "good.hwh"
good_bit.write_bytes(b"v3 bitstream placeholder")
good_hwh.write_bytes(b"v3 hwh placeholder")


def check(name, bit_bytes, hwh_bytes, want):
    bit = scratch / ("case_%d.bit" % len(name))
    bit.write_bytes(bit_bytes)
    bit.with_suffix(".hwh").write_bytes(hwh_bytes)
    try:
        rt.verify_paired_bitstream(bit)
        got = "accepted"
    except FileNotFoundError:
        got = "missing"
    except RuntimeError:
        got = "refused"
    ok = got == want
    print("%-52s -> %-8s %s" % (name, got, "OK" if ok else "FAIL want " + want))
    results.append(ok)


real_bit, real_hwh = rt.EXPECTED_BIT_SHA256, rt.EXPECTED_HWH_SHA256
rt.EXPECTED_BIT_SHA256 = hashlib.sha256(good_bit.read_bytes()).hexdigest()
rt.EXPECTED_HWH_SHA256 = hashlib.sha256(good_hwh.read_bytes()).hexdigest()
check("matching pair", good_bit.read_bytes(), good_hwh.read_bytes(), "accepted")
check("bitstream swapped (v2 bit, v3 driver)",
      b"v2 bitstream placeholder", good_hwh.read_bytes(), "refused")
check("hwh swapped (v2 hwh, v3 bit)",
      good_bit.read_bytes(), b"v2 hwh placeholder", "refused")
rt.EXPECTED_BIT_SHA256, rt.EXPECTED_HWH_SHA256 = real_bit, real_hwh

lone = scratch / "no_hwh.bit"
lone.write_bytes(b"x")
try:
    rt.verify_paired_bitstream(lone)
    got = "accepted"
except FileNotFoundError:
    got = "missing"
ok = got == "missing"
print("%-52s -> %-8s %s" % ("missing hwh is rejected", got, "OK" if ok else "FAIL"))
results.append(ok)

for path in scratch.glob("*"):
    try:
        path.unlink()
    except OSError:
        pass
try:
    scratch.rmdir()
except OSError:
    pass

print("RUNTIME_STOP_TEST %s (%d checks)" % ("PASS" if all(results) else "FAIL", len(results)))
sys.exit(0 if all(results) else 1)
