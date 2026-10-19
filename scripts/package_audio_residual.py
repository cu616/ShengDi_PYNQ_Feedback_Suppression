"""Package a completed local build; never uploads or programs hardware."""
import hashlib
import json
from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parents[1]
work = ROOT / "build/work/audio_residual"
out = ROOT / "board/audio_residual"
evidence = ROOT / "report/verification/audio_residual"
sources = ["src/rtl/audio_pl_residual.v", "src/rtl/feedback_fir.v",
           "src/vendor/pynq_v2_4/iis_ser.vhd", "src/vendor/pynq_v2_4/iis_deser.vhd",
           "build/scripts/create_audio_residual.tcl", "build/scripts/audio_bringup.xdc",
           "build/scripts/test_audio_residual.tcl", "sim/audio/tb_audio_residual.v",
           "board/audio_residual/open_loop_residual.py", "board/audio_residual/residual_tools.py"]
bit = work / "audio_residual.runs/impl_1/system_wrapper.bit"
hwh = work / "audio_residual.srcs/sources_1/bd/system/hw_handoff/system.hwh"
simulation = ROOT / "build/work/audio_residual_test/audio_residual_test.sim/sim_1/behav/xsim/simulate.log"
log = simulation.read_text(errors="replace")
if "AUDIO_RESIDUAL_PASS" not in log or "Fatal:" in log:
    raise RuntimeError("integration simulation has not passed")
for p in [bit, hwh, work / "timing.txt", work / "utilization.txt", work / "drc.txt"]:
    if not p.is_file() or p.stat().st_size == 0:
        raise RuntimeError("missing completed build artifact: " + str(p))
out.mkdir(exist_ok=True)
evidence.mkdir(parents=True, exist_ok=True)
shutil.copy2(bit, out / "audio_residual.bit")
shutil.copy2(hwh, out / "audio_residual.hwh")
for name in ("timing.txt", "utilization.txt", "drc.txt"):
    shutil.copy2(work / name, evidence / name)
shutil.copy2(simulation, evidence / "rtl-simulation.txt")
files = sources + ["board/audio_residual/audio_residual.bit", "board/audio_residual/audio_residual.hwh"]
hashes = {name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest() for name in files}
(out / "manifest.json").write_text(json.dumps(dict(
    overlay="audio_residual", frames=16384, taps=256, rate_hz=48828.125,
    hardware_executed=False, hashes=hashes,
    note="Local build only. Inspect timing/DRC evidence; missing I/O constraints remain."), indent=2)+"\n")
print("LOCAL_PACKAGE_CREATED", out)
