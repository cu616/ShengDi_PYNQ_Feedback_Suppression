"""Package a completed local build; never uploads or programs hardware."""
import hashlib
import json
from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parents[1]
work = ROOT / "build/work/audio_closed"
out = ROOT / "board/audio_closed"
evidence = ROOT / "report/verification/audio_closed"
sources = ["src/rtl/audio_pl_closed.v", "src/rtl/feedback_fir.v",
           "src/vendor/pynq_v2_4/iis_ser.vhd", "src/vendor/pynq_v2_4/iis_deser.vhd",
           "build/scripts/create_audio_closed.tcl", "build/scripts/audio_bringup.xdc",
           "build/scripts/test_audio_closed.tcl", "sim/audio/tb_audio_closed.v",
           "board/audio_closed/closed_trial.py", "board/audio_closed/residual_tools.py", "board/audio_closed/closed_tools.py", "board/audio_closed/closed_batch.py"]
bit = work / "audio_closed.runs/impl_1/system_wrapper.bit"
hwh = work / "audio_closed.srcs/sources_1/bd/system/hw_handoff/system.hwh"
simulation = ROOT / "build/work/audio_closed_test/audio_closed_test.sim/sim_1/behav/xsim/simulate.log"
log = simulation.read_text(errors="replace")
if "AUDIO_CLOSED_PASS" not in log or "Fatal:" in log:
    raise RuntimeError("integration simulation has not passed")
for p in [bit, hwh, work / "timing.txt", work / "utilization.txt", work / "drc.txt"]:
    if not p.is_file() or p.stat().st_size == 0:
        raise RuntimeError("missing completed build artifact: " + str(p))
out.mkdir(exist_ok=True)
evidence.mkdir(parents=True, exist_ok=True)
shutil.copy2(bit, out / "audio_closed.bit")
shutil.copy2(hwh, out / "audio_closed.hwh")
for name in ("timing.txt", "utilization.txt", "drc.txt"):
    shutil.copy2(work / name, evidence / name)
shutil.copy2(simulation, evidence / "rtl-simulation.txt")
files = sources + ["board/audio_closed/audio_closed.bit", "board/audio_closed/audio_closed.hwh"]
hashes = {name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest() for name in files}
(out / "manifest.json").write_text(json.dumps(dict(
    overlay="audio_closed", frames=16384, taps=256, rate_hz=48828.125,
    hardware_executed=False, hashes=hashes,
    note="Local build only. Inspect timing/DRC evidence; missing I/O constraints remain."), indent=2)+"\n")
print("LOCAL_PACKAGE_CREATED", out)
