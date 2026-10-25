"""Exercise B's unchanged waveform CLI on r4 originals and bad inputs.

This is an entry-point audit, not another waveform implementation. It only
mutates inputs, invokes the exact Git blob and inspects exits/reports. NumPy is
needed solely to change one recorded integer in a control NPZ. No board access.
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import zipfile

ROOT = Path(__file__).resolve().parents[1]
A_COMMIT = "63f6a69ee679f992d1e459d9447262fa1db6b403"
C_COMMIT = "23f176755f79ae5fb9785530f6bf72acdc5bac48"
RAW_SHA = "e9aedd0d865b40f880d8578d5275a592ce8322086def620b86654702cf787b48"
SUMMARY_PACK_SHA = "474975275f63173e490c23ea3d97ad77c0a78a5d0977ba8da807bb7bdfc20367"
NAMES = ("07-fir-off.npz", "09-fir-on.npz", "11-fir-on.npz",
         "13-fir-off.npz", "15-continuous-60s.npz")
CASES = ("original", "prediction_mismatch", "missing_unlisted_tail",
         "wrong_frozen_model", "wrong_summary_value", "missing_requested_summary",
         "used_file_unlisted", "model_lag_first_changed", "summary_capture_identity_changed")


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def blob(commit, path):
    return subprocess.check_output(["git", "show", commit + ":" + path], cwd=ROOT)


def run(b_commit, out_dir):
    import numpy as np

    commit = subprocess.check_output(["git", "rev-parse", b_commit + "^{commit}"],
                                     cwd=ROOT).decode().strip()
    source = blob(commit, "scripts/verify_r4_waveforms.py")
    model_raw = blob(commit, "models/room_v1/calibrated_20261024.json")
    packet = blob(A_COMMIT, "report/verification/audio-replay/r4-review-return.zip")
    summary_packet = blob(C_COMMIT, "build/packages/c-r4-to-b-r1.zip")
    if digest(packet) != RAW_SHA or digest(summary_packet) != SUMMARY_PACK_SHA:
        raise ValueError("fixed original package hash mismatch (D2)")
    with zipfile.ZipFile(io.BytesIO(packet)) as archive:
        if set(archive.namelist()) != set(NAMES) | {"manifest.json"}:
            raise ValueError("fixed raw package member set mismatch (D3)")
        originals = {name: archive.read(name) for name in archive.namelist()}
    with zipfile.ZipFile(io.BytesIO(summary_packet)) as archive:
        summary_raw = archive.read("summary-v3.json")
    manifest = json.loads(originals["manifest.json"])
    if set(manifest["files"]) != set(NAMES):
        raise ValueError("fixed manifest member set mismatch (D3)")
    for name in NAMES:
        entry = manifest["files"][name]
        if digest(originals[name]) != entry["sha256"] or len(originals[name]) != entry["bytes"]:
            raise ValueError("fixed member hash/size mismatch (D2): " + name)

    out_dir.mkdir(parents=True, exist_ok=True)
    # Keep each invocation's work so the exact inputs/outputs remain reviewable.
    work = Path(tempfile.mkdtemp(prefix="b-waveform-cli-", dir=out_dir))
    script = work / "verify_r4_waveforms.py"
    script.write_bytes(source)
    rows = []
    for case in CASES:
        folder = work / case
        pack = folder / "pack"
        pack.mkdir(parents=True)
        for name, raw in originals.items():
            (pack / name).write_bytes(raw)
        model_path, summary_path = folder / "model.json", folder / "summary-v3.json"
        model_path.write_bytes(model_raw)
        summary_path.write_bytes(summary_raw)
        if case == "prediction_mismatch":
            target = pack / "09-fir-on.npz"
            with np.load(target, allow_pickle=False) as capture:
                arrays = {key: capture[key] for key in capture.files}
            arrays["prediction_pcm"][1024] += 1
            np.savez_compressed(target, **arrays)
            edited = json.loads(originals["manifest.json"])
            edited["files"][target.name].update(bytes=target.stat().st_size,
                                                sha256=digest(target.read_bytes()))
            (pack / "manifest.json").write_text(json.dumps(edited), encoding="utf8")
        elif case == "missing_unlisted_tail":
            (pack / NAMES[-1]).unlink()
            edited = json.loads(originals["manifest.json"])
            del edited["files"][NAMES[-1]]
            (pack / "manifest.json").write_text(json.dumps(edited), encoding="utf8")
        elif case == "wrong_frozen_model":
            edited = json.loads(model_raw)
            edited["coefficients_q20"][0] += 1
            model_path.write_text(json.dumps(edited), encoding="utf8")
        elif case == "wrong_summary_value":
            edited = json.loads(summary_raw)
            edited["fir_switch_pairs"][0]["on_minus_off_response_rms_db"] += 1.0
            summary_path.write_text(json.dumps(edited), encoding="utf8")
        elif case == "missing_requested_summary":
            summary_path = folder / "not-present.json"
        elif case == "used_file_unlisted":
            # The NPZ is still consumed. Omitting it must not bypass hash verification.
            edited = json.loads(originals["manifest.json"])
            del edited["files"]["09-fir-on.npz"]
            (pack / "manifest.json").write_text(json.dumps(edited), encoding="utf8")
        elif case == "model_lag_first_changed":
            # Q20 alone is not the complete deployed model: lag_first is semantic.
            edited = json.loads(model_raw)
            edited["lag_first"] = 2
            model_path.write_text(json.dumps(edited), encoding="utf8")
        elif case == "summary_capture_identity_changed":
            edited = json.loads(summary_raw)
            edited["fir_switch_pairs"][0]["off_capture_id"] = "different-capture-not-the-original"
            summary_path.write_text(json.dumps(edited), encoding="utf8")

        command = [sys.executable, str(script), "--pack", str(pack),
                   "--model", str(model_path), "--summary-v3", str(summary_path),
                   "--out-dir", str(folder / "out")]
        process = subprocess.run(command, cwd=work, capture_output=True, text=True,
                                 encoding="utf8", timeout=60)
        report_path = folder / "out/waveform.json"
        report = json.loads(report_path.read_text(encoding="utf8")) if report_path.exists() else None
        row = dict(case=case, command=command, exit_code=process.returncode,
                   waveform_report_written=report is not None,
                   package_ok=report.get("package_ok") if report else None,
                   reported_ok=report.get("ok") if report else None,
                   reported_failures=report.get("failures") if report else None,
                   stdout=process.stdout, stderr=process.stderr)
        if case == "original":
            row["passed"] = (process.returncode == 0 and report is not None
                             and report.get("package_ok") is True
                             and len(report.get("trials", {})) == 4
                             and len(report.get("pairs_computed", [])) == 2
                             and all(r.get("bit_exact") is True for r in report["trials"].values())
                             and (report.get("tail_60s") or {}).get("bit_exact") is True)
        else:
            row["rejected"] = process.returncode != 0
        if report:
            row["model_q20_sha256"] = report["model"]["q20_sha256"]
            row["model_lag_first"] = report["model"]["lag_first"]
            row["trial_q20_sha256"] = report.get("trials", {}).get("09-fir-on.npz", {}).get("coefficients_sha256")
            row["prediction_mismatches"] = report.get("trials", {}).get("09-fir-on.npz", {}).get("prediction_mismatches")
            row["manifest_entries"] = len(report.get("package_rows", []))
            row["tail_present"] = report.get("tail_60s") is not None
            if report.get("pairs_computed") and report.get("pairs_reference"):
                row["first_total_difference_db"] = abs(report["pairs_computed"][0]["total_db"]
                    - report["pairs_reference"][0]["on_minus_off_response_rms_db"])
                row["summary_first_off_capture_id"] = report["pairs_reference"][0].get("off_capture_id")
                row["actual_first_off_capture_id"] = report.get("trials", {}).get("07-fir-off.npz", {}).get("capture_id")
        rows.append(row)

    rejected = sum(row["rejected"] for row in rows[1:])
    result = dict(b_commit=commit, a_commit=A_COMMIT, c_summary_commit=C_COMMIT,
                  script_sha256=digest(source), model_file_sha256=digest(model_raw),
                  raw_package_sha256=RAW_SHA, summary_package_sha256=SUMMARY_PACK_SHA,
                  python=sys.version, numpy=np.__version__, work_dir=str(work),
                  positive_passed=rows[0]["passed"], bad_inputs_rejected=rejected,
                  bad_inputs_total=len(CASES)-1,
                  all_ok=bool(rows[0]["passed"] and rejected == len(CASES)-1),
                  hardware_access=False, production_B_code_modified=False, cases=rows)
    report_path = out_dir / "cli-controls.json"
    report_path.write_text(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False)+"\n", encoding="utf8")
    print("B_WAVEFORM_CLI_REVIEW %s | positive=%s | bad_rejected=%d/%d" % (
        "passed" if result["all_ok"] else "failed",
        "passed" if result["positive_passed"] else "failed", rejected, len(CASES)-1))
    return 0 if result["all_ok"] else 2


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--b-commit", default="12e5ce21e88bc4e17166cc327182cc10929932cf")
    parser.add_argument("--out-dir", type=Path, default=ROOT / "tmp/b-waveform-cli-review")
    arguments = parser.parse_args()
    try:
        raise SystemExit(run(arguments.b_commit, arguments.out_dir.resolve()))
    except (OSError, ValueError, KeyError, subprocess.SubprocessError) as error:
        print("B_WAVEFORM_CLI_REVIEW blocked | %s: %s" % (type(error).__name__, error), file=sys.stderr)
        raise SystemExit(2)
