"""recal_algorithm 的真实数据端到端复核：拟合 -> 独立验证 -> 判定，并留证。

用 `_inbox/2026-10-26_bindcapture_rewired` 的六段（部署模型的来源）做 4 训练 / 2 验证，
再拿三个模型跑同一个 validate：本轮拟合的、部署的、旧夹具的、全零的。
证明判据在真实数据上分得开，而不是只在合成数据上成立。

用法：
  python scripts/recal_algorithm_offline.py \
      --inbox D:/Always/QianSai/_inbox \
      --out-dir report/verification/recalibration-algorithm-2026-11-01
"""
from __future__ import annotations

import argparse
import glob
import hashlib
import json
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "board" / "audio_replay"))

import recal_algorithm as ra  # noqa: E402


def entries_of(files):
    out = []
    for p in files:
        p = Path(p)
        out.append({"capture_id": p.stem, "path": str(p), "first_frame": 101780,
                    "source_sha256": hashlib.sha256(p.name.encode()).hexdigest(),
                    "content_kind": "onboard_excitation"})
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--inbox", default="D:/Always/QianSai/_inbox")
    ap.add_argument("--packet", default="2026-10-26_bindcapture_rewired")
    ap.add_argument("--out-dir",
                    default=str(ROOT / "report/verification/recalibration-algorithm-2026-11-01"))
    args = ap.parse_args()

    files = sorted(glob.glob(str(Path(args.inbox) / args.packet / "bind4_*.npz")))
    entries = entries_of(files)
    train, val = entries[:4], entries[4:]
    run = tempfile.mkdtemp(prefix="recal_alg_")
    base = {"contract": "recal-product-v1", "request_id": "offline-1", "scene_id": "room_v1_20261026b",
            "run_dir": run, "attempt": 0, "attempts_total": 1,
            "identity": {"hp_volume": 40, "gain_q12": 1631}}

    t0 = time.time()
    fit = ra.evaluate(dict(base, phase="fit", training=train, validation=val))
    fit_seconds = time.time() - t0
    cases = [{"case": "fit_4train_2val", "decision": fit["decision"],
              "reason": fit["reason"], "seconds": round(fit_seconds, 3),
              "model_sha256": fit.get("model_sha256"),
              "metrics": (fit.get("evidence") or {}).get("metrics")}]

    # 本轮拟合的模型
    if fit["decision"] == "valid_pass":
        t0 = time.time()
        got = ra.evaluate(dict(base, phase="validate", training=train, validation=val,
                               model_path=fit["model_path"], model_sha256=fit["model_sha256"]))
        cases.append({"case": "validate_fitted", "decision": got["decision"],
                      "reason": got["reason"], "seconds": round(time.time() - t0, 3),
                      "qualifies_cancellation": got.get("qualifies_cancellation"),
                      "metrics": (got.get("evidence") or {}).get("metrics")})

    # 拿别人的模型去验：部署模型 / 旧夹具模型 / 全零
    others = {
        "validate_deployed_model": ROOT / "models/room_v1/rewired_512_20261026.json",
        "validate_old_fixture_model": ROOT / "models/room_v1/candidate_512.json",
    }
    for name, path in others.items():
        if not path.exists():
            continue
        got = ra.evaluate(dict(base, phase="validate", training=train, validation=val,
                               model_path=str(path), model_sha256=ra._sha256_file(path)))
        cases.append({"case": name, "model": path.name, "decision": got["decision"],
                      "reason": got["reason"],
                      "qualifies_cancellation": got.get("qualifies_cancellation"),
                      "metrics": (got.get("evidence") or {}).get("metrics")})

    zero = Path(run) / "zero.json"
    zero.write_bytes(json.dumps({"taps": 512, "lag_first": 1,
                                 "coefficients_q20": [0] * 512}).encode())
    got = ra.evaluate(dict(base, phase="validate", training=train, validation=val,
                           model_path=str(zero), model_sha256=ra._sha256_file(zero)))
    cases.append({"case": "validate_zero_model", "decision": got["decision"],
                  "reason": got["reason"], "qualifies_cancellation": got.get("qualifies_cancellation"),
                  "metrics": (got.get("evidence") or {}).get("metrics")})

    # 独立性：验证集借用训练集的 capture
    got = ra.evaluate(dict(base, phase="validate", training=train, validation=train[:2],
                           model_path=fit.get("model_path", str(zero)),
                           model_sha256=fit.get("model_sha256", ra._sha256_file(zero))))
    cases.append({"case": "validate_shared_capture", "decision": got["decision"],
                  "reason": got["reason"]})

    payload = {
        "schema_version": 1,
        "generated_by": "scripts/recal_algorithm_offline.py",
        "contract": ra.CONTRACT,
        "packet": args.packet,
        "split": {"training": [e["capture_id"] for e in train],
                  "validation": [e["capture_id"] for e in val]},
        "thresholds": {"band_hz": list(ra.BAND_LOW_HZ),
                       "band_reduction_min_db": ra.BAND_REDUCTION_MIN_DB,
                       "full_reduction_min_db": ra.FULL_REDUCTION_MIN_DB,
                       "min_validation_captures": ra.MIN_VALIDATION_CAPTURES},
        "cases": cases,
    }
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    p = out_dir / "cases.json"
    p.write_bytes((json.dumps(payload, indent=1, ensure_ascii=False) + "\n").encode("utf-8"))
    print("[%s] %d 例" % (p, len(cases)))
    for c in cases:
        m = c.get("metrics") or {}
        extra = ""
        if "band_reduction_median_db" in m:
            extra = "带内中位 %+.2f dB（最低 %+.2f）" % (m["band_reduction_median_db"],
                                                     m["band_reduction_min_db"])
        print("  %-28s %-18s %s %s" % (c["case"], c["decision"], extra, c["reason"][:44]))
    print("\nsha256 %s" % hashlib.sha256(p.read_bytes()).hexdigest()[:16])


if __name__ == "__main__":
    main()
